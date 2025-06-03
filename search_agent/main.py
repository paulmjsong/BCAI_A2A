import uvicorn
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentSkill
from agent_executor import ArxivSearchAgentExecutor

# 2. 스킬 메타데이터 설정 (에이전트 카드에 표시될 내용)
skill = AgentSkill(
    id="search_arxiv",
    name="ArXiv 논문 검색",
    description="키워드로 arXiv에서 관련 학술 논문을 검색합니다",
    # 지원 입출력 형태 명시 (텍스트 입력 -> JSON 출력)
    input_modes=["text/plain"],
    output_modes=["application/json"]
)

# 3. A2A 에이전트 서버 생성
public_agent_card = AgentCard(
    name="ArxivSearchAgent",
    description="ArXiv 논문 검색 에이전트",
    version="1.0.0",
    skills=[skill]
)
# public_agent_card = AgentCard(
#     name='Arxiv Search Agent',
#     description='ArXiv 논문 검색 에이전트',
#     url='http://localhost:9999/',
#     version='1.0.0',
#     defaultInputModes=['text'],
#     defaultOutputModes=['text'],
#     capabilities=AgentCapabilities(streaming=True),
#     skills=[skill],
#     supportsAuthenticatedExtendedCard=True,
# )

# 4. 에이전트 서버 실행
request_handler = DefaultRequestHandler(
    agent_executor=ArxivSearchAgentExecutor(),
    task_store=InMemoryTaskStore(),
)

server = A2AStarletteApplication(
    agent_card=public_agent_card,
    http_handler=request_handler
)

uvicorn.run(server.build(), host='0.0.0.0', port=9999)