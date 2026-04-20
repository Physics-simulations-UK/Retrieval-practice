import streamlit as st
import google.generativeai as genai

# 1. PAGE SETUP
st.set_page_config(page_title="Retrieval Practice", layout="wide")

# Custom CSS for bigger text and explanation formatting
st.markdown("""
    <style>
    .stButton>button { width: 100%; border-radius: 10px; height: 3em; background-color: #f0f2f6; font-weight: bold; }
    .explanation-box {
        background-color: #e8f4fd;
        padding: 20px;
        border-radius: 10px;
        border-left: 6px solid #2196f3;
        font-size: 18px;
        line-height: 1.5;
    }
    </style>
    """, unsafe_allow_html=True)

# 2. KEY LOADING
if "GEMINI_API_KEY" in st.secrets:
    api_key = st.secrets["GEMINI_API_KEY"].strip()
else:
    api_key = st.sidebar.text_input("Enter API Key:", type="password")

# 3. SIDEBAR
with st.sidebar:
    st.title("🛠️ Settings")
    topic = st.text_input("Topic:", placeholder="e.g., GCSE Forces")
    num_q = st.sidebar.slider("Questions:", 1, 10, 5)
    st.info("Now providing detailed explanations for each answer!")

# 4. MAIN INTERFACE
st.title("🧠 Classroom Retrieval & Explanation")

if st.button("✨ Generate Detailed Questions"):
    if not api_key or not topic:
        st.warning("Please check your API Key and Topic.")
    else:
        try:
            genai.configure(api_key=api_key)
            # Using the 2026 stable model
            model = genai.GenerativeModel('models/gemini-2.5-flash-lite')
           
            # THE UPDATED PROMPT: Asking for explanations
            prompt = (
                f"Act as an expert teacher. Create {num_q} retrieval questions for {topic}. "
                f"Format each line exactly as: Question | Full Answer with a brief explanation. "
                f"Ensure the answer is accurate for the {topic} level."
            )
           
            with st.spinner("Gemini is thinking..."):
                response = model.generate_content(prompt)
                full_text = str(response.text)
                lines = [line for line in full_text.strip().split('\n') if "|" in line]
               
                quiz_data = []
                for line in lines:
                    parts = line.split("|")
                    if len(parts) >= 2:
                        quiz_data.append({"q": parts[0].strip(), "a": parts[1].strip()})
               
                st.session_state.quiz_data = quiz_data
                st.rerun()

        except Exception as e:
            st.error(f"Error: {str(e)}")

# 5. DISPLAY
if 'quiz_data' in st.session_state:
    for i, item in enumerate(st.session_state.quiz_data):
        with st.container():
            st.divider()
            st.markdown(f"### Q{i+1}: {item['q']}")
           
            if st.button(f"👁️ Reveal Detailed Answer", key=f"reveal_{i}"):
                st.markdown(f'<div class="explanation-box"><b>Answer & Explanation:</b><br>{item["a"]}</div>', unsafe_allow_html=True)
else:
    st.info("Ready for your next topic!")
