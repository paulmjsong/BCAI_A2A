### WORK IN PROGRESS ###

import click
import uvicorn
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentSkill
from agent_executor import UserAgentExecutor
from ...resarch_agent.agent_executor import ResearchAgentExecutor


@click.command()
@click.option('--host', default='localhost')
@click.option('--port', default=10000)
@click.option(
    '--billing-agent', 'billing_agent', default='http://localhost:10003'
)

def main(host, port, billing_agent):
    # 1. 스킬 메타데이터 설정
    skill = AgentSkill(
        id="commission",
        name="Commission",
        description="Commission another agent for research assistance over WorldLand",
        input_modes=["text/plain"],
        output_modes=["text/plain"]
    )
    # 2. A2A 에이전트 서버 생성
    agent_card = AgentCard(
        name="UserAgent",
        description="Agent that helps user commission another agent for research assistance over WorldLand",
        url=f'http://{host}:{port}/',
        version="1.0.0",
        defaultInputModes=['text'],
        defaultOutputModes=['text'],
        capabilities=AgentCapabilities(streaming=True),
        skills=[skill]
    )
    # 3. 에이전트 서버 실행
    request_handler = DefaultRequestHandler(
        agent_executor=UserAgentExecutor(billing_agent),
        task_store=InMemoryTaskStore(),
    )
    server = A2AStarletteApplication(
        agent_card=agent_card,
        http_handler=request_handler
    )
    uvicorn.run(server.build(), host=host, port=port)


if __name__ == '__main__':
    main()


# TODO: create user agent
# TODO: interact with billing agent