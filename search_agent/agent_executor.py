import arxiv
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.utils import new_agent_text_message

class ArxivSearchAgent:
    """Arxiv Search Agent."""

    async def invoke(self, query, max_results = 10) -> str:
        if max_results > 10:
            max_results = 10

        search = arxiv.Search(
            query = query, # 아카이브에서 검색할 논문의 주제
            max_results = max_results, # 최대 10개 논문 검색
            sort_by = arxiv.SortCriterion.Relevance # 관련있는 논문만 검색
        )

        paper_titles = []
        for result in search.results():
            paper_titles.append({
                "title": result.title,
                "authors": [author.name for author in result.authors],
                # "summary": result.summary,
                "url": result.entry_id
            })

        return paper_titles

class ArxivSearchAgentExecutor(AgentExecutor):
    """Test AgentProxy Implementation."""

    def __init__(self):
        self.agent = ArxivSearchAgent()
    
    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        result = await self.agent.invoke()
        event_queue.enqueue_event(new_agent_text_message(result))
    
    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise Exception('cancel not supported')