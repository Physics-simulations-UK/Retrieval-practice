import streamlit as st
import google.generativeai as genai
import requests
import re

# --- 1. PAGE CONFIG & STYLING ---
st.set_page_config(page_title="Retrieval Practice Pro", layout="wide", page_icon="✅")

# CSS to standardize buttons and enforce high-contrast print styling
st.markdown("""
    <style>
    /* Uniform height & font for all top action buttons */
    .stButton > button {
        height: 40px !important;
        font-size: 14px !important;
        font-weight: 500 !important;
        border-radius: 8px !important;
    }

    .explanation-box {
        background-color: #f0f7ff;
        padding: 18px;
        border-radius: 8px;
        border-left: 5px solid #004b95;
        color: #1e1e1e;
        margin-top: 10px;
    }

    /* PRINT STYLESHEET (Controls layout and contrast when exporting to PDF) */
    @media print {
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

        /* Force ALL text to render in solid dark print font */
        h1, h2, h3, h4, p, span, div, strong, em {
            color: #000000 !important;
            -webkit-print-color-adjust: exact !important;
            print-color-adjust: exact !important;
        }

        /* Override st.info / stAlert soft grey styling for full contrast print */
        [data-testid="stAlert"] {
            background-color: #f8fafc !important;
            color: #000000 !important;
            border: 1px solid #004b95 !important;
            opacity: 1 !important;
        }
        
        [data-testid="stAlert"] * {
            color: #000000 !important;
        }
        
        .pdf-card {
            border: 1px solid #cbd5e1 !important;
            background-color: #ffffff !important;
            padding: 12px 16px !important;
            margin-bottom: 14px !important;
            border-radius: 6px !important;
            page-break-inside: avoid !important;
        }
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. API SETUP & SECRETS ---
api_key = st.secrets.get("GEMINI_API_KEY", "")
apps_script_url = st.secrets.get("APPS_SCRIPT_URL", "")

# --- 3. HELPER FUNCTIONS ---
def is_arabic(text):
    """Detects if string contains Arabic characters."""
    return bool(re.search(r'[\u0600-\u06FF]', text))

# --- 4. SIDEBAR ---
with st.sidebar:
    try:
        st.image("IMG_0202.png", use_container_width=True)
    except Exception:
        pass
    
    st.divider()
    st.title("🎯 Topic Selector")
   
    level = st.selectbox("Exam Level:", ["GCSE", "A Level"])
    topic = st.text_input("Topic:", placeholder="e.g. Electrolysis")
    num_q = st.slider("Questions:", 1, 10, 5)

# --- 5. MAIN PAGE & SINGLE-ROW ACTION BUTTONS ---
st.title("👨🏻‍🏫 Retrieval Practice")

# Create 4 columns so all buttons fit neatly in one horizontal row
col1, col2, col3, col4 = st.columns([1.8, 1.8, 1.8, 2.2])

with col1:
    # BUTTON 1: GENERATE QUESTIONS
    generate_clicked = st.button("🚀 Generate Questions", key="main_gen", type="primary", use_container_width=True)

# Logic for Question Generation
if generate_clicked:
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
                    st.session_state.revealed_answers = [False] * len(new_quiz)
                    st.rerun()
                else:
                    st.error("The AI response was formatted incorrectly. Please try again.")
        
        except Exception as e:
            if "429" in str(e):
                st.error("Quota exceeded! Please wait a minute or check your daily limit.")
            else:
                st.error(f"An error occurred: {e}")

# Render Master Toggle, Print, and Google Form buttons alongside Generate
if 'quiz_data' in st.session_state and st.session_state.quiz_data:
    quiz_len = len(st.session_state.quiz_data)

    if 'revealed_answers' not in st.session_state or len(st.session_state.revealed_answers) != quiz_len:
        st.session_state.revealed_answers = [False] * quiz_len

    all_revealed = all(st.session_state.revealed_answers)
    master_label = "🙈 Hide All Answers" if all_revealed else "👁️ Reveal All Answers"

    with col2:
        # BUTTON 2: MASTER REVEAL / HIDE ALL
        if st.button(master_label, key="master_toggle_button", use_container_width=True):
            st.session_state.revealed_answers = [not all_revealed] * quiz_len
            st.rerun()

    with col3:
        # BUTTON 3: SAVE TO PDF
        print_clicked = st.button("🖨️ Save as PDF", key="print_pdf_btn", use_container_width=True)
        if print_clicked:
            st.components.v1.html("<script>window.parent.print();</script>", height=0, width=0)

    with col4:
        # BUTTON 4: EXPORT TO GOOGLE FORM
        export_gform_clicked = st.button("📝 Export to Google Form", key="export_gform_btn", use_container_width=True)

    # Handle Google Form Export Logic
    if export_gform_clicked:
        if not apps_script_url:
            st.error("Apps Script URL missing from Streamlit Secrets!")
        else:
            with st.spinner("Building Google Form in your Drive..."):
                payload = {
                    "level": st.session_state.get('last_level', 'GCSE'),
                    "topic": st.session_state.get('last_topic', 'Retrieval Practice'),
                    "questions": st.session_state.quiz_data
                }
                
                try:
                    # Send payload to Google Apps Script Web App
                    res = requests.post(apps_script_url, json=payload, timeout=20)
                    result_data = res.json()
                    
                    if result_data.get("status") == "success":
                        st.success("Google Form Created Successfully!")
                        st.markdown(f"[👉 Click here to open and edit your Google Form]({result_data['editUrl']})")
                    else:
                        st.error(f"Apps Script Error: {result_data.get('message')}")
                except Exception as err:
                    st.error(f"Failed to connect to Apps Script: {err}")

    st.divider()

    # --- 6. QUESTIONS DISPLAY LOOP ---
    st.subheader(f"Topic: {st.session_state.get('last_topic', 'Retrieval Practice')} ({st.session_state.get('last_level', 'GCSE')})")

    for i, item in enumerate(st.session_state.quiz_data):
        st.markdown('<div class="pdf-card">', unsafe_allow_html=True)
        
        # --- Question ---
        q_text = item['q']
        if is_arabic(q_text):
            st.markdown(f'<div dir="rtl" style="text-align: right;"><h3>Q{i+1}: {q_text}</h3></div>', unsafe_allow_html=True)
        else:
            st.markdown(f"### Q{i+1}: {q_text}")

        # --- Individual Answer Toggle Button ---
        is_revealed = st.session_state.revealed_answers[i]
        btn_label = "🙈 Hide Answer" if is_revealed else "👁️ Reveal Answer"
        
        if st.button(f"{btn_label} Q{i+1}", key=f"individual_btn_{i}"):
            st.session_state.revealed_answers[i] = not is_revealed
            st.rerun()

        # --- Answer Output ---
        if st.session_state.revealed_answers[i]:
            st.write("**Mark Scheme / Guidance:**")
            a_text = item['a']
            if is_arabic(a_text):
                st.markdown(f'<div dir="rtl" style="text-align: right; background-color: #eff6ff; padding: 12px; border-radius: 6px; border-right: 4px solid #004b95;">{a_text}</div>', unsafe_allow_html=True)
            else:
                st.info(a_text)
                
        st.markdown('</div>', unsafe_allow_html=True)
        st.divider()

else:
    st.divider()
    st.info("👈 Enter a topic in the sidebar and click 'Generate Questions' to start.")
