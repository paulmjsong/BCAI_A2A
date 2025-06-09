import click
import logging
import uvicorn

from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentSkill
from agent_executor import BillingAgentExecutor


logging.basicConfig()

@click.command()
@click.option('--host', default='localhost')
@click.option('--port', default=10001)
@click.option(
    '--research-agent', 'research_agent', default='http://localhost:10002'
)

def main(host, port, research_agent):
    # 1. 스킬 메타데이터 설정
    skill = AgentSkill(
        id="manage_contract",
        name="Manage Contract",
        description="Manage smart contract between user and owner",
        tags = ["billing", "contract", "worldland"],
        input_modes=["text/plain"],
        output_modes=["text/plain"]
    )
    # 2. A2A 에이전트 서버 생성
    agent_card = AgentCard(
        name="BillingAgent",
        description="Agent that calls on remote agent for content generation and ensures payment from its users",
        url=f'http://{host}:{port}/',
        version="1.0.0",
        defaultInputModes=['text'],
        defaultOutputModes=['text'],
        capabilities=AgentCapabilities(streaming=True),
        skills=[skill]
    )
    # 3. 에이전트 서버 실행
    request_handler = DefaultRequestHandler(
        agent_executor=BillingAgentExecutor(research_agent),
        task_store=InMemoryTaskStore(),
    )
    server = A2AStarletteApplication(
        agent_card=agent_card,
        http_handler=request_handler
    )
    uvicorn.run(server.build(), host=host, port=port)


if __name__ == '__main__':
    main()