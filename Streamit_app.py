import streamlit as st
import google.generativeai as genai

# 1. PAGE SETUP
st.set_page_config(page_title="Retrieval Practice", layout="wide")

# Custom CSS for bigger text and better UI
st.markdown("""
    <style>
    .stButton>button { width: 100%; border-radius: 10px; height: 3em; background-color: #f0f2f6; }
    .answer-box { background-color: #d4edda; padding: 15px; border-radius: 10px; border-left: 5px solid #28a745; }
    </style>
    """, unsafe_allow_html=True)

# 2. KEY LOADING (The "iPad-Proof" way)
# Checks secrets first, then offers manual input
if "GEMINI_API_KEY" in st.secrets:
    api_key = st.secrets["GEMINI_API_KEY"].strip()
else:
    api_key = st.sidebar.text_input("Enter API Key:", type="password")

# 3. SIDEBAR CONTROLS
with st.sidebar:
    st.title("🛠️ Setup")
    topic = st.text_input("Topic:", placeholder="e.g., Photosynthesis")
    num_q = st.slider("Number of Questions:", 1, 10, 5)
    st.info("The AI will generate short-answer retrieval questions.")

# 4. MAIN INTERFACE
st.title("🧠 Classroom Retrieval Practice")
st.write("Generate quick-fire questions to check for understanding.")

if st.button("✨ Generate New Questions"):
    if not api_key:
        st.error("Missing API Key! Add it to Streamlit Secrets or enter it in the sidebar.")
    elif not topic:
        st.warning("Please enter a topic first.")
    else:
        try:
            # Configure the AI
            genai.configure(api_key=api_key)
           
            # Using the explicit 'models/' path to prevent 404/v1beta errors
            model = genai.GenerativeModel('models/gemini-1.5-flash')
           
            prompt = f"Act as a teacher. Create {num_q} retrieval questions for {topic}. Format: Question | Answer. Keep answers very short. One per line."
           
            with st.spinner("Generating questions..."):
                response = model.generate_content(prompt)
               
                # Force response to string to prevent 'MarkdownMixin' TypeErrors
                full_text = str(response.text)
               
                # Parse the lines
                lines = [line for line in full_text.strip().split('\n') if "|" in line]
               
                new_questions = []
                for line in lines:
                    parts = line.split("|")
                    if len(parts) >= 2:
                        new_questions.append({
                            "q": parts[0].strip(),
                            "a": parts[1].strip()
                        })
               
                if new_questions:
                    st.session_state.questions = new_questions
                    # Force a refresh to show the new questions
                else:
                    st.error("The AI didn't use the correct format. Try clicking generate again.")

        except Exception as e:
            st.error(f"⚠️ Error: {str(e)}")

# 5. DISPLAY THE QUESTIONS
if 'questions' in st.session_state:
    for i, item in enumerate(st.session_state.questions):
        with st.container():
            st.divider()
            st.subheader(f"Q{i+1}: {item['q']}")
           
            # Using a unique key for every button
            if st.button(f"👁️ Reveal Answer {i+1}", key=f"btn_{i}"):
                st.markdown(f'<div class="answer-box"><b>Answer:</b> {item["a"]}</div>', unsafe_allow_html=True)

# 6. FOOTER
else:
    st.info("Enter a topic in the sidebar and hit Generate to begin.")
