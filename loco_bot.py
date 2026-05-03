import streamlit as st
import json
import time
from google import genai

# --- 1. SAFE CONFIGURATION & CLIENT SETUP ---
# Fetching the key from Streamlit Secrets to prevent "Leaked Key" 403 errors
try:
    API_KEY = st.secrets["GEMINI_API_KEY"]
except KeyError:
    st.error("🔑 API Key not found! Please add GEMINI_API_KEY to Streamlit Secrets.")
    st.stop()

# Using Gemini 2.0 Flash for improved efficiency and speed
MODEL_NAME = "models/gemini-2.5-flash" 
client = genai.Client(api_key=API_KEY)

# --- 2. DATA LOADING ---
try:
    with open('smi_data.json', 'r', encoding='utf-8') as f:
        smi_library = json.load(f)
except FileNotFoundError:
    st.error("⚠️ 'smi_data.json' not found. Ensure it is in your GitHub repository.")
    smi_library = []

# --- 3. UI SETUP ---
st.set_page_config(page_title="Loco Diagnostic Assistant", page_icon="🚆", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stChatMessage { border-radius: 10px; border: 1px solid #ddd; }
    </style>
    """, unsafe_allow_html=True)

st.title("🚆 Amrit Bharat Train: Technical Assistant")
st.subheader("Official Locomotive Diagnostic & RDSO SMI Search")

# Sidebar for System Status
with st.sidebar:
    st.header("Diagnostic Dashboard")
    st.success("API Status: Connected")
    st.info(f"Database: {len(smi_library)} SMI records indexed")
    if st.button("Clear Chat History"):
        st.session_state.messages = []
        st.rerun()

# --- 4. OPTIMIZED SEARCH LOGIC (Token Conservation) ---
def search_smi_context(query, max_chars=1500): # Lowered to 1500 for better stability
    """
    Limits character count to stay under the 250k token per minute limit.
    """
    query_words = query.lower().split()
    matches = []
    current_length = 0
    
    for entry in smi_library:
        entry_str = str(entry).lower()
        if any(word in entry_str for word in query_words):
            content_snippet = str(entry)
            
            # Standardization: Only add context if it fits the token inventory
            if current_length + len(content_snippet) < max_chars:
                matches.append(content_snippet)
                current_length += len(content_snippet)
            else:
                break 
                
    return "\n---\n".join(matches) if matches else "No specific SMI found."

# --- 5. CHAT INTERFACE ---
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display conversation history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# User Input Handling
if prompt := st.chat_input("Ask about WAP-5 faults, BPCS fluctuations, or SMI instructions..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Search for trimmed context
    context_data = search_smi_context(prompt)

    # History Trimming (Digital 5S): Send only last 3 messages to save tokens
    recent_history = st.session_state.messages[-3:] 
    history_text = "\n".join([f"{m['role'].upper()}: {m['content']}" for m in recent_history])

    system_instruction = f"""
    You are a technical expert for Indian Railways Electrical Locomotives (WAP-5, WAP-7, WAG-9).
    Amrit Bharat trains use Push-Pull WAP-5 locomotives.
    
    RECENT CONVERSATION:
    {history_text}
    
    SMI CONTEXT DATA:
    {context_data}
    
    USER QUESTION: {prompt}
    
    FORMATTING: Use bullet points for maintenance steps. Reference SMI numbers if found.
    """

    # --- 6. GENERATION WITH ENHANCED RETRY LOGIC ---
    bot_response = ""
    with st.chat_message("assistant"):
        response_placeholder = st.empty()
        
        # 3-Attempt Reliability Cycle mirroring locomotive redundancy
        for attempt in range(3):
            try:
                response = client.models.generate_content(
                    model=MODEL_NAME,
                    contents=system_instruction
                )
                bot_response = response.text
                break 
                
            except Exception as e:
                error_msg = str(e)
                
                if "429" in error_msg:
                    response_placeholder.warning(f"🚦 Quota hit. Waiting 60s to reset... (Attempt {attempt+1}/3)")
                    time.sleep(60) 
                    continue
                elif "503" in error_msg:
                    response_placeholder.warning(f"☁️ Server busy. Retrying in 10s... (Attempt {attempt+1}/3)")
                    time.sleep(10)
                    continue
                else:
                    bot_response = f"⚠️ Technical Error: {error_msg}"
                    break
        
        response_placeholder.markdown(bot_response)

    st.session_state.messages.append({"role": "assistant", "content": bot_response})
