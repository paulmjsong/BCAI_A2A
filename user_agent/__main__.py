import click
import logging
import uvicorn

from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentSkill
from agent_executor import UserAgentExecutor


logging.basicConfig()

@click.command()
@click.option('--host', default='localhost')
@click.option('--port', default=10000)
@click.option(
    '--owner-agent', 'owner_agent', default='http://localhost:10001'
)

def main(host, port, owner_agent):
    # 1. 스킬 메타데이터 설정
    skill = AgentSkill(
        id="commission_agent",
        name="Commission Agent",
        description="Commission a remote agent over WorldLand",
        tags=["commission", "worldland", "payment"],
        input_modes=["text/plain"],
        output_modes=["text/plain"]
    )
    # 2. A2A 에이전트 서버 생성
    agent_card = AgentCard(
        name="UserAgent",
        description="Agent that allows user to commission a remote agent over WorldLand",
        url=f'http://{host}:{port}/',
        version="1.0.0",
        defaultInputModes=['text'],
        defaultOutputModes=['text'],
        capabilities=AgentCapabilities(streaming=True),
        skills=[skill]
    )
    # 3. 에이전트 서버 실행
    request_handler = DefaultRequestHandler(
        agent_executor=UserAgentExecutor(owner_agent, agent_card),
        task_store=InMemoryTaskStore(),
    )
    server = A2AStarletteApplication(
        agent_card=agent_card,
        http_handler=request_handler
    )
    uvicorn.run(server.build(), host=host, port=port)


if __name__ == '__main__':
    main()