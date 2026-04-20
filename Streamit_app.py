import streamlit as st
import google.generativeai as genai

# 1. SETUP
st.set_page_config(page_title="Classroom Retrieval", layout="wide")

# 2. LOAD KEY
api_key = st.secrets.get("GEMINI_API_KEY")

# 3. SIDEBAR
with st.sidebar:
    st.title("Settings")
    topic = st.text_input("Topic:", placeholder="e.g. Fractions")
    num_q = st.slider("Questions:", 1, 10, 5)
    if not api_key:
        st.error("🔑 Key not found in Secrets!")
        api_key = st.text_input("Enter Key Manually:", type="password")

# 4. MAIN INTERFACE
st.title("🧠 Retrieval Practice")

if st.button("Generate Questions"):
    if not api_key or not topic:
        st.warning("Please ensure Topic and API Key are ready.")
    else:
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-1.5-flash')
           
            # We tell the AI to ONLY give us the Q|A format
            prompt = f"Provide {num_q} retrieval questions for {topic}. Use the format: Question | Answer. Do not include intro or outro text. One per line."
           
            with st.spinner("Generating..."):
                response = model.generate_content(prompt)
               
                # SAFE PARSING LOGIC
                raw_lines = response.text.strip().split('\n')
                valid_questions = []
               
                for line in raw_lines:
                    if "|" in line:
                        parts = line.split("|")
                        # Only add if it actually has two parts
                        if len(parts) >= 2:
                            valid_questions.append({
                                "q": parts[0].strip(),
                                "a": parts[1].strip()
                            })
               
                if valid_questions:
                    st.session_state.questions = valid_questions
                else:
                    st.error("The AI didn't use the right format. Try clicking Generate again.")
                   
        except Exception as e:
            st.error(f"Error: {e}")

# 5. DISPLAY (with safe check)
if 'questions' in st.session_state:
    for i, item in enumerate(st.session_state.questions):
        st.divider()
        st.subheader(f"Q{i+1}: {item['q']}")
        # Unique keys are vital in Streamlit
        if st.button(f"Reveal Answer {i+1}", key=f"btn_{i}"):
            st.success(f"Answer: {item['a']}")
