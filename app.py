# 📋 app.py · [실습 3-3] 폴리봇 웹앱 ② — 사이드바 : 기억할 턴 수 · 새 대화 (보낼 때마다 요청 1번)
import streamlit as st
from google import genai
from google.genai import types

MODEL_NAME = "gemini-3.5-flash-lite"
SYSTEM_PROMPT = """너는 '폴리봇'이야. 인공지능소프트웨어과 1학년의 파이썬 · AI 공부 도우미 챗봇이야.
규칙 1. 존댓말로 3문장 이내로 답한다.
규칙 2. 파이썬 · AI 공부와 관련 없는 질문에는 '저는 공부 도우미라서 그 질문에는 답하기 어려워요.' 라고 답한다.
규칙 3. 학교 일정처럼 모르는 내용은 지어내지 말고 학과 사무실에 문의하라고 안내한다.
규칙 4. 이름 · 학번 · 전화번호 같은 개인정보를 묻지 않는다."""


@st.cache_resource
def get_client():
    """Gemini client 를 만들어 돌려준다 (키는 st.secrets 에서)"""
    return genai.Client(
        api_key=st.secrets["GEMINI_API_KEY"],
        http_options=types.HttpOptions(
            timeout=120_000,
            retry_options=types.HttpRetryOptions(http_status_codes=[500, 503]),
        ),
    )


def explain_error(error):
    """오류 번호를 보고 할 일을 한글로 알려 준다"""
    code = getattr(error, "status_code", None)
    if code == 429:
        return "⏳ 무료 한도를 넘음 — 1분 기다렸다 다시 보내 보세요."
    if code in (400, 403):
        return "❌ 키 문제 — 키를 다시 복사했는지, AI Studio 에서 키 상태를 확인하세요."
    if code == 402:
        return "💳 결제가 연결된 프로젝트의 키임 — 새 프로젝트로 키를 다시 만드세요."
    return f"❌ 오류 ({code}) : {error}"


def step_text(step):
    """기록의 단계 하나에서 글만 꺼낸다"""
    content = step.get("content")
    if isinstance(content, str):
        return content
    return "".join(part.get("text", "") for part in content or [] if part.get("type") == "text")


def trim_history(history, max_turns):
    """최근 max_turns 턴만 남긴 새 리스트를 돌려준다 (11주차와 같음)"""
    user_positions = [index for index, step in enumerate(history) if step["type"] == "user_input"]
    if len(user_positions) <= max_turns:
        return history
    return history[user_positions[-max_turns]:]


try:
    client = get_client()
except Exception:
    st.error("🔑 GEMINI_API_KEY 를 찾지 못했습니다 — Manage app → ⋮ → Settings → Secrets 칸을 확인하세요.")
    st.stop()

# ---------- 기록 보관함 준비 + 지금까지의 대화 그리기 ----------
if "history" not in st.session_state:       # 이 탭에서 처음 열었을 때만 빈 기록을 만듦
    st.session_state.history = []

st.title("🤖 폴리봇")
st.caption("인공지능소프트웨어과 1학년의 파이썬 · AI 공부 도우미 — 개인정보는 넣지 마세요")

for step in st.session_state.history:      # 다시 실행될 때마다 기록 전체를 말풍선으로 다시 그림
    if step["type"] == "user_input":
        st.chat_message("user").markdown(step_text(step))
    elif step["type"] == "model_output":
        st.chat_message("assistant").markdown(step_text(step))

# ---------- ★ 3-3 에서 새로 넣은 부분 : 사이드바 — 기억할 턴 수 · 새 대화 ----------
with st.sidebar:
    st.header("설정")
    max_turns = st.slider("기억할 턴 수 (MAX_TURNS)", min_value=1, max_value=10, value=6)
    if st.button("🧹 새 대화"):
        st.session_state.history = []
        st.rerun()                          # 지운 상태로 화면을 처음부터 다시 그림
    turns = sum(1 for step in st.session_state.history if step["type"] == "user_input")
    st.metric("기억 중인 턴", f"{turns} / {max_turns}")

# ---------- 메시지 보내기 ----------
if message := st.chat_input("메시지를 입력하세요"):     # 입력하고 Enter 를 누른 그 실행에서만 글이 들어옴
    st.chat_message("user").markdown(message)
    # ① 보낼 리스트를 따로 만듦 (성공했을 때만 진짜 기록으로 바꿈)
    send_list = trim_history(
        st.session_state.history + [{"type": "user_input", "content": [{"type": "text", "text": message}]}],
        max_turns,
    )
    with st.chat_message("assistant"):
        with st.spinner("생각하는 중..."):
            try:
                reply = client.interactions.create(
                    model=MODEL_NAME, store=False, system_instruction=SYSTEM_PROMPT, input=send_list,
                )
            except Exception as error:
                st.error(explain_error(error))                       # 실패하면 기록은 그대로
            else:
                st.markdown(reply.output_text)
                # ② 성공 → 보낸 리스트 + 모델의 답(단계들)을 진짜 기록으로
                st.session_state.history = send_list + [step.model_dump() for step in reply.steps]
                st.rerun()                  # 사이드바의 '기억 중인 턴' 숫자도 새로 그림
