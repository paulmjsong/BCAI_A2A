import asyncio, logging
from uuid import uuid4
from web3 import Web3

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
WORLDLAND_RPC_URL  = "https://seoul.worldland.foundation"   # <- fill in
CONTRACT_ADDRESS   = "0xDeaDBeef..."                        # <- fill in
CONTRACT_ABI       = [...]                                  # <- fill in

w3 = Web3(Web3.HTTPProvider(WORLDLAND_RPC_URL))
contract = w3.eth.contract(address=CONTRACT_ADDRESS, abi=CONTRACT_ABI)


# ────────────────── research_agent endpoint ──────────────────
POLL_DELAY_SECONDS = 3

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


# ────────────────── executor ──────────────────
class BillingAgentExecutor(AgentExecutor):
    """Agent Executor for Billing Agent"""

    # Initialization
    def __init__(self, research_agent_url):
        self.research_agent_endpoint = research_agent_url
    
    # Core pipeline
    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        updater = TaskUpdater(event_queue, context.task_id, context.context_id)
        if not context.current_task:
            updater.submit()
        updater.start_work()

        # Expect: Part-0 = contentId, Part-1 = user query (text)
        parts = context.message.parts
        if len(parts) < 2 or not all(isinstance(p.root, TextPart) for p in parts[:2]):
            self._update_fail(updater, "Malformed request")

        content_id  = parts[0].root.text.strip()
        user_query  = parts[1].root.text.strip()
        content_hash = Web3.keccak(text=content_id)

        self._update_working(updater, "Verifying payment on-chain…")

        # 1) Verify on-chain payment
        try:
            paid = await asyncio.to_thread(
                contract.functions.paidContent(content_hash).call
            )
        except Exception as e:
            logger.exception("Blockchain call failed")
            self._update_fail(updater, str(e))
            return

        if not paid:
            self._update_fail(updater, "Payment not found on-chain")
            return

        # 2) Forward query to research agent
        self._update_working(updater, "Payment confirmed. Asking research agent…")

        async with A2AClient(self.research_agent_endpoint) as client:
            send_req = SendMessageRequest(
                id=str(uuid4()),
                params=MessageSendParams(
                    message=Message(
                        contextId=context.context_id,
                        messageId=str(uuid4()),
                        role="user",
                        parts=[Part(TextPart(text=user_query))]
                    )
                )
            )
            resp = await client.send_message(send_req)

            if not hasattr(resp.root, "result") or not hasattr(resp.root.result, "id"):
                self._update_fail(updater, "Research agent returned no task")
                return

            task_id = resp.root.result.id

            # 3) Poll until research agent completes
            while True:
                await asyncio.sleep(POLL_DELAY_SECONDS)
                tg_resp = await client.get_task(
                    GetTaskRequest(id=str(uuid4()),
                                   params=TaskQueryParams(id=task_id))
                )
                if not isinstance(tg_resp.root, GetTaskSuccessResponse):
                    self._update_fail(updater, "Error querying research task")
                    return

                task = tg_resp.root.result
                if task.status.state == TaskState.completed and task.artifacts:
                    updater.add_artifact(task.artifacts[0].parts)
                    updater.complete()
                    return
                elif task.status.state == TaskState.failed:
                    self._update_fail(updater, task.status.message.parts[0].root.text)
                    return
                # else still working → loop

    # Helper functions
    def _update_working(self, updater: TaskUpdater, msg: str):
        updater.update_status(TaskState.working, message=self._msg(updater, msg))

    def _update_fail(self, updater: TaskUpdater, msg: str):
        updater.update_status(TaskState.failed, message=self._msg(updater, msg))

    def _msg(self, updater: TaskUpdater, txt: str):  # quick TaskMessage factory
        return updater.new_agent_message([Part(TextPart(text=txt))])
    
    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise ServerError(error=UnsupportedOperationError())