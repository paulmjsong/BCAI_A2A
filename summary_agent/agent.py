### WORK IN PROGRESS ###

import json
from typing import Any, AsyncIterable, Optional
from google.adk.agents.llm_agent import LlmAgent
from google.adk.artifacts import InMemoryArtifactService
from google.adk.memory.in_memory_memory_service import InMemoryMemoryService
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types


class SummaryAgent:
    """Paper Summary Agent"""
    def __init__(self):
        self._agent = self._build_agent()
        self._user_id = 'remote_agent'
        self._runner = Runner(
            app_name=self._agent.name,
            agent=self._agent,
            artifact_service=InMemoryArtifactService(),
            session_service=InMemorySessionService(),
            memory_service=InMemoryMemoryService(),
        )

    def get_processing_message(self) -> str:
        return '요약 요청을 처리하는 중입니다...'

    def _build_agent(self) -> LlmAgent:
        """Builds the LLM agent for the summary agent."""
        return LlmAgent(
            model='gemini-2.5-flash-preview-05-20',
            name='summary_agent',
            description=(
                '최대 10개의 연구 논문을 입력 받아 한국어로 사람이 이해하기 쉬운 요약문을 생성하는 에이전트'
            ),
            instruction="""
다음은 최대 10개의 연구 논문 전문 텍스트입니다. 각 논문의 핵심 내용을 간결하고 명확하게 한국어로 요약하십시오. 

- 논문별로 구분해서 번호를 붙여 요약해 주세요.
- 요약은 전문적이면서도 사람이 쉽게 이해할 수 있는 문체로 작성해 주세요.
- 필요하면 중요한 결과나 기여도 강조해 주세요.
- 각 논문 내용이 길 경우 핵심만 뽑아 최대 200자 내외로 요약해 주세요.

아래에 입력된 논문 텍스트를 참고하여 요약문을 작성하십시오.
    """)

    async def stream(self, papers, session_id) -> AsyncIterable[dict[str, Any]]:
        # 1. Prepare query with papers
        combined_text = "\n\n".join(
            [f"[논문 {i+1}]\n{paper.strip()}" for i, paper in enumerate(papers)]
        )
        full_query = f"다음은 {len(papers)}개의 연구 논문 전문입니다. 아래 논문들을 읽고, 각각을 한국어로 간결하게 요약해주세요:\n\n{combined_text}"

        # 2. Send query to agent
        session = await self._runner.session_service.get_session(
            app_name=self._agent.name,
            user_id=self._user_id,
            session_id=session_id,
        )
        content = types.Content(
            role='user', parts=[types.Part.from_text(text=full_query)]
        )
        if session is None:
            session = await self._runner.session_service.create_session(
                app_name=self._agent.name,
                user_id=self._user_id,
                state={},
                session_id=session_id,
            )
        async for event in self._runner.run_async(
            user_id=self._user_id, session_id=session.id, new_message=content
        ):
            if event.is_final_response():
                response = ''
                if (
                    event.content
                    and event.content.parts
                    and event.content.parts[0].text
                ):
                    response = '\n'.join(
                        [p.text for p in event.content.parts if p.text]
                    )
                elif (
                    event.content
                    and event.content.parts
                    and any(
                        [
                            True
                            for p in event.content.parts
                            if p.function_response
                        ]
                    )
                ):
                    response = next(
                        p.function_response.model_dump()
                        for p in event.content.parts
                    )
                yield {
                    'is_task_complete': True,
                    'content': response,
                }
            else:
                yield {
                    'is_task_complete': False,
                    'updates': self.get_processing_message(),
                }