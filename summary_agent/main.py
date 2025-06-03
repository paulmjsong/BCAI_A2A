import os
import openai  # OpenAI API 라이브러리 (pip install openai)
from a2a_sdk import A2AServer, AgentSkill

# OpenAI API 키 설정 - 실제 운영 시에는 환경변수에 API 키를 저장해 두는 것을 권장
openai.api_key = os.getenv("OPENAI_API_KEY")  # 또는 openai.api_key = "sk-..." 

# 1. 에이전트 스킬 함수 정의
def summarize_text(task):
    """입력된 텍스트(논문 초록/본문)를 GPT-4 모델을 통해 요약하여 반환"""
    original_text = task.input.text  # 입력으로 받은 원본 텍스트
    # GPT-4 모델에 요약 요청 (ChatCompletion API 사용)
    messages = [
        {"role": "system", "content": "당신은 과학 논문 요약 도우미입니다. 사용자에게 논문의 간략한 요약을 제공합니다."},
        {"role": "user", "content": f"논문 내용을 요약해줘:\n\"\"\"\n{original_text}\n\"\"\""}
    ]
    response = openai.ChatCompletion.create(model="gpt-4", messages=messages, max_tokens=500)
    summary = response['choices'][0]['message']['content'].strip()
    return summary

# 2. 스킬 메타데이터 설정
summarize_skill = AgentSkill(
    id="summarize_text",
    name="텍스트 요약",
    description="긴 텍스트(논문 등)를 요약하여 핵심만 반환합니다 (GPT-4 사용)",
    func=summarize_text,
    input_modes=["text/plain"],
    output_modes=["text/plain"]
)

# 3. A2A 에이전트 서버 생성
agent = A2AServer(
    name="SummarizerAgent",
    description="GPT-4 논문 요약 에이전트",
    version="1.0.0",
    skills=[summarize_skill]
)

# 4. 에이전트 서버 실행 (기본 localhost:8001)
PORT = int(os.getenv("PORT", "8001"))
agent.run(host="0.0.0.0", port=PORT)
