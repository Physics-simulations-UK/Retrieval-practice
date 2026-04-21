import streamlit as st
import google.generativeai as genai
import time

# 1. PAGE SETUP
st.set_page_config(page_title="Edexcel Retrieval Practice", layout="wide")

# Custom CSS for UI
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
    /* Styles the timer metric */
    [data-testid="stMetricValue"] {
        font-size: 40px;
        color: #ff4b4b;
    }
    </style>
    """, unsafe_allow_html=True)

# 2. KEY LOADING
if "GEMINI_API_KEY" in st.secrets:
    api_key = st.secrets["GEMINI_API_KEY"].strip()
else:
    api_key = st.sidebar.text_input("Enter API Key:", type="password")

# 3. SIDEBAR (Logo, Selection, and Timer)
with st.sidebar:
    # Handle Logo (Ensure your file is named 'mylogo.png' on GitHub)
    try:
        st.image("IMG_0202.png", use_container_width=True)
    
    
    st.title("🎯 Selection")
    
    level = st.selectbox(
        "Select Level:",
        ["KS3 (Year 7-9)", "GCSE", "A Level"]
    )
    
    topic = st.text_input("Enter Topic:", placeholder="e.g., Forces & Motion")
    num_q = st.slider("Questions:", 1, 10, 5)
    
    st.divider()
    
    # --- CLASSROOM TIMER SECTION ---
    st.subheader("⏲️ Classroom Timer")
    duration = st.number_input("Seconds:", min_value=5, max_value=300, value=30, step=5)
    
    if st.button("⏱️ Start Countdown"):
        timer_place = st.empty()
        for remaining in range(duration, -1, -1):
            timer_place.metric("Time Remaining", f"{remaining}s")
            time.sleep(1)
        st.balloons()
        timer_place.success("⏰ Time is up!")

# 4. MAIN GENERATION LOGIC
st.title("🧠 Edexcel Retrieval Practice")

if st.button("🚀 Generate Edexcel Questions"):
    if not api_key or not topic:
        st.warning("Please provide an API Key and a Topic.")
    else:
        try:
            genai.configure(api_key=api_key)
            # Using Lite for better free-tier stability in 2026
            model = genai.GenerativeModel('models/gemini-2.5-flash-lite')
            
            prompt = (
                f"Act as a senior Edexcel examiner. Create {num_q} retrieval questions for {topic} "
                f"at {level} level. Focus on conceptual depth. "
                f"Format: Question | Answer + Explanation + 'Key Terms' for the mark scheme. "
                f"Ensure terminology matches Edexcel specification exactly."
            )
            
            with st.spinner(f"Creating {level} questions..."):
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
            st.error(f"⚠️ Error: {str(e)}")

# 5. DISPLAY QUESTIONS
if 'quiz_data' in st.session_state:
    for i, item in enumerate(st.session_state.quiz_data):
        with st.container():
            st.divider()
            st.markdown(f"### Q{i+1}: {item['q']}")
            
            if st.button(f"👁️ Reveal Answer & Mark Scheme", key=f"reveal_{i}"):
                st.markdown(f'<div class="explanation-box"><b>Edexcel Guidance:</b><br>{item["a"]}</div>', unsafe_allow_html=True)
else:
    st.info("Select your level and topic in the sidebar to start.")
