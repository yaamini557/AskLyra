import os
import io
import json
import uuid
import streamlit as st
from google import genai
from google.genai import types
from dotenv import load_dotenv

# ---------- PAGE CONFIG ----------
st.set_page_config(page_title="AskLyra", page_icon="✨", layout="centered")

load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=API_KEY)

# ---------- SETTINGS ----------
MODELS = [
    "gemini-3.5-flash-lite",  # main (copy exact names from AI Studio if these differ)
    "gemma-4-31b-it",         # backup
]

SYSTEM_PROMPT = (
    "You are Lyra, a friendly, warm and clear AI companion. "
    "Give helpful, well-organized answers. Keep replies concise unless the "
    "user asks for detail. If the user uploads an image or document, "
    "use it to answer their question.Use emojis if required based on the replies you give."
)

MAX_HISTORY = 8          # only send the last N messages to the model
CHAT_DIR = "chats"       # folder where chats are saved
os.makedirs(CHAT_DIR, exist_ok=True)

IMAGE_TYPES = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp"}

# ---------- CUSTOM STYLING ----------
st.markdown("""
    <style>
    .stApp {
        background: radial-gradient(circle at 20% 20%, #1a1a3e 0%, #0a0a1f 50%, #000000 100%);
    }
    .stChatMessage {
        border-radius: 16px;
        padding: 14px;
        margin-bottom: 12px;
        background-color: rgba(255, 255, 255, 0.06);
        border: 1px solid rgba(167, 139, 250, 0.2);
        box-shadow: 0 0 20px rgba(167, 139, 250, 0.1);
    }
    h1 {
        text-align: center;
        background: linear-gradient(90deg, #a78bfa, #f472b6, #facc15);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 900;
        font-size: 3rem;
        margin-bottom: 5px;
        letter-spacing: 2px;
    }
    .subtitle {
        text-align: center;
        color: #c4b5fd;
        font-style: italic;
        margin-bottom: 35px;
        font-size: 1.1rem;
    }
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0a0a1f 0%, #1a1a3e 100%);
        border-right: 1px solid rgba(167, 139, 250, 0.2);
    }
    section[data-testid="stSidebar"] .stButton button {
        text-align: left;
        justify-content: flex-start;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }
    header[data-testid="stHeader"] {
        background: transparent;
    }
    .fixed-header {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        z-index: 999;
        padding: 2.8rem 0 0.6rem 0;
        background: rgba(10, 10, 31, 0.9);
        backdrop-filter: blur(8px);
        border-bottom: 1px solid rgba(167, 139, 250, 0.2);
        text-align: center;
    }
    .fixed-header h1 {
        font-size: 2.2rem;
        margin: 0;
    }
    .fixed-header .subtitle {
        margin: 0;
        font-size: 0.95rem;
    }
    .block-container {
        padding-top: 9rem !important;
    }
    </style>
""", unsafe_allow_html=True)

# ---------- HEADER ----------
st.markdown(
    """
    <div class="fixed-header">
        <h1>✨ AskLyra</h1>
    </div>
    """,
    unsafe_allow_html=True,
)


# ---------- SAVE / LOAD CHATS ----------
def new_chat_id():
    return uuid.uuid4().hex[:10]


def chat_path(cid):
    return os.path.join(CHAT_DIR, f"{cid}.json")


def save_chat():
    """Save the current chat to disk (uploaded files are saved as names only)."""
    cid = st.session_state.current_id
    msgs = []
    for m in st.session_state.messages:
        msgs.append({
            "role": m["role"],
            "content": m["content"],
            "files": [f["name"] for f in m.get("files", [])],
            "model": m.get("model"),
        })
    first_user = next((m for m in st.session_state.messages if m["role"] == "user"), None)
    title = "New chat"
    if first_user:
        title = (first_user["content"] or "").strip()[:35]
        if not title and first_user.get("files"):
            title = "📄 " + first_user["files"][0]["name"][:30]
        if not title:
            title = "New chat"
    with open(chat_path(cid), "w", encoding="utf-8") as f:
        json.dump({"id": cid, "title": title, "messages": msgs}, f, ensure_ascii=False)


