import streamlit as st
import google.generativeai as genai
import time
import re
from weasyprint import HTML

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

# --- 3. HELPER FUNCTIONS ---
def is_arabic(text):
    return bool(re.search(r'[\u0600-\u06FF]', text))

def generate_pdf(quiz_data, level, topic):
    """Generates a styled A4 PDF document of questions and mark schemes."""
    items_html = ""
    for i, item in enumerate(quiz_data):
        q_text = item['q']
        a_text = item['a']
        
        q_rtl_class = "rtl" if is_arabic(q_text) else ""
        a_rtl_class = "rtl-box" if is_arabic(a_text) else ""
        
        items_html += f"""
        <div class="card">
            <div class="q-title">Question {i+1}</div>
            <div class="q-text {q_rtl_class}">{q_text}</div>
            <div class="ans-box {a_rtl_class}">
                <strong>Mark Scheme / Guidance:</strong><br>
                {a_text}
            </div>
        </div>
        """

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <meta charset="utf-8">
    <style>
      @page {{
        size: A4;
        margin: 15mm 15mm;
        background-color: #ffffff;
      }}
      body {{
        font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
        color: #1e293b;
        margin: 0;
        padding: 0;
      }}
      .header-table {{
        width: 100%;
        border-collapse: collapse;
        margin-bottom: 20px;
        border-bottom: 2px solid #004b95;
        padding-bottom: 10px;
      }}
      .header-title {{
        font-size: 20pt;
        font-weight: bold;
        color: #004b95;
      }}
      .header-meta {{
        font-size: 10pt;
        color: #64748b;
        margin-top: 4px;
      }}
      .card {{
        background-color: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 6px;
        padding: 12px 16px;
        margin-bottom: 14px;
        page-break-inside: avoid;
      }}
      .q-title {{
        font-size: 11pt;
        font-weight: bold;
        color: #004b95;
        margin-bottom: 4px;
      }}
      .q-text {{
        font-size: 11pt;
        font-weight: bold;
        color: #0f172a;
        margin-bottom: 8px;
      }}
      .q-text.rtl {{
        direction: rtl;
        text-align: right;
        font-size: 13pt;
      }}
      .ans-box {{
        background-color: #eff6ff;
        border-left: 4px solid #004b95;
        padding: 8px 12px;
        border-radius: 4px;
        font-size: 10pt;
        color: #1e293b;
        margin-top: 6px;
      }}
      .ans-box.rtl-box {{
        direction: rtl;
        text-align: right;
        border-left: none;
        border-right: 4px solid #004b95;
        font-size: 11pt;
      }}
    </style>
    </head>
    <body>
      <table class="header-table">
        <tr>
          <td>
            <div class="header-title">Retrieval Practice Sheet</div>
            <div class="header-meta">Exam Level: {level} | Topic: {topic}</div>
          </td>
        </tr>
      </table>
      {items_html}
    </body>
    </html>
    """
    return HTML(string=html_content).write_pdf()

# --- 4. FRAGMENTS (Independent Areas) ---
@st.fragment
def display_quiz():
    if 'quiz_data' in st.session_state and st.session_state.quiz_data:
        # Action Bar with Download Button
        col1, col2 = st.columns([3, 1])
        with col2:
            current_level = st.session_state.get('last_level', 'GCSE')
            current_topic = st.session_state.get('last_topic', 'Retrieval Practice')
            
            pdf_bytes = generate_pdf(st.session_state.quiz_data, current_level, current_topic)
            st.download_button(
                label="📄 Download PDF for Google Classroom",
                data=pdf_bytes,
                file_name=f"Retrieval_{current_topic.replace(' ', '_')}.pdf",
                mime="application/pdf",
                key="dl_pdf"
            )

        for i, item in enumerate(st.session_state.quiz_data):
            with st.container():
                st.divider()
                # --- THE QUESTION --- 
                q_text = item['q'] 
                if is_arabic(q_text): 
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

# --- 5. SIDEBAR ---
with st.sidebar:
    st.image("IMG_0202.png", use_container_width=True)
    
    st.divider()
    
    st.title("🎯 Topic Selector")
   
    level = st.selectbox("Exam Level:", ["GCSE", "A Level"])
    topic = st.text_input("Topic:", placeholder="e.g. Electrolysis")
    num_q = st.slider("Questions:", 1, 10, 5)

# --- 6. MAIN LOGIC & GENERATION ---
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
