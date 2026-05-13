import streamlit as st
import google.generativeai as genai
import time

# --- 1. PAGE CONFIG & STYLING ---
st.set_page_config(page_title="Retrieval Practice Pro", layout="wide", page_icon="✅")

st.markdown("""
    <style>
    .explanation-box {
        background-color: #f0f7ff;
        padding: 18px;
        border-radius: 8px;
        border-left: 5px solid #004b95;
        color: #1e1e1e;
        margin-top: 10px;
    }
    .stMetric { background-color: #fff2f2; padding: 10px; border-radius: 10px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. API SETUP ---
api_key = st.secrets.get("GEMINI_API_KEY", "")

# --- 3. FRAGMENTS (Independent Areas) ---
import re
def is_arabic(text):
    return bool(re.search(r'[\u0600-\u06FF]', text))

@st.fragment
def display_quiz():
    if 'quiz_data' in st.session_state and st.session_state.quiz_data:
        for i, item in enumerate(st.session_state.quiz_data):
            with st.container():
                st.divider()
               # --- THE QUESTION --- 
                q_text = item['q'] 
                if is_arabic(q_text): # We use a single f-string block to avoid breaking the HTML 
                    html_q = f'<div dir="rtl" style="text-align: right;"><h3>Q{i+1}: {q_text}</h3></div>' 
                    st.markdown(html_q, unsafe_allow_html=True) 
                else: 
                    st.markdown(f"### Q{i+1}: {q_text}") 
                # --- THE ANSWER --- 
                if st.button(f"👁️ Reveal Answer", key=f"rev_{i}"): 
                    st.write("**Mark Scheme / Guidance:**") 
                    
                    a_text = item['a'] 
                    if is_arabic(a_text): 
                        html_a = f'<div dir="rtl" style="text-align: right; background-color: #f0f2f6; padding: 15px; border-radius: 10px;">{a_text}</div>' 
                        st.markdown(html_a, unsafe_allow_html=True) 
                    else: 
                        # Native info box for Science/Maths (handles LaTeX $) 
                        st.info(a_text)
    else:
        st.info("👈 Set your topic in the sidebar and click Generate!")

# --- 4. SIDEBAR ---
with st.sidebar:
    st.image("IMG_0202.png", use_container_width=True)
    
    st.divider()
    
    st.title("🎯 Topic Selector")
   
    level = st.selectbox("Exam Level:", ["GCSE", "A Level"])
    topic = st.text_input("Topic:", placeholder="e.g. Electrolysis")
    num_q = st.slider("Questions:", 1, 10, 5)
   

# --- 5. MAIN LOGIC & GENERATION ---
st.title("👨🏻‍🏫 Retrieval Practice")

if st.button("🚀 Generate Questions", key="main_gen"):
    if not api_key:
        st.error("API Key missing! Check your Secrets.")
    elif not topic:
        st.warning("Please enter a topic first.")
    else:
        try:
            genai.configure(api_key=api_key)
            # Using the latest 2026 stable model string
            model = genai.GenerativeModel('gemini-3.1-flash-lite')
           
            # Strict prompt to avoid 'blank' errors
            prompt = (
                f"Act as an expert {level} Edexcel examiner." 
                f"Create {num_q} retrieval questions for the {level} {topic} topic. "
                f"strictly follow the current Edexcel Specification."
                f"The 'Answer' side must include specific Edexcel marking key words as found in offical mark schemes."
                f"Format every line exactly as: Question Text | Answer and Mark Scheme. "
                f"In the Answer section, include a brief 'Common Misconception' tip in brackets if applicable, focus on misconceptions specifically mentioned in Examiner Reports."
                f"Use LaTeX for math/formulas (e.g., $E=mc^2$). "
                f"No bolding, no numbers, no intro text. Just the lines with |."
            )
           
            with st.spinner("Generating exam-style questions..."):
                response = model.generate_content(prompt)
                raw_text = response.text
               
                new_quiz = []
                for line in raw_text.split('\n'):
                    if "|" in line:
                        parts = line.split("|", 1)
                        if len(parts) == 2:
                            q_clean = parts[0].replace("*", "").strip()
                            a_clean = parts[1].replace("*", "").strip()
                           
                            if len(q_clean) > 3: # Ignore stray fragments
                                new_quiz.append({"q": q_clean, "a": a_clean})
               
                if new_quiz:
                    st.session_state.quiz_data = new_quiz
                    st.rerun()
                else:
                    st.error("The AI response was formatted incorrectly. Please try again.")
       
        except Exception as e:
            if "429" in str(e):
                st.error("Quota exceeded! Please wait a minute or check your daily limit.")
            else:
                st.error(f"An error occurred: {e}")

# --- 6. RENDER THE QUIZ ---
display_quiz()
