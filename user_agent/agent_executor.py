import asyncio, logging
from uuid import uuid4
from web3 import Web3
from eth_account import Account

from a2a.client import A2AClient
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events.event_queue import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import (
    # AgentCard,
    Message, MessageSendParams, SendMessageRequest, TaskQueryParams,
    GetTaskRequest, GetTaskSuccessResponse, Part, TextPart,
    TaskState, UnsupportedOperationError,
)
from a2a.utils.errors import ServerError


# ────────────────── blockchain / contract config ──────────────────
WORLDLAND_RPC_URL  = "https://seoul.worldland.foundation"   # <- fill in
CONTRACT_ADDRESS   = "0xDeaDBeef..."                        # <- fill in
CONTRACT_ABI       = [...]                                  # <- fill in

PRIVATE_KEY_USER   = "0x..."                                # <- fill in
PRICE_WEI          = 10**16                                 # 0.01 WLC example

w3 = Web3(Web3.HTTPProvider(WORLDLAND_RPC_URL))
acct = Account.from_key(PRIVATE_KEY_USER)
contract = w3.eth.contract(address=CONTRACT_ADDRESS, abi=CONTRACT_ABI)


# ────────────────── owner_agent endpoint ──────────────────
POLL_DELAY = 3  # seconds

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


# ────────────────── executor ──────────────────
class UserAgentExecutor(AgentExecutor):
    """Agent Executor for User Agent"""

    # Initialization
    def __init__(self, owner_agent_url, agent_card):
        self.owner_agent_endpoint = owner_agent_url
    
    # Core pipeline
    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        updater = TaskUpdater(event_queue, context.task_id, context.context_id)
        if not context.current_task:
            updater.submit()
        updater.start_work()

        # 1) Generate a unique contentId
        content_id = str(uuid4())
        content_hash = Web3.keccak(text=content_id)

        # 2) Pay the contract
        updater.update_status(
            TaskState.working, 
            message=self._msg(updater, f"Paying {PRICE_WEI} wei for content…"),
        )
        try:
            tx_hash = await asyncio.to_thread(self._pay_contract, content_hash)
            updater.update_status(
                TaskState.working,
                message=self._msg(updater, f"Waiting for tx {tx_hash.hex()}…")
            )
            await asyncio.to_thread(w3.eth.wait_for_transaction_receipt, tx_hash)
        except Exception as e:
            logger.exception("Payment failed")
            updater.update_status(
                TaskState.failed, 
                message=self._msg(updater, str(e))
            )
            return

        # 3) Ask the owner agent for the content
        updater.update_status(
            TaskState.working, 
            message=self._msg(updater, "Payment confirmed. Requesting content from owner…"),
        )
        async with A2AClient(self.owner_agent_endpoint) as client:
            send_req = SendMessageRequest(
                id=str(uuid4()),
                params=MessageSendParams(
                    message=Message(
                        contextId=context.context_id,
                        messageId=str(uuid4()),
                        role="user",
                        parts=[Part(TextPart(text=content_id))]
                    )
                )
            )
            resp = await client.send_message(send_req)

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
    def _pay_contract(self, content_hash):
        nonce = w3.eth.get_transaction_count(acct.address)
        txn = contract.functions.payForContent(content_hash).build_transaction({
            "from": acct.address,
            "value": PRICE_WEI,
            "gas": 100_000,
            "gasPrice": w3.to_wei("1", "gwei"),
            "nonce": nonce,
            "chainId": w3.eth.chain_id,
        })
        signed = acct.sign_transaction(txn)
        return w3.eth.send_raw_transaction(signed.rawTransaction)

    def _msg(self, updater: TaskUpdater, txt: str):
        return updater.new_agent_message([Part(TextPart(text=txt))])
    
    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise ServerError(error=UnsupportedOperationError())