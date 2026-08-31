import streamlit as st
import google.generativeai as genai
import re

# --- 1. PAGE CONFIG & STYLING ---
st.set_page_config(page_title="Retrieval Practice Pro", layout="wide", page_icon="✅")

# CSS for Streamlit UI + Print-to-PDF Stylesheet
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

    /* PRINT STYLESHEET (Controls layout when exporting to PDF) */
    @media print {
        /* Hide sidebar, buttons, and navigation when printing */
        section[data-testid="stSidebar"],
        button,
        header,
        footer,
        .stButton,
        [data-testid="stHeader"] {
            display: none !important;
        }
        
        body, .main {
            background-color: #ffffff !important;
            color: #000000 !important;
        }
        
        .pdf-card {
            border: 1px solid #cbd5e1 !important;
            background-color: #f8fafc !important;
            padding: 12px 16px !important;
            margin-bottom: 14px !important;
            border-radius: 6px !important;
            page-break-inside: avoid !important;
        }

        .pdf-header {
            border-bottom: 2px solid #004b95;
            padding-bottom: 8px;
            margin-bottom: 20px;
        }
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. API SETUP ---
api_key = st.secrets.get("GEMINI_API_KEY", "")

# --- 3. HELPER FUNCTIONS ---
def is_arabic(text):
    """Detects if string contains Arabic characters."""
    return bool(re.search(r'[\u0600-\u06FF]', text))

# --- 4. FRAGMENTS (Independent Areas) ---
@st.fragment
def display_quiz():
    if 'quiz_data' in st.session_state and st.session_state.quiz_data:
        
        # Action Bar with Print/Save to PDF Trigger
        col1, col2 = st.columns([3, 1])
        with col1:
            st.caption(f"**Exam Level:** {st.session_state.get('last_level', 'GCSE')} | **Topic:** {st.session_state.get('last_topic', 'Retrieval Practice')}")
        with col2:
            # Native JS trigger opens browser print dialog (Save as PDF)
            st.components.v1.html("""
                <button onclick="window.parent.print()" style="
                    background-color: #004b95;
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 6px;
                    font-weight: bold;
                    cursor: pointer;
                    width: 100%;
                ">🖨️ Save as PDF</button>
            """, height=45)

        # Questions Display Loop
        for i, item in enumerate(st.session_state.quiz_data):
            st.markdown('<div class="pdf-card">', unsafe_allow_html=True)
            st.divider()
            
            # --- THE QUESTION --- 
            q_text = item['q'] 
            if is_arabic(q_text): 
                html_q = f'<div dir="rtl" style="text-align: right;"><h3>Q{i+1}: {q_text}</h3></div>' 
                st.markdown(html_q, unsafe_allow_html=True) 
            else: 
                st.markdown(f"### Q{i+1}: {q_text}") 

            # --- THE ANSWER / MARK SCHEME --- 
            if st.button(f"👁️ Reveal Answer Q{i+1}", key=f"rev_{i}"): 
                st.write("**Mark Scheme / Guidance:**") 
                
                a_text = item['a'] 
                if is_arabic(a_text): 
                    html_a = f'<div dir="rtl" style="text-align: right; background-color: #eff6ff; padding: 12px; border-radius: 6px; border-right: 4px solid #004b95;">{a_text}</div>' 
                    st.markdown(html_a, unsafe_allow_html=True) 
                else: 
                    st.info(a_text)
                    
            st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.info("👈 Set your topic in the sidebar and click Generate!")

# --- 5. SIDEBAR ---
with st.sidebar:
    try:
        st.image("IMG_0202.png", use_container_width=True)
    except Exception:
        pass  # Fallback if image isn't loaded
    
    st.divider()
    st.title("🎯 Topic Selector")
   
    level = st.selectbox("Exam Level:", ["GCSE", "A Level"])
    topic = st.text_input("Topic:", placeholder="e.g. Electrolysis")
    num_q = st.slider("Questions:", 1, 10, 5)

# --- 6. MAIN LOGIC & AI GENERATION ---
st.title("👨🏻‍🏫 Retrieval Practice")

if st.button("🚀 Generate Questions", key="main_gen"):
    if not api_key:
        st.error("API Key missing! Check your Secrets.")
    elif not topic:
        st.warning("Please enter a topic first.")
    else:
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-3.1-flash-lite')
           
            prompt = (
                f"Act as an expert {level} Edexcel examiner. " 
                f"Create {num_q} retrieval questions for the {level} {topic} topic, "
                f"strictly following the current Edexcel Specification. "
                f"The 'Answer' side must include specific Edexcel marking key words as found in official mark schemes. "
                f"Format every line exactly as: Question Text | Answer and Mark Scheme. "
                f"In the Answer section, include a brief 'Common Misconception' tip in brackets if applicable, focusing on misconceptions specifically mentioned in Examiner Reports. "
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
                           
                            if len(q_clean) > 3:
                                new_quiz.append({"q": q_clean, "a": a_clean})
               
                if new_quiz:
                    st.session_state.quiz_data = new_quiz
                    st.session_state.last_level = level
                    st.session_state.last_topic = topic
                    st.rerun()
                else:
                    st.error("The AI response was formatted incorrectly. Please try again.")
        
        except Exception as e:
            if "429" in str(e):
                st.error("Quota exceeded! Please wait a minute or check your daily limit.")
            else:
                st.error(f"An error occurred: {e}")

# --- 7. RENDER THE QUIZ ---
display_quiz()
