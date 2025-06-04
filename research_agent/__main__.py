import click
import uvicorn
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentSkill
from agent_executor import RearchAgentExecutor


@click.command()
@click.option('--host', default='localhost')
@click.option('--port', default=10002)

def main(host, port):
    # 1. 스킬 메타데이터 설정
    skill = AgentSkill(
        id="research_trend_analysis",
        name="Research Trend Analysis",
        description="arXiv의 관련 학술 논문을 바탕으로 연구 동향 분석합니다",
        input_modes=["text/plain"],
        output_modes=["text/plain"]
    )
    # 2. A2A 에이전트 서버 생성
    agent_card = AgentCard(
        name="ResearchAgent",
        description="Agent that analyzes research trends based on relevant arXiv papers",
        url=f'http://{host}:{port}/',
        version="1.0.0",
        defaultInputModes=['text'],
        defaultOutputModes=['text'],
        capabilities=AgentCapabilities(streaming=True),
        skills=[skill]
    )
    # 3. 에이전트 서버 실행
    request_handler = DefaultRequestHandler(
        agent_executor=RearchAgentExecutor(),
        task_store=InMemoryTaskStore(),
    )
    server = A2AStarletteApplication(
        agent_card=agent_card,
        http_handler=request_handler
    )
    uvicorn.run(server.build(), host=host, port=port)


if __name__ == '__main__':
    main()