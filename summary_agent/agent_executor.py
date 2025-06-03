import json

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import DataPart, Part, Task, TaskState, TextPart, UnsupportedOperationError
from a2a.utils import new_agent_parts_message, new_agent_text_message, new_task
from a2a.utils.errors import ServerError
from agent import SummaryAgent


class SummaryAgentExecutor(AgentExecutor):
    """Summary Agent Executor"""

    def __init__(self):
        self.agent = SummaryAgent()

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        papers = context.get_user_input()  # TODO
        task = context.current_task

        # This agent always produces Task objects. If this request does
        # not have current task, create a new one and use it.
        if not task:
            task = new_task(context.message)
            event_queue.enqueue_event(task)
        updater = TaskUpdater(event_queue, task.id, task.contextId)
        # invoke the underlying agent, using streaming results. The streams
        # now are update events.
        async for item in self.agent.stream(papers, task.contextId):
            is_task_complete = item['is_task_complete']
            artifacts = None
            if not is_task_complete:
                updater.update_status(
                    TaskState.working,
                    new_agent_text_message(
                        item['updates'], task.contextId, task.id
                    ),
                )
                continue
            # If the response is a dictionary, assume its a form
            if isinstance(item['content'], dict):
                # Verify it is a valid form
                if (
                    'response' in item['content']
                    and 'result' in item['content']['response']
                ):
                    data = json.loads(item['content']['response']['result'])
                    updater.update_status(
                        TaskState.input_required,
                        new_agent_parts_message(
                            [Part(root=DataPart(data=data))],
                            task.contextId,
                            task.id,
                        ),
                        final=True,
                    )
                    continue
                else:
                    updater.update_status(
                        TaskState.failed,
                        new_agent_text_message(
                            'Reaching an unexpected state',
                            task.contextId,
                            task.id,
                        ),
                        final=True,
                    )
                    break
            else:
                # Emit the appropriate events
                updater.add_artifact(
                    [Part(root=TextPart(text=item['content']))], name='form'
                )
                updater.complete()
                break

    async def cancel(self, request: RequestContext, event_queue: EventQueue) -> Task | None:
        raise ServerError(error=UnsupportedOperationError())