import asyncio, hashlib, httpx, json, logging, os
from dotenv import load_dotenv
from uuid import uuid4
from web3 import Web3
from eth_account import Account

from a2a.client import A2AClient
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events.event_queue import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import (
    Message, MessageSendParams, SendMessageRequest, TaskQueryParams,
    GetTaskRequest, Part, TextPart,
    TaskState, UnsupportedOperationError,
)
from a2a.utils.errors import ServerError


# ────────────────── blockchain / contract config ──────────────────
load_dotenv()

WORLDLAND_RPC_URL = "https://seoul.worldland.foundation/"
w3 = Web3(Web3.HTTPProvider(WORLDLAND_RPC_URL))

PRIVATE_KEY_BUYER = os.getenv("PRIVATE_KEY_BUYER")
acct = Account.from_key(PRIVATE_KEY_BUYER)

POLL_DELAY = 3  # seconds

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


# ────────────────── executor ──────────────────
class BuyerAgentExecutor(AgentExecutor):
    """
    Agent Executor for Buyer Agent
    
    Phase 1:
    1.  send purchase intent

    Phase 2:
    2.  receive quote
    3.  make payment                    (on-chain)
    4.  send order confirmation

    Phase 3:
    5.  receive content
    6.  verify content hash
        6a. if match → confirm order    (on-chain)
        6b. if mismatch → raise dispute (on-chain)
    """
    
    # Core pipeline
    async def execute(self, context: RequestContext, event_queue: EventQueue):
        updater = TaskUpdater(event_queue, context.task_id, context.context_id)
        if not context.current_task:
            updater.submit()
        updater.start_work()

        user_query = context.message.parts[0].root.text.strip()
        remote_url = context.message.parts[1].root.text.strip()

        # change timeout
        async with httpx.AsyncClient(timeout=3600) as httpx_client:
            client = A2AClient(httpx_client=httpx_client, url=remote_url)
            
            # 1) Send purchase intent to seller
            self._step(updater, "Sending purchase intent...")
            resp1 = await client.send_message(
                SendMessageRequest(
                    id=str(uuid4()),
                    params=MessageSendParams(
                        message=Message(
                            contextId=context.context_id,
                            role="user",
                            messageId=str(uuid4()),
                            parts=[
                                Part(TextPart(text=user_query)),
                                Part(TextPart(text=acct.address)),
                            ],
                        )
                    )
                )
            )

            # 2) Poll for quote from seller
            self._step(updater, "Waiting for quote from seller...")
            # # original code
            # task1 = await self._poll_task(
            #     client, resp1.root.result.id, updater
            # )

            # ----- edit -----
            task_id1 = (
                resp1.root.result
                if isinstance(resp1.root.result, str)
                else resp1.root.result.id
            )

            task1 = await self._poll_task(client, task_id1, updater)
            # ----- end of edit -----
            if task1.status.state != TaskState.input_required:
                return self._fail(updater, "Seller did not provide quote")
            
            # ----- edit -----
            try:
                quote = json.loads(task1.status.message.parts[0].root.text)
            except (json.JSONDecodeError, AttributeError) as exc:
                return self._fail(updater, f"Malformed quote: {exc}")
            
            required = {"chainId", "orderId", "contract", "abi", "priceWei"}
            if missing := required - quote.keys():
                return self._fail(updater, f"Quote missing fields: {', '.join(missing)}")

            # ----- end of edit -----

            if int(quote["chainId"]) != w3.eth.chain_id:
                return self._fail(updater, "Seller quote targets a different chain")
            
            # # original code
            # quote = json.loads(task1.status.message.parts[0].root.text)
            order_id  = quote["orderId"]
            order_b32 = Web3.keccak(text=order_id)  # bytes32 key
            contract  = w3.eth.contract(address=quote["contract"], abi=quote["abi"])
            price_wei = int(quote["priceWei"])

            # 3) Pay seller's contract on blockchain (escrow payment)
            self._step(updater, "Paying contract...")
            txh = await asyncio.to_thread(self._make_payment, contract, order_b32, price_wei)
            await asyncio.to_thread(w3.eth.wait_for_transaction_receipt, txh)

            # 4) Send order confirmation to seller (orderId + buyer address)
            self._step(updater, "Sending order confirmation...")

            thread_id1 = getattr(task1, "id", task_id1) # added code

            resp2 = await client.send_message(
                SendMessageRequest(
                    id=str(uuid4()),
                    params=MessageSendParams(
                        message=Message(
                            contextId=context.context_id,
                            # taskId=task1.id,   # continue same task thread (original code)
                            taskId = thread_id1, # added code
                            role="user",
                            messageId=str(uuid4()),
                            parts=[
                                Part(TextPart(text=order_id)),
                                Part(TextPart(text=acct.address)),
                            ],
                        )
                    )
                )
            )

            # 5) Poll for content delivery with hash from seller
            self._step(updater, "Waiting for content delivery...")

            # # original code
            # task2 = await self._poll_task(
            #     client, resp2.root.result.id, updater
            # )

            # ----- edit -----
            task_id2 = (
                resp2.root.result
                if isinstance(resp2.root.result, str)
                else resp2.root.result.id
            )

            task2 = await self._poll_task(
                client, task_id2, updater
            )
            # ----- end of edit -----

            if task2.status.state == TaskState.failed:
                return self._fail(updater, "Seller agent failed: " + 
                                  task2.status.message.parts[0].root.text)

            # # 6) Verify content hash (original code)
            # self._step(updater, "Content received. Verifying hash...")
            # content_data  = task2.status.message.parts[0].root.text
            # provided_hash = task2.status.message.parts[1].root.text
            # computed_hash = hashlib.sha256(content_data.encode('utf-8')).hexdigest()

            # ----- edit -----
            # 6) Verify content hash
            self._step(updater, "Content received. Verifying hash...")

            provided_hash = task2.status.message.parts[0].root.text.strip()

            if not task2.artifacts:
                return self._fail(updater, "Seller sent no artifact with the content")

            content_data = "".join(p.root.text for p in task2.artifacts[0].parts)
            computed_hash = hashlib.sha256(content_data.encode('utf-8')).hexdigest()
            # ----- end of edit -----

            if computed_hash.lower() == provided_hash.lower():
                # 6a) Hash matches → confirm order
                self._step(updater, "Hash verified. Confirming order...")
                txh2 = await asyncio.to_thread(self._confirm_order, contract, order_b32)
                await asyncio.to_thread(w3.eth.wait_for_transaction_receipt, txh2)

                # Notify seller about successful delivery
                thread_id2 = getattr(task2, "id", task_id2) # added code
                await client.send_message(
                    SendMessageRequest(
                        id=str(uuid4()),
                        params=MessageSendParams(
                            message=Message(
                                contextId=context.context_id,
                                # taskId=task2.id, # original code
                                taskId=thread_id2, # added code
                                role="user",
                                messageId=str(uuid4()),
                                parts=[
                                    Part(TextPart(text="Goods Received Confirmation")),
                                ],
                            )
                        )
                    )
                )
                updater.add_artifact([Part(TextPart(text=content_data))])
                updater.complete()
                logger.debug("Transaction completed: content verified and delivered.")
            else:
                # 6b) Hash mismatch → raise dispute
                self._step(updater, "Hash mismatch! Opening dispute and notifying seller...")
                txh3 = await asyncio.to_thread(self._raise_dispute, contract, order_b32)
                await asyncio.to_thread(w3.eth.wait_for_transaction_receipt, txh3)

                # Notify seller about the dispute
                resp3 = await client.send_message(
                    SendMessageRequest(
                        id=str(uuid4()),
                        params=MessageSendParams(
                            message=Message(
                                contextId=context.context_id,
                                # taskId=task2.id,                     # original code
                                taskId=getattr(task2, "id", task_id2), # added code
                                role="user",
                                messageId=str(uuid4()),
                                parts=[
                                    Part(TextPart(text="Content Verification Failed")),
                                ],
                            )
                        )
                    )
                )
                text = "Dispute opened. Waiting for seller refund."
                updater.add_artifact([Part(TextPart(text=text))])
                updater.complete()
                logger.debug(text)
    
    # On-chain helpers
    def _make_payment(self, contract, order_b32, value_wei: int):
        nonce = w3.eth.get_transaction_count(acct.address)
        txn = contract.functions.makePayment(order_b32).build_transaction({
            "from": acct.address,
            "value": value_wei,
            "gas": 120_000,
            "gasPrice": w3.eth.gas_price,
            "nonce": nonce,
            "chainId": w3.eth.chain_id,
        })
        return self._send(txn)
    
    def _confirm_order(self, contract, order_b32):
        nonce = w3.eth.get_transaction_count(acct.address)
        txn = contract.functions.confirmOrder(order_b32).build_transaction({
            "from": acct.address,
            "gas": 100_000,
            "gasPrice": w3.eth.gas_price,
            "nonce": nonce,
            "chainId": w3.eth.chain_id,
        })
        return self._send(txn)
    
    def _raise_dispute(self, contract, order_b32):
        nonce = w3.eth.get_transaction_count(acct.address)
        txn = contract.functions.raiseDispute(order_b32).build_transaction({
            "from": acct.address,
            "gas": 100_000,
            "gasPrice": w3.eth.gas_price,
            "nonce": nonce,
            "chainId": w3.eth.chain_id,
        })
        return self._send(txn)
    
    def _send(self, txn):
        signed = acct.sign_transaction(txn)
        return w3.eth.send_raw_transaction(signed.raw_transaction)
    
    # Misc helpers
    async def _poll_task(self, client, task_id: str, updater: TaskUpdater):
        while True:
            # # original code
            # gt = await client.get_task(
            #     GetTaskRequest(
            #         id=str(uuid4()),
            #         params=TaskQueryParams(id=task_id)
            #     )
            # )
            # t = gt.root.result
            # if t.status.state != TaskState.working:
            #     return t
            # await asyncio.sleep(POLL_DELAY)

            # ----- edit -----
            resp = await client.get_task(
                GetTaskRequest(
                    id = str(uuid4()),
                    params=TaskQueryParams(id=task_id)
                )
            )

            task = resp.root.result
            if task.status.state in (TaskState.completed, TaskState.failed):
                return task

            await asyncio.sleep(POLL_DELAY)
            # ----- end of edit -----

            self._step(updater, f"Still waiting...")
    
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
    
    async def cancel(self, context: RequestContext, event_queue: EventQueue):
        raise ServerError(error=UnsupportedOperationError())