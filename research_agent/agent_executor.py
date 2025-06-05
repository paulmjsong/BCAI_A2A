from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.utils import new_agent_text_message
from agent import ResearchAgent


class RearchAgentExecutor(AgentExecutor):
    """Agent Executor for Research Agent"""

    def __init__(self):
        self._agent = ResearchAgent()
    
    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        query = context.get_user_input()
        result = await self._agent.invoke(query)
        event_queue.enqueue_event(new_agent_text_message(result))
    
    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise Exception('cancel not supported')