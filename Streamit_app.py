import streamlit as st
import google.generativeai as genai

# --- PAGE CONFIG ---
st.set_page_config(page_title="Gemini Retrieval Tool", layout="wide")

# Custom Styling (Projector Mode)
st.markdown("""
    <style>
    .stButton>button { width: 100%; height: 3.5em; font-size: 20px !important; }
    .question-box { font-size: 38px !important; font-weight: bold; margin-bottom: 20px; }
    .answer-box { font-size: 32px !important; color: #ffffff; background-color: #1a73e8; padding: 20px; border-radius: 10px; }
    </style>
    """, unsafe_allow_now_ok=True)

# --- SIDEBAR ---
with st.sidebar:
    st.title("⚙️ Gemini Setup")
    gemini_key = st.text_input("Enter Gemini API Key", type="password")
    topic = st.text_input("Topic:", placeholder="e.g. Victorian London")
    num_q = st.slider("Questions:", 1, 10, 5)

# --- GENERATION LOGIC ---
if st.button("✨ Generate Retrieval Questions"):
    if not gemini_key:
        st.error("Please add your API key in the sidebar!")
    elif not topic:
        st.error("Please enter a topic!")
    else:
        try:
            genai.configure(api_key=gemini_key)
            model = genai.GenerativeModel('gemini-1.5-flash') # Using the fast, free-tier model
           
            prompt = f"Create {num_q} short-answer retrieval questions for students on {topic}. Format each line exactly as: Question | Answer"
           
            response = model.generate_content(prompt)
            # Parse the response
            lines = [line for line in response.text.strip().split('\n') if "|" in line]
            st.session_state.qa_pairs = []
            for line in lines:
                q, a = line.split("|")
                st.session_state.qa_pairs.append({"q": q.strip(), "a": a.strip()})
        except Exception as e:
            st.error(f"Error: {e}")

# --- DISPLAY ---
if 'qa_pairs' in st.session_state:
    for i, pair in enumerate(st.session_state.qa_pairs):
        st.markdown(f"### Question {i+1}")
        st.markdown(f"<div class='question-box'>{pair['q']}</div>", unsafe_allow_now_ok=True)
       
        if st.button(f"Reveal Answer {i+1}", key=f"ans_{i}"):
            st.markdown(f"<div class='answer-box'>✅ {pair['a']}</div>", unsafe_allow_now_ok=True)
        st.write("")
