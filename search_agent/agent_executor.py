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

        # 검색한 논문들의 제목과 저자, pdf url 링크를 리스트에 딕셔너리 형태로 저장
        paper_titles = []
        for result in search.results():
            paper_titles.append({
                "title": result.title,
                "authors": [author.name for author in result.authors],
                "url": result.entry_id
            })

        return paper_titles

# 아카이브 검색 에이전트 실행 class
class ArxivSearchAgentExecutor(AgentExecutor):
    """Test AgentProxy Implementation."""

    def __init__(self):
        self.agent = ArxivSearchAgent()
    
    # 에이전트가 호출될 때 실행되는 코드
    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        result = await self.agent.invoke()
        event_queue.enqueue_event(new_agent_text_message(result))
    
    # 에러 핸들링: 에이전트 실행에 오류가 있는 경우
    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise Exception('cancel not supported')