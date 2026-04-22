import streamlit as st
import google.generativeai as genai
import time

# 1. PAGE SETUP
st.set_page_config(page_title="Edexcel Retrieval", layout="wide")

st.markdown("""
    <style>
    .explanation-box {
        background-color: #f8f9fa;
        padding: 20px;
        border-radius: 10px;
        border-left: 6px solid #2196f3;
        line-height: 1.6;
    }
    [data-testid="stMetricValue"] { font-size: 45px; color: #ff4b4b; }
    </style>
    """, unsafe_allow_html=True)

# 2. API KEY LOADING
api_key = st.secrets.get("GEMINI_API_KEY", "")

# 3. FRAGMENTS
@st.fragment
def classroom_timer():
    st.subheader("⏲️ Classroom Timer")
    duration = st.number_input("Seconds:", 5, 300, 30, 5)
    if st.button("⏱️ Start Countdown", key="t_btn"):
        ph = st.empty()
        for i in range(duration, -1, -1):
            ph.metric("Time Remaining", f"{i}s")
            time.sleep(1)
        ph.success("⏰ Time is up!")
        st.balloons()

@st.fragment
def display_quiz():
    if 'quiz_data' in st.session_state:
        for i, item in enumerate(st.session_state.quiz_data):
            st.divider()
            st.markdown(f"### Q{i+1}: {item['q']}")
            if st.button(f"👁️ Reveal Answer", key=f"rev_{i}"):
                # We use Markdown to ensure LaTeX ($) renders correctly
                st.markdown(f'<div class="explanation-box"><b>Edexcel Guidance:</b><br>{item["a"]}</div>', unsafe_allow_html=True)
    else:
        st.info("Ready for your topic selection!")

# 4. SIDEBAR
with st.sidebar:
    try:
        st.image("mylogo.png", use_container_width=True)
    except:
        st.title("🎯 Edexcel Prep")
   
    level = st.selectbox("Level:", ["KS3", "GCSE", "A Level"])
    topic = st.text_input("Topic:", placeholder="e.g. Waves")
    num_q = st.slider("Questions:", 1, 10, 5)
   
    st.divider()
    classroom_timer()

# 5. MAIN LOGIC
st.title("🧠 Edexcel Retrieval Practice")

if st.button("🚀 Generate Questions"):
    if not api_key or not topic:
        st.error("Missing API Key or Topic!")
    else:
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('models/gemini-2.5-flash-lite')
           
             # 1. We tell the AI to be VERY simple with the format
            prompt = (
                f"Create {num_q} Edexcel {level} questions about {topic}. "
                f"Use this EXACT format for every line: Question Text | Answer Text. "
                f"Do not use bold, do not use bullet points, do not use numbers. "
                f"Use LaTeX for math like $E=mc^2$."
            )
           
            with st.spinner("Writing questions..."):
                res = model.generate_content(prompt)
                raw_text = res.text
               
                # DEBUG: This lets you see what the AI actually said if it fails
                # st.write(raw_text)

                st.session_state.quiz_data = []
               
                for line in raw_text.split('\n'):
                    if "|" in line:
                        # We split and then strip out any weird characters like * or numbers
                        parts = line.split("|")
                        if len(parts) >= 2:
                            q = parts[0].replace("*", "").strip()
                            a = parts[1].replace("*", "").strip()
                           
                            # Only add if it's not empty
                            if q and a:
                                st.session_state.quiz_data.append({"q": q, "a": a})
               
                st.rerun()
        except Exception as e:
            st.error(f"Quota error or Connection issue: {e}")

display_quiz()
