import gradio as gr
import asyncio, httpx, json, logging, os, hashlib, html, threading, time
from collections import OrderedDict
from datetime import datetime
from uuid import uuid4

from a2a.client import A2AClient
from a2a.types import (
    Message, MessageSendParams, SendMessageRequest, TaskQueryParams, 
    GetTaskRequest, Part, TextPart, TaskState, 
)


MY_AGENT_URL = "http://localhost:10000"         # Set to user agent's actual URL
REMOTE_AGENT_URLS = {
    "Research Agent": "http://localhost:10001", # Set to remote agent's actual URL
    "(Preparing)": "",                          # Placeholder for future agents
}
POLL_DELAY = 3

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# ────────────────── session management ──────────────────
MAX_SESSIONS = 100
sessions = OrderedDict()
session_lock = threading.Lock()

def get_session_id(request: gr.Request):
    raw_id = request.client.host + str(request.headers.get("user-agent"))
    return hashlib.sha256(raw_id.encode()).hexdigest()

def init_session(session_id: str):
    sessions[session_id] = {
        "chat_history": [],
        # "log_history": [],
    }

def reset_session(request: gr.Request):
    """대화 및 파일 업로드 내역 삭제"""
    session_id = get_session_id(request)
    with session_lock:
        init_session(session_id)
        sessions.move_to_end(session_id)
        print(f"♻️ Session {session_id[:8]}... reset.")
    return "", []


# ────────────────── run client ──────────────────
async def run_client(query, remote_url, my_url=MY_AGENT_URL):
    """
    Connects to the UserAgent, sends a query, and polls for the result.
    """
    try:
        async with httpx.AsyncClient(timeout=120) as httpx_client:
            client = A2AClient(httpx_client=httpx_client, url=my_url)
            # 1. Send the initial query to the UserAgent
            logger.info(f"Sending query: '{query}' to {my_url}")
            send_request = SendMessageRequest(
                id=str(uuid4()),
                params=MessageSendParams(
                    message=Message(
                        role="user",
                        messageId=str(uuid4()),
                        parts=[
                            Part(TextPart(text=query)),
                            Part(TextPart(text=remote_url)),
                        ]
                    )
                )
            )
            
            resp = await client.send_message(send_request)

            if hasattr(resp.root, "error"):
                error_message = resp.root.error.message
                logger.error(error_message)
                return error_message

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
                    error_message = get_task_resp.root.error.message
                    logger.error(error_message)
                    return error_message

                task = get_task_resp.root.result
                
                if task.status.state == TaskState.completed:
                    # The final result is stored in the task's artifacts
                    result_text = task.artifacts[0].parts[0].root.text
                    logger.info("Task completed!")
                    return result_text
                if task.status.state == TaskState.failed:
                    error_message = task.status.message.parts[0].root.text
                    logger.error(error_message)
                    return error_message
                # Display the intermediate status message from the agent
                if task.status.message:
                    status_update = task.status.message.parts[0].root.text
                    logger.info(f"Status update: {status_update}")
                else:
                    logger.info("Task is still in progress...")

    except Exception as e:
        logger.error(f"An error occurred while connecting to the agent at {my_url}. Is it running?")
        logger.error(f"Details: {e}")
        return f"Exception: {str(e)}"


# ────────────────── handle query ──────────────────
async def handle_query(query, remote_url, request: gr.Request,):
    session_id = get_session_id(request)
    # Ensure session-safe access
    with session_lock:
        if session_id not in sessions:
            if len(sessions) >= MAX_SESSIONS:
                evicted_id, _ = sessions.popitem(last=False)
                print(f"🧹 Removed LRU session: {evicted_id[:8]}...")
            init_session(session_id)
            print(f"✅ New session created: {session_id[:8]}... | Total sessions: {len(sessions)}")
        session = sessions[session_id]
        sessions.move_to_end(session_id)
    
    chat_history = session["chat_history"]
    # log_history = session["log_history"]
    if query == "" or remote_url == "":
        return chat_history
    
    start_time = time.time()                                         # ⏱️ TIMER
    
    response = await run_client(query, remote_url)

    response = html.escape(response)
    chat_history.append({"role": "user", "content": query})
    chat_history.append({"role": "assistant", "content": response})
    save_history(chat_history, session_id)
   
    end_time = time.time()                                           # ⏱️ TIMER
    elapsed_time = end_time - start_time                             # ⏱️ TIMER
    print(f"Responded to user query in {elapsed_time:.2f} seconds")  # ⏱️ TIMER
    
    return chat_history


