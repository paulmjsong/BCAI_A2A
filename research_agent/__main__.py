import click
import logging
import uvicorn

from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentSkill
from agent_executor import ResearchAgentExecutor


logging.basicConfig()

@click.command()
@click.option('--host', default='localhost')
@click.option('--port', default=10002)

def main(host, port):
    # 1. 스킬 메타데이터 설정
    skill = AgentSkill(
        id="analyze_research",
        name="Analyze Research",
        description="Analyze research trend based on arXiv papers relevant to user's query",
        tags = ["research", "arxiv", "trend"],
        input_modes=["text/plain"],
        output_modes=["text/plain"]
    )
    # 2. A2A 에이전트 서버 생성
    agent_card = AgentCard(
        name="ResearchAgent",
        description="Agent that analyzes research trends based on arXiv papers relevant to user's query",
        url=f'http://{host}:{port}/',
        version="1.0.0",
        defaultInputModes=['text'],
        defaultOutputModes=['text'],
        capabilities=AgentCapabilities(streaming=True),
        skills=[skill]
    )
    # 3. 에이전트 서버 실행
    request_handler = DefaultRequestHandler(
        agent_executor=ResearchAgentExecutor(agent_card),
        task_store=InMemoryTaskStore(),
    )
    server = A2AStarletteApplication(
        agent_card=agent_card,
        http_handler=request_handler
    )
    uvicorn.run(server.build(), host=host, port=port)


if __name__ == '__main__':
    main()