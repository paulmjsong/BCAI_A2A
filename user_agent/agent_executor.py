import asyncio, json, logging
from uuid import uuid4
from web3 import Web3
from eth_account import Account

from a2a.client import A2AClient
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events.event_queue import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import (
    Message, MessageSendParams, SendMessageRequest, TaskQueryParams,
    GetTaskRequest, GetTaskSuccessResponse, Part, TextPart,
    TaskState, UnsupportedOperationError,
)
from a2a.utils.errors import ServerError


# ────────────────── blockchain / contract config ──────────────────
WORLDLAND_RPC_URL = "https://seoul.worldland.foundation"   # <- fill in
PRIVATE_KEY_USER  = "0x..."                                # <- fill in

w3 = Web3(Web3.HTTPProvider(WORLDLAND_RPC_URL))
acct = Account.from_key(PRIVATE_KEY_USER)


# ────────────────── owner_agent endpoint ──────────────────
POLL_DELAY = 3  # seconds

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


# ────────────────── executor ──────────────────
class UserAgentExecutor(AgentExecutor):
    """
    Agent Executor for User Agent

    Sends query → receives invoice → pays → sends contentId → receives content
    """

    # Initialization
    def __init__(self, owner_agent_url, agent_card):
        self.owner_agent_endpoint = owner_agent_url
    
    # Core pipeline
    async def execute(self, context: RequestContext, event_queue: EventQueue):
        updater = TaskUpdater(event_queue, context.task_id, context.context_id)
        if not context.current_task:
            updater.submit()
        updater.start_work()

        user_query = context.message.parts[0].root.text.strip()
        async with A2AClient(self.owner_agent_endpoint) as client:
            # 1) Send query
            resp = await client.send_message(
                SendMessageRequest(
                    id=str(uuid4()),
                    params=MessageSendParams(
                        message=Message(
                            contextId=context.context_id,
                            role="user",
                            messageId=str(uuid4()),
                            parts=[Part(TextPart(text=user_query))]
                        )
                    )
                )
            )

            # Wait until hitting INPUT_REQUIRED and get invoice
            task = resp.root.result
            while task.status.state == TaskState.working:
                await asyncio.sleep(POLL_DELAY)
                gt = await client.get_task(
                    GetTaskRequest(
                        id=str(uuid4()),
                        params=TaskQueryParams(id=task.id))
                )
                task = gt.root.result

            if task.status.state != TaskState.input_required:
                return self._update_fail(updater, "Owner agent did not issue invoice")

            invoice = json.loads(task.status.message.parts[0].root.text)
            content_id = invoice["contentId"]
            contract   = w3.eth.contract(address=invoice["contract"], abi=invoice["abi"])
            price_wei  = int(invoice["priceWei"])

            # 2) Pay owner
            self._update_status(updater, "Paying contract…")
            txh = await asyncio.to_thread(self._pay, contract, content_id, price_wei)
            await asyncio.to_thread(w3.eth.wait_for_transaction_receipt, txh)

            # 3) Send contentId to owner
            resp2 = await client.send_message(
                SendMessageRequest(
                    id=str(uuid4()),
                    params=MessageSendParams(
                        message=Message(
                            contextId=context.context_id,
                            taskId=task.id,  # continue same task
                            role="user",
                            messageId=str(uuid4()),
                            parts=[Part(TextPart(text=content_id))]
                        )
                    )
                )
            )

            # 4) Poll until completed
            t2 = resp2.root.result
            while t2.status.state not in (TaskState.completed, TaskState.failed):
                await asyncio.sleep(POLL_DELAY)
                gt = await client.get_task(
                    GetTaskRequest(
                        id=str(uuid4()),
                        params=TaskQueryParams(id=t2.id))
                )
                t2 = gt.root.result

            if t2.status.state == TaskState.completed:
                updater.add_artifact(t2.artifacts[0].parts)
                updater.complete()
            else:
                self._update_fail(updater, "Owner agent failed: "+t2.status.message.parts[0].root.text)

        # 4) Wait (poll) until task completes
        if hasattr(resp.root, "result") and resp.root.result.id:
            task_id = resp.root.result.id
            while True:
                await asyncio.sleep(POLL_DELAY)
                tg_resp = await client.get_task(
                    GetTaskRequest(id=str(uuid4()), params=TaskQueryParams(id=task_id))
                )
                if not isinstance(tg_resp.root, GetTaskSuccessResponse):
                    updater.update_status(
                        TaskState.failed, 
                        message=self._msg(updater, "Owner agent error"),
                    )
                    return
                task = tg_resp.root.result
                if task.status.state == TaskState.completed:
                    parts = task.artifacts[0].parts
                    updater.add_artifact(parts)
                    updater.complete()
                    return
                elif task.status.state == TaskState.failed:
                    updater.update_status(
                        TaskState.failed, 
                        message=task.status.message,
                    )
                    return
                # else still working; loop
    
    # Helper functions
    def _pay_contract(self, contract, content_id: str, value: int):
        nonce = w3.eth.get_transaction_count(acct.address)
        txn = contract.functions.payForContent(Web3.keccak(text=content_id)).build_transaction({
            "from": acct.address,
            "value": value,
            "gas": 100000,
            "gasPrice": w3.to_wei("1", "gwei"),
            "nonce": nonce,
            "chainId": w3.eth.chain_id,
        })
        signed = acct.sign_transaction(txn)
        return w3.eth.send_raw_transaction(signed.rawTransaction)
    
    def _update_status(self, updater: TaskUpdater, msg: str):
        updater.update_status(TaskState.working, message=self._msg(updater, msg))

    def _update_fail(self, updater: TaskUpdater, msg: str):
        updater.update_status(TaskState.failed, message=self._msg(updater, msg))

    def _msg(self, updater: TaskUpdater, txt: str):
        return updater.new_agent_message([Part(TextPart(text=txt))])
    
    async def cancel(self, context: RequestContext, event_queue: EventQueue):
        raise ServerError(error=UnsupportedOperationError())