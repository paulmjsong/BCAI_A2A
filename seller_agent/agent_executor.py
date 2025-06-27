import asyncio, hashlib, httpx, json, logging, os, time
from dotenv import load_dotenv
from uuid import uuid4
from web3 import Web3
from eth_account import Account

from google.adk.events import Event, EventActions
from google.adk.sessions import InMemorySessionService

from a2a.client import A2AClient
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events.event_queue import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import (
    AgentCard, Message, MessageSendParams, SendMessageRequest,
    GetTaskRequest, GetTaskSuccessResponse, TaskState, TaskQueryParams,
    Part, TextPart, UnsupportedOperationError,
)
from a2a.utils.errors import ServerError


# ────────────────── blockchain / contract config ──────────────────
load_dotenv()

WORLDLAND_RPC_URL = "https://seoul.worldland.foundation/"
w3 = Web3(Web3.HTTPProvider(WORLDLAND_RPC_URL))

PRIVATE_KEY_SELLER = os.getenv("PRIVATE_KEY_SELLER")
acct = Account.from_key(PRIVATE_KEY_SELLER)

with open("billing_agent/contract_abi.json", "r") as f:
    CONTRACT_ABI = json.load(f)
CONTRACT_ADDR = os.getenv("CONTRACT_ADDRESS")
PRICE_WEI     = 10**18  # 1 WLC example
contract      = w3.eth.contract(address=CONTRACT_ADDR, abi=CONTRACT_ABI)

POLL_DELAY = 3  # seconds
GLOBAL_SESSION_SERVICE = InMemorySessionService()

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


