import streamlit as st
import json
import time
from google import genai

# --- 1. CONFIGURATION & CLIENT SETUP ---
# Quota Tip: Moving to the Pay-as-you-go tier in AI Studio increases limits.
API_KEY = "AIzaSyBGYl37P2CL4XgQ5lb6nr-xN1OZHWfDanE"  
MODEL_NAME = "models/gemini-2.0-flash" 

client = genai.Client(api_key=API_KEY)

# --- 2. DATA LOADING ---
try:
    with open('smi_data.json', 'r', encoding='utf-8') as f:
        smi_library = json.load(f)
except FileNotFoundError:
    st.error("⚠️ 'smi_data.json' not found. Please ensure it is in the project folder.")
    smi_library = []

# --- 3. UI SETUP (Amrit Bharat Theme) ---
st.set_page_config(page_title="Loco Diagnostic Assistant", page_icon="🚆", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stChatMessage { border-radius: 10px; border: 1px solid #ddd; }
    </style>
    """, unsafe_allow_html=True)

st.title("🚆 Amrit Bharat Train: Technical Assistant")
st.subheader("Official Locomotive Diagnostic & RDSO SMI Search")

with st.sidebar:
    st.header("Diagnostic Dashboard")
    st.success("API Status: Connected")
    st.info(f"Database: {len(smi_library)} SMI records indexed")
    if st.button("Clear Chat History"):
        st.session_state.messages = []
        st.rerun()

# --- 4. OPTIMIZED SEARCH LOGIC (Context Trimming) ---
def search_smi_context(query, max_chars=3000):
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
            
            # Prevent 429 errors by capping data sent to the AI[cite: 1].
            if current_length + len(content_snippet) < max_chars:
                matches.append(content_snippet)
                current_length += len(content_snippet)
            else:
                break 
                
    return "\n---\n".join(matches) if matches else "No specific SMI found."

# --- 5. CHAT INTERFACE ---
if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("Ask about WAP-5 faults, BPCS fluctuations, or SMI instructions..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Use trimmed context to avoid exhausting resource quota[cite: 1].
    context_data = search_smi_context(prompt)

    system_instruction = f"""
    You are a technical expert for Indian Railways Electrical Locomotives (WAP-5, WAP-7, WAG-9).
    Amrit Bharat trains use Push-Pull WAP-5 locomotives[cite: 1].
    
    SMI CONTEXT DATA:
    {context_data}
    
    USER QUESTION: {prompt}
    
    FORMATTING RULES:
    1. Use bullet points for maintenance steps.
    2. Reference specific SMI numbers if found in the context.
    3. If data is missing, suggest checking the RDSO 3-Phase Archive.
    """

    # --- 6. GENERATION WITH ENHANCED RETRY LOGIC (Handles 429 and 503) ---
    bot_response = ""
    with st.chat_message("assistant"):
        response_placeholder = st.empty()
        
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
                
                # Handle 429: Resource Exhausted (Quota limit hit)[cite: 1].
                if "429" in error_msg:
                    response_placeholder.warning(f"🚦 Quota hit. Waiting 60s for reset... (Attempt {attempt+1}/3)")
                    time.sleep(60) 
                    continue
                
                # Handle 503: Service Unavailable (Server busy)[cite: 1].
                elif "503" in error_msg:
                    response_placeholder.warning(f"☁️ Server busy. Retrying in 10s... (Attempt {attempt+1}/3)")
                    time.sleep(10)
                    continue
                
                else:
                    bot_response = f"⚠️ Connection Error: {error_msg}"
                    break
        
        response_placeholder.markdown(bot_response)

    st.session_state.messages.append({"role": "assistant", "content": bot_response})