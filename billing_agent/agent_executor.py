import asyncio, json, logging, os
from dotenv import load_dotenv
from uuid import uuid4
from web3 import Web3
# from eth_account import Account

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
load_dotenv()
WORLDLAND_RPC_URL = "https://seoul.worldland.foundation/"
w3 = Web3(Web3.HTTPProvider(WORLDLAND_RPC_URL))

# PRIVATE_KEY_USER  = os.getenv("PRIVATE_KEY")
# acct = Account.from_key(PRIVATE_KEY_OWNER)

CONTRACT_ADDRESS  = os.getenv("CONTRACT_ADDRESS")
CONTRACT_ABI      = os.getenv("CONTRACT_ABI")
PRICE_WEI         = 10**16  # 0.01 WLC example
contract = w3.eth.contract(address=CONTRACT_ADDRESS, abi=CONTRACT_ABI)

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
    def __init__(self, research_agent_url):
        self.research_agent_endpoint = research_agent_url
    
    # Core pipeline
    async def execute(self, context: RequestContext, event_queue: EventQueue):
        updater = TaskUpdater(event_queue, context.task_id, context.context_id)
        if not context.current_task:
            updater.submit()
        updater.start_work()

        # Expect: Part-0 = contentId, Part-1 = user query (text)
        parts = context.message.parts
        if len(parts) < 2 or not all(isinstance(p.root, TextPart) for p in parts[:2]):
            self._update_fail(updater, "Malformed request")

        text0  = parts[0].root.text.strip()
        session = await self._get_session(context)

        # ---------------- First request ----------------
        if text0 not in session.state.get("invoices", {}):
            # treat as fresh query
            content_id = str(uuid4())
            session.state.setdefault("invoices", {})[content_id] = text0
            await self._save_session(session)

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
            return
        
        # ---------------- Second request ----------------
        content_id = text0
        user_query  = session.state["invoices"].get(content_id)
        if not user_query:
            return self._fail(updater, "Unknown contentId")

        # 1) Verify payment
        self._update_status(updater, "Verifying payment…")
        if not await asyncio.to_thread(self._paid, content_id):
            self._update_fail(updater, "Payment not found on-chain")
            return

        # 2) Call research agent
        self._update_status(updater, "Payment confirmed. Fetching content…")
        content_parts = await self._call_research_agent(user_query)
        if content_parts is None:
            self._update_fail(updater, "Research agent failed")
        
        # 3) Reply to user
        updater.add_artifact(content_parts)
        updater.complete()
        # cleanup
        del session.state["invoices"][content_id]
        await self._save_session(session)


    # Helper functions
    def _paid(self, content_id: str) -> bool:
        return contract.functions.paidContent(Web3.keccak(text=content_id)).call()
    
    async def _call_research_agent(self, user_query: str):
        async with A2AClient(self.research_agent_endpoint) as client:
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
        return updater.new_agent_message([Part(TextPart(text=txt))])

    async def _get_session(self, context: RequestContext):
        return await context.runner.session_service.get_session(
            app_name=context.context_id, session_id=context.context_id
        ) or await context.runner.session_service.create_session(
            app_name=context.context_id, session_id=context.context_id
        )

    async def _save_session(self, session):
        await session.service.update_session(session)


# TODO: add functionality for withdrawal and price update