# ────────────────── executor ──────────────────
class BillingAgentExecutor(AgentExecutor):
    """
    Agent Executor for Billing Agent
    
    Phase 1:
    1. receive purchase intent
    2. create order                     (on-chain)
    3. send quote

    Phase 2:
    4. verify payment                   (on-chain)
    5. call research agent
    6. send content + hash

    Phase 3:
    7. receive verification result
        7a. if success → settle payment (on-chain)
        7b. if fail → refund payment    (on-chain)
    """

    # Initialization
    def __init__(self, agent_card, research_agent_url):
        self.app_name                = agent_card.name
        self.research_agent_endpoint = research_agent_url
        self.session_service         = GLOBAL_SESSION_SERVICE
    
    # Core pipeline
    async def execute(self, context: RequestContext, event_queue: EventQueue):
        updater = TaskUpdater(event_queue, context.task_id, context.context_id)
        if not context.current_task:
            updater.submit()
        updater.start_work()

        parts = context.message.parts
        if not parts or not isinstance(parts[0].root, TextPart):
            return self._fail(updater, "Malformed request")
        
        session = await self._get_session(context)
        orders  = session.state.get("orders", {})

        # PHASE 1
        if len(parts) == 2 and parts[1].root.text.startswith("0x"):
            logger.debug("PHASE 1")

            # 1) Receive purchase intent
            user_query   = parts[0].root.text.strip()
            buyer_addr   = Web3.to_checksum_address(parts[1].root.text.strip())
            order_id     = str(uuid4())
            order_b32    = Web3.keccak(text=order_id)
            
            # 2) Create order on-chain
            self._step(updater, "Creating on-chain order…")
            txh = await asyncio.to_thread(self._create_order, order_b32, buyer_addr, PRICE_WEI)
            await asyncio.to_thread(w3.eth.wait_for_transaction_receipt, txh)

            orders[order_id] = {
                "buyer": buyer_addr,
                "query": user_query,
                "status": "invoice_sent",
                "hash":  None   # filled after content generation
            }
            await self._save(session, orders)

            # 3) Send quote to buyer
            quote = {
                "contract": CONTRACT_ADDR,
                "chainId":  w3.eth.chain_id,
                "priceWei": PRICE_WEI,
                "orderId":  order_id,
                "abi":      CONTRACT_ABI,
            }
            updater.update_status(
                TaskState.input_required,
                message=updater.new_agent_message([Part(TextPart(text=json.dumps(quote)))]),
            )
            return
        
        # PHASE 2
        if len(parts) == 2 and parts[0].root.text in orders:
            logger.debug("PHASE 2")
            order_id   = parts[0].root.text.strip()
            buyer_addr = Web3.to_checksum_address(parts[1].root.text.strip())
            order      = orders[order_id]
            order_b32  = Web3.keccak(text=order_id)

            if order["buyer"] != buyer_addr:
                return self._fail(updater, "Buyer address mismatch")

            # 4) Verify payment
            self._step(updater, "Verifying on-chain payment...")
            status_code = contract.functions.orders(order_b32).call()[4]  # Status enum
            if status_code != 2:   # Funded
                return self._fail(updater, "Payment not found on-chain")

            # 5) Call research agent
            self._step(updater, "Payment confirmed. Fetching content...")
            content_parts = await self._call_research_agent(order["query"])
            if content_parts is None:
                return self._fail(updater, "Research agent failed")
            
            # 6) Send content + hash to buyer
            content_txt = "".join(p.root.text for p in content_parts)
            hash = hashlib.sha256(content_txt.encode()).hexdigest()
            order["status"] = "content_sent"
            order["hash"]   = hash
            await self._save(session, orders)

            updater.update_status(
                TaskState.input_required,
                message=updater.new_agent_message([
                    Part(TextPart(text=content_txt)),
                    Part(TextPart(text=hash)),
                ]),
            )
            return
        
        # PHASE 3
        if len(parts) == 1:
            logger.debug("PHASE 3")
            body = parts[0].root.text.strip().lower()
            
            # 7) Find the latest order still awaiting confirm/dispute
            pending = next((oid for oid, r in orders.items()
                            if r["status"] == "content_sent"), None)
            if not pending:
                return self._fail(updater, "No pending order")

            order_b32 = Web3.keccak(text=pending)

            if "goods received" in body:
                # 7a) Settle payment
                self._step(updater, "Settling payment...")
                txh = await asyncio.to_thread(self._settle, order_b32)
                await asyncio.to_thread(w3.eth.wait_for_transaction_receipt, txh)
                orders[pending]["status"] = "settled"
            
            elif "content verification failed" in body:
                # 7b) Refund buyer
                self._step(updater, "Refunding buyer...")
                txh = await asyncio.to_thread(self._refund, order_b32)
                await asyncio.to_thread(w3.eth.wait_for_transaction_receipt, txh)
                orders[pending]["status"] = "refunded"
            
            await self._save(session, orders)
            updater.complete()
            return

        return self._fail(updater, "Unexpected message format")

    # On-chain helpers
    def _create_order(self, order_b32, buyer, amount_wei):
        nonce = w3.eth.get_transaction_count(acct.address)
        tx = contract.functions.createOrder(order_b32, buyer, amount_wei).build_transaction({
            "from": acct.address,
            "gas": 150_000,
            "gasPrice": w3.eth.gas_price,
            "nonce": nonce,
            "chainId": w3.eth.chain_id,
        })
        return self._send(tx)

    def _settle(self, order_b32):
        nonce = w3.eth.get_transaction_count(acct.address)
        tx = contract.functions.settlePayment(order_b32).build_transaction({
            "from": acct.address,
            "gas": 120_000,
            "gasPrice": w3.eth.gas_price,
            "nonce": nonce,
            "chainId": w3.eth.chain_id,
        })
        return self._send(tx)

    def _refund(self, order_b32):
        nonce = w3.eth.get_transaction_count(acct.address)
        tx = contract.functions.refund(order_b32).build_transaction({
            "from": acct.address,
            "gas": 120_000,
            "gasPrice": w3.eth.gas_price,
            "nonce": nonce,
            "chainId": w3.eth.chain_id,
        })
        return self._send(tx)

    def _send(self, unsigned_tx):
        signed = acct.sign_transaction(unsigned_tx)
        return w3.eth.send_raw_transaction(signed.raw_transaction)
    
    # ResearchAgent helper
    async def _call_research_agent(self, user_query: str):
        async with httpx.AsyncClient(timeout=60) as httpx_client:
            client = A2AClient(httpx_client=httpx_client, url=self.research_agent_endpoint)
            resp = await client.send_message(
                SendMessageRequest(
                    id=str(uuid4()),
                    params=MessageSendParams(
                        message=Message(
                            contextId=str(uuid4()),
                            role="user",
                            messageId=str(uuid4()),
                            parts=[Part(TextPart(text=user_query))]
                        )
                    )
                )
            )
            task_id = resp.root.result.id
            while True:
                await asyncio.sleep(POLL_DELAY)
                gt = await client.get_task(
                    GetTaskRequest(
                        id=str(uuid4()),
                        params=TaskQueryParams(id=task_id)
                    )
                )
                if not isinstance(gt.root, GetTaskSuccessResponse):
                    return None
                t = gt.root.result
                if t.status.state == TaskState.completed and t.artifacts:
                    return t.artifacts[0].parts
                if t.status.state == TaskState.failed:
                    return None
    
    # Misc helpers
    async def _save(self, session, orders):
        await self.session_service.append_event(
            session,
            Event(
                invocation_id=str(uuid4()),
                author=self.app_name,
                timestamp=time.time(),
                actions=EventActions(state_delta={"orders": orders}),
            ),
        )
    
    def _step(self, updater: TaskUpdater, msg: str):
        logger.debug(msg)
        updater.update_status(
            TaskState.working, 
            message=updater.new_agent_message([Part(TextPart(text=msg))])
        )

    def _fail(self, updater: TaskUpdater, msg: str):
        logger.error(msg)
        updater.update_status(
            TaskState.failed, 
            message=updater.new_agent_message([Part(TextPart(text=msg))])
        )

    async def _get_session(self, ctx: RequestContext):
        return (
            await self.session_service.get_session(
                app_name=self.app_name, 
                user_id="anonymous", 
                session_id=ctx.task_id, 
            ) or await self.session_service.create_session(
                app_name=self.app_name, 
                user_id="anonymous", 
                session_id=ctx.task_id, 
            )
        )
    
    async def cancel(self, *_):
        raise ServerError(error=UnsupportedOperationError())