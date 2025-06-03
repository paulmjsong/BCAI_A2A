import click
import uvicorn
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentSkill
from agent_executor import ArxivSearchAgentExecutor


@click.command()
@click.option('--host', default='localhost')
@click.option('--port', default=10002)
def main(host, port):
    # 1. 스킬 메타데이터 설정
    skill = AgentSkill(
        id="search_arxiv",
        name="ArXiv 논문 검색",
        description="키워드로 arXiv에서 관련 학술 논문을 검색합니다",
        input_modes=["text/plain"],
        output_modes=["application/json"]
    )
    # 2. A2A 에이전트 서버 생성
    agent_card = AgentCard(
        name="ArxivSearchAgent",
        description="ArXiv 논문 검색 에이전트",
        url=f'http://{host}:{port}/',
        version="1.0.0",
        defaultInputModes=['text'],
        defaultOutputModes=['text'],
        capabilities=AgentCapabilities(streaming=True),
        skills=[skill]
    )
    # 3. 에이전트 서버 실행
    request_handler = DefaultRequestHandler(
        agent_executor=ArxivSearchAgentExecutor(),
        task_store=InMemoryTaskStore(),
    )
    server = A2AStarletteApplication(
        agent_card=agent_card,
        http_handler=request_handler
    )
    uvicorn.run(server.build(), host=host, port=port)


if __name__ == '__main__':
    main()