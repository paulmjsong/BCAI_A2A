import asyncio
import click
import logging
from uuid import uuid4

from a2a.client import A2AClient
from a2a.types import (
    GetTaskRequest,
    Message,
    MessageSendParams,
    Part,
    SendMessageRequest,
    TaskQueryParams,
    TaskState,
    TextPart,
)


POLL_DELAY = 3

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# ────────────────── run client ──────────────────
async def run_client(url: str, query: str):
    """
    Connects to the UserAgent, sends a query, and polls for the result.
    """
    try:
        async with A2AClient(url) as client:
            # 1. Send the initial query to the UserAgent
            logger.info(f"Sending query: '{query}' to {url}")
            send_request = SendMessageRequest(
                id=str(uuid4()),
                params=MessageSendParams(
                    message=Message(
                        role="user",
                        messageId=str(uuid4()),
                        parts=[Part(TextPart(text=query))]
                    )
                )
            )
            
            resp = await client.send_message(send_request)

            if hasattr(resp.root, "error"):
                logger.error(f"Error sending message: {resp.root.error.message}")
                return

            task = resp.root.result
            task_id = task.id
            logger.info(f"Task created successfully. Task ID: {task_id}")

            # 2. Poll the server until the task is complete or fails
            while True:
                await asyncio.sleep(POLL_DELAY)
                
                logger.info(f"Checking status for task {task_id}...")
                get_task_resp = await client.get_task(
                    GetTaskRequest(
                        id=str(uuid4()),
                        params=TaskQueryParams(id=task_id)
                    )
                )

                if hasattr(get_task_resp.root, "error"):
                    logger.error(f"Error getting task status: {get_task_resp.root.error.message}")
                    break

                task = get_task_resp.root.result
                
                if task.status.state == TaskState.completed:
                    logger.info("Task completed!")
                    # The final result is stored in the task's artifacts
                    result_text = task.artifacts[0].parts[0].root.text
                    print("\n✅ Final Result:")
                    print(result_text)
                    break
                elif task.status.state == TaskState.failed:
                    logger.error("Task failed!")
                    error_message = task.status.message.parts[0].root.text
                    print(f"\n❌ Error: {error_message}")
                    break
                else: # TaskState.working
                    # Display the intermediate status message from the agent
                    if task.status.message:
                        status_update = task.status.message.parts[0].root.text
                        logger.info(f"Status update: {status_update}")
                    else:
                        logger.info("Task is still in progress...")

    except Exception as e:
        logger.error(f"An error occurred while connecting to the agent at {url}. Is it running?")
        logger.error(f"Details: {e}")


# ────────────────── main ──────────────────
@click.command()
@click.option('--url', default='http://localhost:10000', help='URL of the UserAgent to connect to.')

def main(url: str):
    """
    A command-line client to interact with the A2A UserAgent.

    QUERY: The question or command you want to send to the agent.
    """
    while(1):
        query = input("Enter research topic:")
        asyncio.run(run_client(url, query))


if __name__ == '__main__':
    main()