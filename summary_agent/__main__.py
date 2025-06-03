import os
import click
import uvicorn

from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentSkill
from agent import ReimbursementAgent
from agent_executor import SummaryAgentExecutor

from dotenv import load_dotenv
load_dotenv()


class MissingAPIKeyError(Exception):
    """Exception for missing API key."""

    pass


@click.command()
@click.option('--host', default='localhost')
@click.option('--port', default=10002)
def main(host, port):
    # 0. API_KEY 확인
    if not os.getenv('GOOGLE_API_KEY'):
        raise MissingAPIKeyError(
            'GOOGLE_API_KEY environment variable not set and GOOGLE_GENAI_USE_VERTEXAI is not TRUE.'
        )
    # 1. 스킬 메타데이터 설정
    skill = AgentSkill(
        id='summarize_papers',
        name='논문 요약',
        description='GPT-4를 사용해 논문의 내용을 요약합니다',
        input_modes=["application/json"],
        output_modes=["text/plain"]
    )
    # 2. A2A 에이전트 서버 생성
    agent_card = AgentCard(
        name='Paper Summary Agent',
        description='논문 요약 에이전트',
        url=f'http://{host}:{port}/',
        version='1.0.0',
        defaultInputModes=['text'],
        defaultOutputModes=['text'],
        capabilities=AgentCapabilities(streaming=True),
        skills=[skill]
    )
    # 3. 에이전트 서버 실행
    request_handler = DefaultRequestHandler(
        agent_executor=SummaryAgentExecutor(),
        task_store=InMemoryTaskStore(),
    )
    server = A2AStarletteApplication(
        agent_card=agent_card, http_handler=request_handler
    )
    uvicorn.run(server.build(), host=host, port=port)


if __name__ == '__main__':
    main()