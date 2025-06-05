from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.utils import new_agent_text_message
# from agent import ArxivSearchAgent
from agent import create_agent


class ArxivSearchAgentExecutor(AgentExecutor):
    """Agent Executor for Arxiv Search Agent"""

    def __init__(self):
        # self.agent = ArxivSearchAgent()
        self.agent = create_agent()
    
    # 에이전트가 호출될 때 실행되는 코드
    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        query = ""
        result = await self.agent.invoke(query)
        event_queue.enqueue_event(new_agent_text_message(result))
    
    # 에러 핸들링: 에이전트 실행에 오류가 있는 경우
    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise Exception('cancel not supported')


# TODO: receive query from user