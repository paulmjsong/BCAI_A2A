import arxiv, logging
from typing import Dict, List

from google.adk.agents.llm_agent import LlmAgent, RunConfig
from google.adk.artifacts import InMemoryArtifactService
from google.adk.events import Event
from google.adk.memory.in_memory_memory_service import InMemoryMemoryService
from google.adk.runners import Runner
from google.adk.sessions import Session, InMemorySessionService
from google.genai import types

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events.event_queue import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import (
    AgentCard,
    TaskState, UnsupportedOperationError,
)
from a2a.utils.errors import ServerError

import utils  # A2A<->GenAI conversion helpers


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

MAX_RESULTS = 10


# ────────────────── arXiv search tool ──────────────────
def search_papers(query, max_results=MAX_RESULTS) -> List[Dict]:
    if not query.strip():
        raise ValueError("Query must be non-empty")
    max_results = min(max_results, MAX_RESULTS)

    search = arxiv.Search(
        query = query.strip(),
        max_results = max_results,
        sort_by = arxiv.SortCriterion.Relevance
    )
    paper_list = []
    for result in search.results():
        paper_list.append({
            "title": result.title,
            "summary": result.summary,
            "authors": [author.name for author in result.authors],
            "categories": result.categories,
            "published": result.published.strftime('%Y-%m-%d'),
            "url": result.id
        })
    return paper_list


# ────────────────── build LLM agent ──────────────────
def build_llm_agent() -> LlmAgent:
    prompt = """
You are a research-trend analyst AI.

• Use the `search_papers` tool to fetch up to 10 recent, relevant arXiv papers.
• For each paper, write a concise (2-3 sentence) English summary of the abstract.
• After listing the papers, add a **“Recent Trend Analysis”** section that synthesizes key methods, directions, or gaps you observe, citing specific paper titles or authors where useful.
• Output format (Markdown):

1. **Title** (Authors, YYYY-MM-DD)  
   *Categories:* cs.AI, cs.CL  
   *Summary:* …

2. …

## Recent Trend Analysis
- …

Keep the analysis clear, avoid jargon where possible, and write entirely in **English**.
"""
    return LlmAgent(
        model='gemini-2.5-flash-preview-05-20',
        name='research_agent',
        description=(
            "Analyzes arXiv papers and produces Korean trend summaries"
        ),
        instruction=prompt,
        tools=[search_papers],
    )


# ────────────────── executor ──────────────────
class ResearchAgentExecutor(AgentExecutor):
    """Agent Executor for Research Agent"""

    # Initialization
    def __init__(self, agent_card: AgentCard):
        self.card = agent_card
        self.runner = Runner(
            app_name=agent_card.name,
            agent=build_llm_agent(),
            artifact_service=InMemoryArtifactService(),
            session_service=InMemorySessionService(),
            memory_service=InMemoryMemoryService(),
        )
    
    # Core pipeline
    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        updater = TaskUpdater(event_queue, context.task_id, context.context_id)
        if not context.current_task:
            updater.submit()
        updater.start_work()
        
        user_content = types.UserContent(
            parts=utils.convert_a2a_parts_to_genai(context.message.parts)
        )
        await self._process(user_content, context, updater)
    
    async def _process_request(self, user_msg: types.UserContent, context: RequestContext, updater: TaskUpdater):
        session = await self._ensure_session(context)
        async for event in self.runner.run_async(
            session_id=session.id, 
            # user_id=session.user_id,
            new_message=user_msg,
            run_config=RunConfig(event, updater)
        ):
            await self._handle_event(event, updater)
    
    async def _handle_event(self, event: Event, updater: TaskUpdater):
            if event.is_final_response():
                parts = utils.convert_genai_parts_to_a2a(event.content.parts)
                updater.add_artifact(parts)
                updater.complete()
                return
            if not event.get_function_calls():
                updater.update_status(
                    TaskState.working,
                    message=updater.new_agent_message(
                        utils.convert_genai_parts_to_a2a(event.content.parts),
                    ),
                )
    
    # Helper functions
    async def _ensure_session(self, context: RequestContext) -> Session:
        session = await self.runner.session_service.get_session(
            app_name=self.runner.app_name, 
            session_id=context.context_id,
        ) or await self.runner.session_service.create_session(
            app_name=self.runner.app_name, 
            session_id=context.context_id,
        )
        return session
    
    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise ServerError(error=UnsupportedOperationError())