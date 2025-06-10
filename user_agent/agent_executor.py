import asyncio, httpx, json, logging, os
# import google.generativeai as genai
from dotenv import load_dotenv
from uuid import uuid4
from web3 import Web3
from eth_account import Account

# from google.adk.agents.llm_agent import LlmAgent

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
# GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
# genai.configure(api_key=GOOGLE_API_KEY)

WORLDLAND_RPC_URL = "https://seoul.worldland.foundation/"
w3 = Web3(Web3.HTTPProvider(WORLDLAND_RPC_URL))

PRIVATE_KEY_USER  = os.getenv("PRIVATE_KEY_USER")
acct = Account.from_key(PRIVATE_KEY_USER)

POLL_DELAY = 3  # seconds

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


# # ────────────────── build LLM agent ──────────────────
# def build_llm_agent() -> LlmAgent:
#     prompt = """
# You are a research-trend analyst AI.

# • Use the `search_papers` tool to fetch up to 10 recent, relevant arXiv papers.
# • For each paper, write a concise (2-3 sentence) English summary of the abstract.
# • After listing the papers, add a **“Recent Trend Analysis”** section that synthesizes key methods, directions, or gaps you observe, citing specific paper titles or authors where useful.
# • Output format (Markdown):

# 1. **Title** (Authors, YYYY-MM-DD)  
#    *Categories:* cs.AI, cs.CL  
#    *Summary:* ...

# 2. ...

# ## Recent Trend Analysis
# - ...

# Keep the analysis clear, avoid jargon where possible, and write entirely in **English**.
# """
#     return LlmAgent(
#         model='gemini-2.5-flash-preview-05-20',
#         name='research_agent',
#         description=(
#             "Analyzes arXiv papers and produces Korean trend summaries"
#         ),
#         instruction=prompt,
#         tools=[commission_remote_agent],
#     )


# ────────────────── executor ──────────────────
class UserAgentExecutor(AgentExecutor):
    """
    Agent Executor for User Agent

    Sends query → receives invoice → pays → sends contentId → receives content
    """
    
    # Core pipeline
    async def execute(self, context: RequestContext, event_queue: EventQueue):
        updater = TaskUpdater(event_queue, context.task_id, context.context_id)
        if not context.current_task:
            updater.submit()
        updater.start_work()

        user_query = context.message.parts[0].root.text.strip()
        remote_url = context.message.parts[1].root.text.strip()
        async with httpx.AsyncClient(timeout=60) as httpx_client:
            client = A2AClient(httpx_client=httpx_client, url=remote_url)
            # 1) Send query
            self._update_status(updater, "Sending query...")
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
            self._update_status(updater, "Waiting for invoice...")
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
            self._update_status(updater, "Paying contract...")
            txh = await asyncio.to_thread(self._pay_contract, contract, content_id, price_wei)
            await asyncio.to_thread(w3.eth.wait_for_transaction_receipt, txh)

            # 3) Send contentId to owner
            self._update_status(updater, "Sending contentId...")
            resp2 = await client.send_message(
                SendMessageRequest(
                    id=str(uuid4()),
                    params=MessageSendParams(
                        message=Message(
                            contextId=context.context_id,
                            taskId=task.id,  # continue same task
                            role="user",
                            messageId=str(uuid4()),
                            parts=[
                                Part(TextPart(text=content_id)),
                                Part(TextPart(text=acct.address)),
                            ]
                        )
                    )
                )
            )

            # 4) Poll until completed
            self._update_status(updater, "Waiting for generated content...")
            t2 = resp2.root.result
            # t2 = resp.root.result
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
                logger.debug(f"Task completed")
            else:
                self._update_fail(updater, "Owner agent failed: "+t2.status.message.parts[0].root.text)
    
    # Helper functions
    def _pay_contract(self, contract, content_id: str, value: int):
        nonce = w3.eth.get_transaction_count(acct.address)
        txn = contract.functions.makePayment(Web3.keccak(text=content_id)).build_transaction({
            "from": acct.address,
            "value": value,
            "gas": 100000,
            "gasPrice": w3.eth.gas_price,
            "nonce": nonce,
            "chainId": w3.eth.chain_id,
        })
        signed = acct.sign_transaction(txn)
        return w3.eth.send_raw_transaction(signed.raw_transaction)
    
    def _update_status(self, updater: TaskUpdater, msg: str):
        updater.update_status(TaskState.working, message=self._msg(updater, msg))

    def _update_fail(self, updater: TaskUpdater, msg: str):
        updater.update_status(TaskState.failed, message=self._msg(updater, msg))

    def _msg(self, updater: TaskUpdater, txt: str):
        logger.debug(txt)
        return updater.new_agent_message([Part(TextPart(text=txt))])
    
    async def cancel(self, context: RequestContext, event_queue: EventQueue):
        raise ServerError(error=UnsupportedOperationError())