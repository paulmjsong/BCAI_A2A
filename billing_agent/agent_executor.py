import asyncio, httpx, json, logging, os, time
from dotenv import load_dotenv
from uuid import uuid4
from web3 import Web3

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

with open("billing_agent/contract_abi.json", "r") as f:
    CONTRACT_ABI = json.load(f)
CONTRACT_ADDRESS = os.getenv("CONTRACT_ADDRESS")
PRICE_WEI        = 10**18  # 1 WLC example
contract = w3.eth.contract(address=CONTRACT_ADDRESS, abi=CONTRACT_ABI)

GLOBAL_SESSION_SERVICE = InMemorySessionService()
POLL_DELAY = 3  # seconds

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


# ────────────────── executor ──────────────────
class BillingAgentExecutor(AgentExecutor):
    """
    Agent Executor for Billing Agent
    
    First call: receives query → sends invoice (INPUT_REQUIRED)
    Second call: receives cid → verifies payment → calls research agent → sends content
    """

    # Initialization
    def __init__(self, agent_card, research_agent_url):
        self.app_name = agent_card.name
        self.research_agent_endpoint = research_agent_url
        self.session_service = GLOBAL_SESSION_SERVICE
    
    # Core pipeline
    async def execute(self, context: RequestContext, event_queue: EventQueue):
        updater = TaskUpdater(event_queue, context.task_id, context.context_id)
        if not context.current_task:
            updater.submit()
        updater.start_work()

        parts = context.message.parts
        if not parts or not isinstance(parts[0].root, TextPart):
            return self._update_fail(updater, "Malformed request")
        
        session = await self._get_session(context)
        invoices = session.state.get("invoices", {})

        # ---------------- first request ----------------
        # Expecting: query
        if len(parts) == 1:
            logger.debug("FIRST REQUEST")
            query = parts[0].root.text.strip()

            if query not in invoices:
                # treat as fresh query
                content_id = str(uuid4())
                invoices[content_id] = query

                await self.session_service.append_event(
                    session,
                    Event(
                        invocation_id=str(uuid4()),
                        author=self.app_name,
                        timestamp=time.time(),
                        actions=EventActions(state_delta={"invoices": invoices}),
                    ),
                )
                self._update_status(updater, "Sending invoice...")
                invoice = {
                    "contract": CONTRACT_ADDRESS,
                    "chainId": w3.eth.chain_id,
                    "priceWei": PRICE_WEI,
                    "contentId": content_id,
                    "abi": CONTRACT_ABI,
                }
                updater.update_status(
                    TaskState.input_required,
                    message=updater.new_agent_message(
                        [Part(TextPart(text=json.dumps(invoice)))]
                    ),
                )
        
        # ---------------- second request ----------------
        # Expecting: content_id, payer_address
        elif len(parts) == 2:
            logger.debug("SECOND REQUEST")
            content_id = parts[0].root.text.strip()
            payer_addr = parts[1].root.text.strip()

            user_query = invoices.get(content_id)
            if not user_query:
                return self._update_fail(updater, "Unknown contentId")

            # 1) Verify payment
            self._update_status(updater, "Verifying payment...")
            if not await asyncio.to_thread(self._paid, payer_addr, content_id):
                return self._update_fail(updater, "Payment not found on-chain")

            # 2) Call research agent
            self._update_status(updater, "Payment confirmed. Fetching content...")
            content_parts = await self._call_research_agent(user_query)
            if content_parts is None:
                return self._update_fail(updater, "Research agent failed")
            
            # 3) Reply to user
            updater.add_artifact(content_parts)
            updater.complete()
            logger.debug(f"Task completed")

            # 4) Remove fulfilled invoice
            invoices.pop(content_id, None)
            await self.session_service.append_event(
                session,
                Event(
                    invocation_id=str(uuid4()),
                    author=self.app_name,
                    timestamp=time.time(),
                    actions=EventActions(state_delta={"invoices": invoices}),
                ),
            )
        else:
            return self._update_fail(updater, "Unexpected number of parts")


    # Helper functions
    def _paid(self, payer_addr: str, content_id: str) -> bool:
        return contract.functions.paidContent(payer_addr, Web3.keccak(text=content_id)).call()
    
    async def _call_research_agent(self, user_query: str):
        async with httpx.AsyncClient(timeout=60) as httpx_client:
            client = A2AClient(httpx_client=httpx_client, url=self.research_agent_endpoint)
            send_req = SendMessageRequest(
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
            resp = await client.send_message(send_req)
            if not hasattr(resp.root, "result") or not hasattr(resp.root.result, "id"):
                return None
            task_id = resp.root.result.id
            # poll
            while True:
                await asyncio.sleep(POLL_DELAY)
                tg_resp = await client.get_task(
                    GetTaskRequest(
                        id=str(uuid4()),
                        params=TaskQueryParams(id=task_id)
                    )
                )
                if not isinstance(tg_resp.root, GetTaskSuccessResponse):
                    return None
                task = tg_resp.root.result
                if task.status.state == TaskState.completed and task.artifacts:
                    return task.artifacts[0].parts
                if task.status.state == TaskState.failed:
                    return None
    
    async def cancel(self, *_):
        raise ServerError(error=UnsupportedOperationError())
    
    def _update_status(self, updater: TaskUpdater, msg: str):
        updater.update_status(TaskState.working, message=self._msg(updater, msg))

    def _update_fail(self, updater: TaskUpdater, msg: str):
        updater.update_status(TaskState.failed, message=self._msg(updater, msg))

    def _msg(self, updater: TaskUpdater, txt: str):
        logger.debug(txt)
        return updater.new_agent_message([Part(TextPart(text=txt))])

    async def _get_session(self, context: RequestContext):
        session = await self.session_service.get_session(
            app_name=self.app_name, 
            user_id="anonymous", 
            session_id=context.task_id, 
        ) or await self.session_service.create_session(
            app_name=self.app_name, 
            user_id="anonymous", 
            session_id=context.task_id, 
        )
        return session