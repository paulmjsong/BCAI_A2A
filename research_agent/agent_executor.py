import arxiv, logging, os
import google.generativeai as genai
from dotenv import load_dotenv

from google.adk.agents.llm_agent import LlmAgent
from google.adk.artifacts import InMemoryArtifactService
from google.adk.events import Event
from google.adk.memory.in_memory_memory_service import InMemoryMemoryService
from google.adk.runners import Runner, RunConfig
from google.adk.sessions import InMemorySessionService
from google.genai import types

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events.event_queue import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import (
    AgentCard, TaskState, UnsupportedOperationError,
)
from a2a.utils.errors import ServerError

# ----- added -----
import utils  # A2A<->GenAI conversion helpers
# ----- end of added -----

# ────────────────── genai config ──────────────────
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
genai.configure(api_key=GOOGLE_API_KEY)

MAX_RESULTS = 10

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


# ────────────────── arXiv search tool ──────────────────
def search_papers(query: str, max_results: int) -> list:
    """
    max_results should be 1-10. If caller passes >10 we clamp internally.
    """
    if not query.strip():
        raise ValueError("Query must be non-empty")
    
    logger.debug(f"Searching arXiv with query: \"{query}\"...")
    max_results = min(max_results, MAX_RESULTS)
    search = arxiv.Search(
        query = query.strip(),
        max_results = max_results,
        sort_by = arxiv.SortCriterion.Relevance
    )
    papers = []
    for result in search.results():
        papers.append({
            "title": result.title,
            "summary": result.summary,
            "authors": [author.name for author in result.authors],
            "categories": result.categories,
            "published": result.published.strftime('%Y-%m-%d'),
            "url": result.entry_id, 
        })
    logger.debug(f"Retrieved {len(papers)} papers:")
    for i, paper in enumerate(papers):
        logger.debug(f"{i+1:02} {paper['title']}")
    return papers


# ────────────────── build LLM agent ──────────────────
def build_llm_agent() -> LlmAgent:
    prompt = """
You are a research-trend analyst AI specialized in tracking cutting-edge topics in machine learning, AI, NLP, and related fields.

🔍 Task Instructions:
Step 1: Generate a concise and effective search term based on the user’s query.
This term should reflect the core topic or method they’re interested in and will be used with the search_papers tool to fetch relevant arXiv papers.

Step 2: Use the search_papers tool with the generated term to retrieve up to 10 recent (within the past year), high-relevance papers from arXiv.

Step 3: For each paper:
• Include the title, author(s), and publication date.
• Specify the arXiv categories.
• Write a concise, 2-3 sentence summary of the abstract in plain English. Highlight key methods, contributions, or findings.

Step 4: After listing the papers, write a ## Recent Trend Analysis section that:
• Synthesizes emerging methods, directions, applications, or open challenges.
• References specific paper titles or authors where relevant.
• Avoids jargon and maintains clarity for a broad research-oriented audience.

📄 **Output Format (Markdown)**
**Search Term:** *<automatically inferred search term from user query>*

## Recent Papers
1. **<Title>** (<Authors>, YYYY-MM-DD)  
   *Categories:* <arXiv categories>  
   *Summary:* <Plain English summary of the abstract.>

...

## Recent Trend Analysis
- <Key observations with references to papers>

🧠 **Additional Guidance**
If papers are too similar, prioritize diversity of subtopics or techniques.

Emphasize novelty, practicality, or conceptual contributions.

Avoid copying text from abstracts verbatim.
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
    """
    Agent Executor for Research Agent

    Receives query → fetches papers → generates content → sends content
    """

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
    async def execute(self, context: RequestContext, event_queue: EventQueue):
        updater = TaskUpdater(event_queue, context.task_id, context.context_id)
        if not context.current_task:
            updater.submit()
        updater.start_work()
        
        user_query = types.UserContent(
            parts=utils.convert_a2a_parts_to_genai(context.message.parts)
            # parts=context.message.parts
        )
        logger.debug("Processing request...")

        await self._process_request(user_query, context, updater)
        logger.debug("Task completed")
    
    async def _process_request(self, user_query: types.UserContent, context: RequestContext, updater: TaskUpdater):
        session = await self._get_session(context)
        async for event in self.runner.run_async(
            session_id=session.id, 
            user_id=session.user_id, 
            new_message=user_query, 
            run_config=RunConfig(), 
        ):
            await self._handle_event(event, updater)
    
    async def _handle_event(self, event: Event, updater: TaskUpdater):
        if event.is_final_response():
            # switch comments
            parts = utils.convert_genai_parts_to_a2a(event.content.parts)
            # parts = event.content.parts
            updater.add_artifact(parts)
            updater.complete()
            return
        if not event.get_function_calls():
            updater.update_status(
                TaskState.working,
                message=updater.new_agent_message(
                    # switch comments
                    utils.convert_genai_parts_to_a2a(event.content.parts),
                    # event.content.parts,
                ),
            )
    
    # Helper functions
    async def _get_session(self, context: RequestContext):
        session = await self.runner.session_service.get_session(
            app_name=self.runner.app_name, 
            user_id="anonymous", 
            session_id=context.context_id,
        ) or await self.runner.session_service.create_session(
            app_name=self.runner.app_name, 
            user_id="anonymous", 
            session_id=context.context_id,
        )
        return session
    
    async def cancel(self, context: RequestContext, event_queue: EventQueue):
        raise ServerError(error=UnsupportedOperationError())