# ────────────────── save history ──────────────────
def save_history(history, session_id):
    """대화 기록(history)을 JSON 파일로 저장"""
    folder = "./chat_logs"
    os.makedirs(folder, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d")
    filename = os.path.join(folder, f"{timestamp}_{session_id}.json")
    counter = 1
    while os.path.exists(filename):
        filename = os.path.join(folder, f"{timestamp}_{session_id}_{counter}.json")
        counter += 1
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


# ────────────────── main ──────────────────
css = """
div {
    flex-wrap: nowrap !important;
}
.responsive-height {
    height: 85vh !important;
}
.fill-height {
    height: 100% !important;
    flex-wrap: nowrap !important;
}
.extend-height {
    min-height: 260px !important;
    flex: 1 !important;
    overflow: hidden !important;
}
#agent_column {
    min_width: 100px !important;
    background: var(--block-background) !important;
    border: var(--block-border-width) solid var(--block-border-color) !important;
    border-radius: var(--block-radius) !important;
    box-shadow: var(--block-shadow) !important;
    padding: var(--block-padding) !important;
}
button {
    min-width: 0 !important;
}
.btn_selected {
    background-color: var(--button-primary-background-fill) !important;
    color: var(--button-primary-text-color) !important;
}
footer {
    display: none !important;
}
"""

js = """
window.highlightButton = function(selected_id) {
    let selectedButton = document.getElementById(selected_id);
    if (selectedButton) {
        let buttons = document.querySelectorAll('button');
        buttons.forEach(btn => btn.classList.remove('btn_selected'));
        selectedButton.classList.add('btn_selected');
    }
}
"""

with gr.Blocks(title="My AI Client", css=css, js=js, fill_height=True) as demo:
    gr.Markdown("<h1>My AI Client</h1>")
    with gr.Row(elem_classes=["responsive-height"]):
        # Agent Selection Column
        with gr.Column(elem_classes=["fill-height"], scale=1):
            with gr.Column(elem_classes=["extend-height"], elem_id="agent_column"):
                gr.Markdown("<h3>Agents for Hire</h3>")
                agent_btns = [gr.Button(agent, variant="secondary", elem_id=f"agent_btn{i}")
                            for i, agent in enumerate(REMOTE_AGENT_URLS.keys())]
            url_input = gr.Textbox(label="Agent URL", placeholder=f"No agent selected", interactive=False)
            user_input = gr.Textbox(label="User Query", placeholder=f"Enter your query here", lines=4)
            with gr.Row():
                submit_btn = gr.Button("Submit", variant="primary")
                reset_btn = gr.Button("Reset", variant="secondary")
        # Input/Output Column
        with gr.Column(elem_classes=["fill-height"], scale=3):
            chatbot = gr.Chatbot(label="Chatbot", type="messages", elem_classes=["extend-height"])
    # Event listeners
    for i, agent_btn in enumerate(agent_btns):
        agent_btn.click(fn=lambda x=REMOTE_AGENT_URLS[agent_btn.value]: x, inputs=[], outputs=[url_input], 
                        js=f"() => highlightButton('agent_btn{i}')")
    user_input.submit(fn=handle_query, inputs=[user_input, url_input], outputs=[chatbot])
    submit_btn.click(fn=handle_query, inputs=[user_input, url_input], outputs=[chatbot])
    reset_btn.click(fn=reset_session, inputs=[], outputs=[user_input, chatbot])

demo.launch(share=True, favicon_path="")