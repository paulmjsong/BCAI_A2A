import arxiv
from google.adk.agents.llm_agent import LlmAgent


def search_arxiv(self, query, max_results = 10) -> str:
    if max_results > 10:
        max_results = 10

    search = arxiv.Search(
        query = query, # 아카이브에서 검색할 논문의 주제
        max_results = max_results, # 최대 10개 논문 검색
        sort_by = arxiv.SortCriterion.Relevance # 관련있는 논문만 검색
    )

    paper_list = []
    for result in search.results():
        paper_list.append({
            "title": result.title,
            "summary": result.summary,
            "authors": [author.name for author in result.authors],
            "published": result.published.strftime('%Y-%m-%d'),
            "url": result.id
        })
    return paper_list


# class ArxivSearchAgent:
#     """Arxiv Search Agent"""

#     def __init__(self):
#         self._user_id = 'remote_agent'
#         self._agent = LlmAgent(
#             model='gemini-2.5-flash-preview-05-20',
#             name='arxiv_search_agent',
#             description="An agent that can search arXiv for research papers related to user's query",
#             instruction=(
#                 "당신은 연구 조교 AI입니다. 사용자에게 주어진 주제와 관련된 여러 학술 논문의 메타데이터(제목, 저자, 출판일, 카테고리, 초록)가 제공될 것입니다. "
#                 "각 논문마다 한국어로 쉽게 이해할 수 있는 요약을 작성하세요. "
#                 "모든 논문의 요약을 마친 후, 해당 주제 분야에서 최근 연구 동향과 발전을 종합 분석하여 '연구 동향 분석'이라는 제목의 섹션으로 제공하세요. "
#                 "응답 형식은 번호가 매겨진 논문 목록과 각 논문의 메타데이터 및 요약, 그리고 마지막에 연구 동향 분석 섹션으로 하세요."
#             )
#         )

#     async def invoke(self, query: str) -> str:
#         # Step 1: Rewrite user's query for better search
#         rephrased = self._agent.run(query)
#         # Step 2: Search arXiv for relevant papers
#         papers = self.search_arxiv(rephrased)
#         return papers


def create_agent():
    return LlmAgent(
        model='gemini-2.5-flash-preview-05-20',
        name='arxiv_search_agent',
        description="An agent that can search arXiv for research papers related to user's query",
        instruction=(
            "You are an agent that can help users discover research papers related to their topic of interest. "
            "Users will request information about a particular research topic. "
            "You must first rephrase the user's query for improved search results, "
            "then use the provided tools to search papers from arXiv and store their metadata into a list."
        ),
        tools=[search_arxiv]
    )


# TODO: check if create_agents works as expected