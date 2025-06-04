import arxiv
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.utils import new_agent_text_message
from google.adk.agents.llm_agent import LlmAgent


# def search_papers(query: str, max_results: int = 10) -> list[dict]:
#     # Search for up to 10 arXiv papers related to user's query
#     if max_results > 10:
#         max_results = 10
#     search = arxiv.Search(
#         query = query,
#         max_results = max_results,
#         sort_by = arxiv.SortCriterion.Relevance
#     )
#     paper_list = []
#     for result in search.results():
#         paper_list.append({
#             "title": result.title,
#             "summary": result.summary,
#             "authors": [author.name for author in result.authors],
#             "published": result.published.strftime('%Y-%m-%d'),
#             "url": result.id
#         })
#     return paper_list


class BillingAgent:
    """Agent that bills users based on their usage of arXiv papers"""

    def __init__(self):
        self._user_id = 'remote_agent'
        self._agent = LlmAgent(
            model='gemini-2.5-flash-preview-05-20',
            name='research_agent',
            description=(
                "Agent that analyzes research trends based on relevant arXiv papers"
            ),
            instruction=(
                "당신은 연구 조교 AI입니다. 사용자에게 주어진 주제와 관련된 여러 학술 논문의 메타데이터(제목, 저자, 출판일, 카테고리, 초록)가 제공될 것입니다. "
                "각 논문마다 한국어로 쉽게 이해할 수 있는 요약을 작성하세요. "
                "모든 논문의 요약을 마친 후, 해당 주제 분야에서 최근 연구 동향과 발전을 종합 분석하여 '연구 동향 분석'이라는 제목의 섹션으로 제공하세요. "
                "응답 형식은 번호가 매겨진 논문 목록과 각 논문의 메타데이터 및 요약, 그리고 마지막에 연구 동향 분석 섹션으로 하세요."
            ),
        )

    async def invoke(self, query: str) -> str:
        # Step 1: Search for relevant papers on arXiv
        papers = self.search_papers(query)
        # Step 2: Generate summaries and trend analysis in Korean using the LLM
        result = self.llm_agent.run(papers)
        return result


class RearchAgentExecutor(AgentExecutor):
    """Agent Executor for Billing Agent"""

    def __init__(self):
        self.agent = BillingAgent()
    
    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        result = await self.agent.invoke()
        event_queue.enqueue_event(new_agent_text_message(result))
    
    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise Exception('cancel not supported')