def load_chat(cid):
    try:
        with open(chat_path(cid), "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return []
    messages = []
    for m in data.get("messages", []):
        messages.append({
            "role": m["role"],
            "content": m["content"],
            "files": [{"name": n, "data": None} for n in m.get("files", [])],
            "model": m.get("model"),
        })
    return messages


def list_chats():
    items = []
    for fn in os.listdir(CHAT_DIR):
        if fn.endswith(".json"):
            p = os.path.join(CHAT_DIR, fn)
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                items.append((os.path.getmtime(p), data["id"], data.get("title", "Chat")))
            except Exception:
                continue
    items.sort(reverse=True)
    return items


def start_new_chat():
    st.session_state.current_id = new_chat_id()
    st.session_state.messages = []


# ---------- STATE ----------
if "current_id" not in st.session_state:
    start_new_chat()

# ---------- SIDEBAR ----------
with st.sidebar:
    st.markdown("### 🌌 AskLyra")
    if st.button("➕ New chat", use_container_width=True, type="primary"):
        start_new_chat()
        st.rerun()

    st.markdown("---")
    st.caption("💬 Your chats")
    chats = list_chats()
    if not chats:
        st.caption("No saved chats yet.")
    for _, cid, title in chats[:30]:
        col1, col2 = st.columns([5, 1])
        is_current = cid == st.session_state.current_id
        with col1:
            if st.button(
                title or "Chat",
                key=f"open_{cid}",
                use_container_width=True,
                type="primary" if is_current else "secondary",
            ):
                st.session_state.current_id = cid
                st.session_state.messages = load_chat(cid)
                st.rerun()
        with col2:
            if st.button("🗑", key=f"del_{cid}"):
                try:
                    os.remove(chat_path(cid))
                except Exception:
                    pass
                if is_current:
                    start_new_chat()
                st.rerun()

    st.markdown("---")
    st.caption("📎 Upload images, PDFs, text files and Word docs.")
    


# ---------- HELPERS ----------
def read_docx(data: bytes) -> str:
    try:
        from docx import Document
        doc = Document(io.BytesIO(data))
        return "\n".join(p.text for p in doc.paragraphs)
    except Exception:
        return "(Could not read this Word file. Install python-docx: pip install python-docx)"


def file_to_part(f):
    ext = f["name"].rsplit(".", 1)[-1].lower()
    if ext in IMAGE_TYPES:
        return types.Part.from_bytes(data=f["data"], mime_type=IMAGE_TYPES[ext])
    if ext == "pdf":
        return types.Part.from_bytes(data=f["data"], mime_type="application/pdf")
    if ext == "docx":
        return types.Part.from_text(text=f"[Contents of {f['name']}]\n{read_docx(f['data'])}")
    text = f["data"].decode("utf-8", errors="ignore")
    return types.Part.from_text(text=f"[Contents of {f['name']}]\n{text}")


def build_contents(messages):
    contents = []
    for m in messages[-MAX_HISTORY:]:
        parts = []
        for f in m.get("files", []):
            if f.get("data") is not None:
                parts.append(file_to_part(f))
            else:
                parts.append(types.Part.from_text(
                    text=f"[Earlier attachment: {f['name']} (no longer available)]"))
        parts.append(types.Part.from_text(text=m["content"] or "(see attached file)"))
        role = "user" if m["role"] == "user" else "model"
        contents.append(types.Content(role=role, parts=parts))
    return contents


def ask_model(messages):
    contents = build_contents(messages)
    errors = []
    for model_name in MODELS:
        try:
            if model_name.startswith("gemma"):
                c = list(contents)
                c[0].parts.insert(0, types.Part.from_text(text=SYSTEM_PROMPT + "\n\n"))
                response = client.models.generate_content(model=model_name, contents=c)
            else:
                response = client.models.generate_content(
                    model=model_name,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_PROMPT,
                        max_output_tokens=2000,
                    ),
                )
            if response.text:
                return response.text, model_name
        except Exception as e:
            errors.append(f"{model_name}: {str(e)[:150]}")
            continue
    raise RuntimeError(" | ".join(errors) if errors else "No model responded.")


def show_files(files):
    for f in files:
        ext = f["name"].rsplit(".", 1)[-1].lower()
        if ext in IMAGE_TYPES and f.get("data") is not None:
            st.image(f["data"], width=250)
        else:
            st.caption(f"📄 {f['name']}")


# ---------- RENDER HISTORY ----------
if not st.session_state.messages:
    st.markdown(
        "<p style='text-align:center;color:#c4b5fd;margin-top:3rem;'>"
        "👋 Hi, I'm Lyra! Ask me anything, or tap <b>+</b> to upload a file.</p>",
        unsafe_allow_html=True,
    )

for msg in st.session_state.messages:
    avatar = "🧑" if msg["role"] == "user" else "✨"
    with st.chat_message(msg["role"], avatar=avatar):
        show_files(msg.get("files", []))
        if msg["content"]:
            st.write(msg["content"])
        if msg.get("model"):
            st.caption(f"model: {msg['model']}")

# ---------- USER INPUT ----------
user_input = st.chat_input(
    "Ask Lyra something...",
    accept_file="multiple",
    file_type=["png", "jpg", "jpeg", "webp", "pdf", "txt", "md", "csv", "docx"],
)

if user_input:
    text = user_input.text or ""
    files = [{"name": f.name, "data": f.getvalue()} for f in (user_input.files or [])]

    st.session_state.messages.append({"role": "user", "content": text, "files": files})
    with st.chat_message("user", avatar="🧑"):
        show_files(files)
        if text:
            st.write(text)

    with st.chat_message("assistant", avatar="✨"):
        with st.spinner("Lyra is thinking..."):
            try:
                reply, used = ask_model(st.session_state.messages)
            except Exception as e:
                reply = (
                    "😔 Sorry, I'm out of free requests right now or something went wrong. "
                    "Please try again in a minute.\n\n"
                    f"`{str(e)[:300]}`"
                )
                used = None
            st.write(reply)
            if used:
                st.caption(f"model: {used}")

    st.session_state.messages.append(
        {"role": "assistant", "content": reply, "files": [], "model": used}
    )
    save_chat()
    if len(st.session_state.messages) == 2:
        st.rerun()  # refresh sidebar so the new chat appears in the list