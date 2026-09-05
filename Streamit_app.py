import streamlit as st
import google.generativeai as genai
import re
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# --- 1. PAGE CONFIG & STYLING ---
st.set_page_config(page_title="Retrieval Practice Pro", layout="wide", page_icon="✅")

st.markdown("""
    <style>
    .stButton > button {
        height: 40px !important;
        font-size: 14px !important;
        font-weight: 500 !important;
        border-radius: 8px !important;
    }
    .pdf-card {
        border: 1px solid #cbd5e1 !important;
        background-color: #ffffff !important;
        padding: 12px 16px !important;
        margin-bottom: 14px !important;
        border-radius: 6px !important;
        page-break-inside: avoid !important;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. INITIALIZE SESSION STATE ---
if "quiz_data" not in st.session_state:
    st.session_state.quiz_data = []

api_key = st.secrets.get("GEMINI_API_KEY", "")

def is_arabic(text):
    return bool(re.search(r'[\u0600-\u06FF]', text))

# --- 3. GOOGLE OAUTH HANDLING ---
SCOPES = [
    'https://www.googleapis.com/auth/forms.body',
    'https://www.googleapis.com/auth/drive.file'
]

def get_oauth_flow():
    client_config = {
        "web": {
            "client_id": st.secrets["google_oauth"]["client_id"],
            "client_secret": st.secrets["google_oauth"]["client_secret"],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [st.secrets["google_oauth"]["redirect_uri"]]
        }
    }
    # autogenerate state=None to prevent PKCE state mismatch loops on redirects
    flow = Flow.from_client_config(
        client_config,
        scopes=SCOPES,
        redirect_uri=st.secrets["google_oauth"]["redirect_uri"]
    )
    return flow

# PERSISTENT CREDENTIAL RECOVERY
# 1. Check if token already stored in session
creds_dict = st.session_state.get("google_creds", None)

# 2. Check if coming back from Google redirect with ?code=
if not creds_dict and "code" in st.query_params:
    try:
        flow = get_oauth_flow()
        # Fetch token without strictly enforcing state check across session restarts
        flow.fetch_token(code=st.query_params["code"])
        c = flow.credentials
        
        creds_dict = {
            'token': c.token,
            'refresh_token': c.refresh_token,
            'token_uri': c.token_uri,
            'client_id': c.client_id,
            'client_secret': c.client_secret,
            'scopes': c.scopes
        }
        st.session_state["google_creds"] = creds_dict
        st.toast("✅ Google Drive Connected Successfully!", icon="🎉")
    except Exception as e:
        st.error(f"Authentication Error: {e}")

def get_valid_credentials():
    if "google_creds" in st.session_state and st.session_state["google_creds"]:
        return Credentials(**st.session_state["google_creds"])
    return None

def create_google_form(topic, questions):
    creds = get_valid_credentials()
    if not creds:
        raise Exception("Not connected to Google.")

    forms_service = build('forms', 'v1', credentials=creds)
    form_title = f"{topic} - Retrieval Practice"
    
    # Create base form
    form = forms_service.forms().create(body={"info": {"title": form_title}}).execute()
    form_id = form["formId"]
    
    # Make Quiz and add Questions
    batch_requests = [
        {
            "updateSettings": {
                "settings": {"quizSettings": {"isQuiz": True}},
                "updateMask": "quizSettings.isQuiz"
            }
        }
    ]
    
    for i, q in enumerate(questions):
        batch_requests.append({
            "createItem": {
                "item": {
                    "title": q["q"],
                    "description": f"Mark Scheme Guidance:\n{q['a']}",
                    "textItem": {}
                },
                "location": {"index": i}
            }
        })
    
    forms_service.forms().batchUpdate(formId=form_id, body={"requests": batch_requests}).execute()
    return f"https://docs.google.com/forms/d/{form_id}/edit"

# --- 4. SIDEBAR ---
with st.sidebar:
    try:
        st.image("IMG_0202.png", use_container_width=True)
    except Exception:
        pass
    
    st.divider()
    st.title("🔑 Google Integration")
    
    active_creds = get_valid_credentials()
    if active_creds:
        st.success("✅ Connected to Google Drive")
        if st.button("Disconnect", key="logout_btn"):
            st.session_state["google_creds"] = None
            if "code" in st.query_params:
                del st.query_params["code"]
            st.rerun()
    else:
        try:
            flow = get_oauth_flow()
            auth_url, _ = flow.authorization_url(
                prompt='consent',
                access_type='offline',
                include_granted_scopes='true'
            )
            st.link_button("🔑 Connect Google Drive", auth_url, use_container_width=True)
        except Exception as err:
            st.error(f"Config error: {err}")

    st.divider()
    st.title("🎯 Topic Selector")
    level = st.selectbox("Exam Level:", ["GCSE", "A Level"])
    topic = st.text_input("Topic:", placeholder="e.g. Electrolysis")
    num_q = st.slider("Questions:", 1, 10, 5)

# --- 5. MAIN PAGE & ACTIONS ---
st.title("👨🏻‍🏫 Retrieval Practice")

col1, col2, col3, col4 = st.columns([2, 2, 2, 2])

with col1:
    generate_clicked = st.button("🚀 Generate Questions", key="main_gen", type="primary", use_container_width=True)

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
                f"In the Answer section, include a brief 'Common Misconception' tip in brackets if applicable. "
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
            st.error(f"An error occurred: {e}")

# Render options bar & question list if quiz data is present
if st.session_state.quiz_data:
    quiz_len = len(st.session_state.quiz_data)

    if 'revealed_answers' not in st.session_state or len(st.session_state.revealed_answers) != quiz_len:
        st.session_state.revealed_answers = [False] * quiz_len

    all_revealed = all(st.session_state.revealed_answers)
    master_label = "🙈 Hide All Answers" if all_revealed else "👁️ Reveal All Answers"

    with col2:
        if st.button(master_label, key="master_toggle_button", use_container_width=True):
            st.session_state.revealed_answers = [not all_revealed] * quiz_len
            st.rerun()

    with col3:
        if st.button("🖨️ Save as PDF", key="print_pdf_btn", use_container_width=True):
            st.components.v1.html("<script>window.parent.print();</script>", height=0, width=0)

    with col4:
        if get_valid_credentials():
            if st.button("📝 Export to Google Forms", key="export_forms_btn", type="primary", use_container_width=True):
                with st.spinner("Creating Google Form in your Drive..."):
                    try:
                        form_url = create_google_form(
                            st.session_state.get("last_topic", "Retrieval Practice"),
                            st.session_state.quiz_data
                        )
                        st.success(f"Form Created! [Click here to open Form]({form_url})")
                    except Exception as e:
                        st.error(f"Failed to create Google Form: {e}")
        else:
            st.info(" Connect Google Drive in Sidebar to Export")

    st.divider()

    # --- 6. QUESTIONS DISPLAY LOOP ---
    st.subheader(f"Topic: {st.session_state.get('last_topic', 'Retrieval Practice')} ({st.session_state.get('last_level', 'GCSE')})")

    for i, item in enumerate(st.session_state.quiz_data):
        st.markdown('<div class="pdf-card">', unsafe_allow_html=True)
        
        q_text = item['q']
        if is_arabic(q_text):
            st.markdown(f'<div dir="rtl" style="text-align: right;"><h3>Q{i+1}: {q_text}</h3></div>', unsafe_allow_html=True)
        else:
            st.markdown(f"### Q{i+1}: {q_text}")

        is_revealed = st.session_state.revealed_answers[i]
        btn_label = "🙈 Hide Answer" if is_revealed else "👁️ Reveal Answer"
        
        if st.button(f"{btn_label} Q{i+1}", key=f"individual_btn_{i}"):
            st.session_state.revealed_answers[i] = not is_revealed
            st.rerun()

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
