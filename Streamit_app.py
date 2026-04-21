import streamlit as st
import google.generativeai as genai
import time

# 1. PAGE SETUP
st.set_page_config(page_title="Retrieval Practice", layout="wide")

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
        st.image("IMG_0202.png", use_container_width=True)
    except:
        st.title("📚 Topic Selection")
   
    level = st.selectbox("Level:", ["GCSE", "A Level"])
    topic = st.text_input("Topic:", placeholder="e.g. Waves")
    num_q = st.slider("Questions:", 1, 10, 5)
   
    st.divider()
    classroom_timer()

# 5. MAIN LOGIC
st.title("👨🏻‍🏫 Retrieval Practice")

if st.button("🚀 Generate Questions"):
    if not api_key or not topic:
        st.error("Missing API Key or Topic!")
    else:
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('models/gemini-2.5-flash-lite')
           
            # The "Strict Format" Prompt
            prompt = (
                f"Act as an Edexcel teacher. Create {num_q} questions for {topic} at {level}. "
                f"Use LaTeX for math (e.g. $E=mc^2$). "
                f"CRITICAL: Separate Question and Answer with exactly one '|' symbol. "
                f"Format: Question | Answer + Mark Scheme Keywords."
            )
           
            with st.spinner("Generating..."):
                res = model.generate_content(prompt)
                if not res.text:
                    st.warning("The API returned an empty response.")
                    st.stop()
                    
                lines = [l.strip() for l in res.text.split('\n') if "|" in l]

                if not lines:
                    st.error("The AI didnt format the question correctly. Try clicking Generate again.")
                else:
                   st.session_state.quiz_data = []
                for line in lines:
                    q, a = line.split("|", 1) # Only split on the first pipe
                    st.session_state.quiz_data.append({"q": q.strip(), "a": a.strip()})
                st.rerun()
        except Exception as e:
                if "429" in str(e):
                    st.error("**Quota Exhausted**.")
                elif "API_KEY_INVALID" in str(e):
                    st.error("**INVALID KEY**.")
                else:
                    st.error(f"Unexpected Error:{e}")
            

display_quiz()
