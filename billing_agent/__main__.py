import click
import uvicorn
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentSkill
from agent_executor import BillingAgentExecutor


@click.command()
@click.option('--host', default='localhost')
@click.option('--port', default=10002)

def main(host, port):
    # 1. 스킬 메타데이터 설정
    skill = AgentSkill(
        id="billing",
        name="Billing",
        description="arXiv의 관련 학술 논문을 바탕으로 연구 동향 분석합니다",
        input_modes=["text/plain"],
        output_modes=["text/plain"]
    )
    # 2. A2A 에이전트 서버 생성
    agent_card = AgentCard(
        name="BillingAgent",
        description="Agent that bills users based on their usage of arXiv papers",
        url=f'http://{host}:{port}/',
        version="1.0.0",
        defaultInputModes=['text'],
        defaultOutputModes=['text'],
        capabilities=AgentCapabilities(streaming=True),
        skills=[skill]
    )
    # 3. 에이전트 서버 실행
    request_handler = DefaultRequestHandler(
        agent_executor=BillingAgentExecutor(),
        task_store=InMemoryTaskStore(),
    )
    server = A2AStarletteApplication(
        agent_card=agent_card,
        http_handler=request_handler
    )
    uvicorn.run(server.build(), host=host, port=port)


if __name__ == '__main__':
    main()