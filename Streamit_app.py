import streamlit as st
import google.generativeai as genai
import re
import requests
import json
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

# --- 3. DIRECT GOOGLE OAUTH HANDLER ---
SCOPES = [
    'https://www.googleapis.com/auth/forms.body',
    'https://www.googleapis.com/auth/drive.file'
]

CLIENT_ID = st.secrets["google_oauth"]["client_id"]
CLIENT_SECRET = st.secrets["google_oauth"]["client_secret"]
REDIRECT_URI = st.secrets["google_oauth"]["redirect_uri"]

def get_auth_url():
    scope_str = "%20".join(SCOPES)
    return (
        f"https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id={CLIENT_ID}&"
        f"redirect_uri={REDIRECT_URI}&"
        f"response_type=code&"
        f"scope={scope_str}&"
        f"access_type=offline&"
        f"prompt=consent"
    )

def exchange_code_for_tokens(auth_code):
    token_url = "https://oauth2.googleapis.com/token"
    payload = {
        "code": auth_code,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code",
    }
    res = requests.post(token_url, data=payload)
    if res.status_code == 200:
        return res.json()
    else:
        raise Exception(f"Token exchange failed: {res.text}")

# PERSISTENT CREDENTIAL RECOVERY
if "google_creds" not in st.session_state:
    st.session_state.google_creds = None

if not st.session_state.google_creds and "code" in st.query_params:
    try:
        auth_code = st.query_params["code"]
        tokens = exchange_code_for_tokens(auth_code)
        
        st.session_state.google_creds = {
            'token': tokens.get('access_token'),
            'refresh_token': tokens.get('refresh_token'),
            'token_uri': "https://oauth2.googleapis.com/token",
            'client_id': CLIENT_ID,
            'client_secret': CLIENT_SECRET,
            'scopes': SCOPES
        }
        st.query_params.clear()
        st.rerun()
    except Exception as e:
        st.error(f"Authentication Error: {e}")

def get_valid_credentials():
    if st.session_state.google_creds and st.session_state.google_creds.get('token'):
        return Credentials(**st.session_state.google_creds)
    return None

# --- 4. GOOGLE FORM QUIZ CREATOR WITH AUTOMATIC GRADING ---
def create_google_form(topic, questions):
    creds = get_valid_credentials()
    if not creds:
        raise Exception("Not connected to Google Account.")

    forms_service = build('forms', 'v1', credentials=creds)
    form_title = f"{topic} - Multiple Choice Quiz"
    
    # Create base form
    form = forms_service.forms().create(body={"info": {"title": form_title}}).execute()
    form_id = form["formId"]
    
    # 1. Turn on Quiz Mode
    batch_requests = [
        {
            "updateSettings": {
                "settings": {"quizSettings": {"isQuiz": True}},
                "updateMask": "quizSettings.isQuiz"
            }
        }
    ]
    
    # 2. Add Multiple Choice items with Answer Keys
    for i, q in enumerate(questions):
        # Format options structure
        option_objs = [{"value": opt} for opt in q["options"]]
        
        item_request = {
            "createItem": {
                "item": {
                    "title": q["q"],
                    "questionItem": {
                        "question": {
                            "required": True,
                            "grading": {
                                "pointValue": 1,
                                "correctAnswers": {
                                    "answers": [{"value": q["correct_option"]}]
                                },
                                "generalFeedback": {
                                    "text": f"Mark Scheme Guidance: {q['explanation']}"
                                }
                            },
                            "choiceQuestion": {
                                "type": "RADIO",
                                "options": option_objs,
                                "shuffle": True
                            }
                        }
                    }
                },
                "location": {"index": i}
            }
        }
        batch_requests.append(item_request)
    
    forms_service.forms().batchUpdate(formId=form_id, body={"requests": batch_requests}).execute()
    return f"https://docs.google.com/forms/d/{form_id}/edit"

# --- 5. SIDEBAR ---
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
            st.session_state.google_creds = None
            st.rerun()
    else:
        st.link_button("🔑 Connect Google Drive", get_auth_url(), use_container_width=True)

    st.divider()
    st.title("🎯 Topic Selector")
    level = st.selectbox("Exam Level:", ["GCSE", "A Level"])
    topic = st.text_input("Topic:", placeholder="e.g. Electrolysis")
    num_q = st.slider("Questions:", 1, 10, 5)

# --- 6. MAIN PAGE & ACTIONS ---
st.title("👨🏻‍🏫 Self-Marking Quiz Generator")

col1, col2, col3, col4 = st.columns([2, 2, 2, 2])

with col1:
    generate_clicked = st.button("🚀 Generate Quiz", key="main_gen", type="primary", use_container_width=True)

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
                f"Create {num_q} multiple choice retrieval questions for the {level} {topic} topic, "
                f"strictly following the Edexcel specification.\n\n"
                f"Return ONLY a raw JSON array containing objects with the following schema, with no markdown formatting or backticks:\n"
                f"[\n"
                f"  {{\n"
                f'    "question": "Question text",\n'
                f'    "options": ["Option 1", "Option 2", "Option 3", "Option 4"],\n'
                f'    "correct_option": "Exact matching string from options array",\n'
                f'    "explanation": "Brief Edexcel mark scheme explanation"\n'
                f"  }}\n"
                f"]"
            )
           
            with st.spinner("Generating self-marking questions..."):
                response = model.generate_content(prompt)
                raw_text = response.text.strip()
                
                # Clean markdown wrapper if present
                if raw_text.startswith("```json"):
                    raw_text = raw_text[7:]
                if raw_text.startswith("```"):
                    raw_text = raw_text[3:]
                if raw_text.endswith("```"):
                    raw_text = raw_text[:-3]
                
                quiz_json = json.loads(raw_text.strip())
                
                new_quiz = []
                for q in quiz_json:
                    new_quiz.append({
                        "q": q["question"],
                        "options": q["options"],
                        "correct_option": q["correct_option"],
                        "explanation": q["explanation"]
                    })
               
                if new_quiz:
                    st.session_state.quiz_data = new_quiz
                    st.session_state.last_level = level
                    st.session_state.last_topic = topic
                    st.session_state.revealed_answers = [False] * len(new_quiz)
                    st.rerun()
                else:
                    st.error("The AI response was empty. Please try again.")
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
                with st.spinner("Creating Self-Marking Google Quiz..."):
                    try:
                        form_url = create_google_form(
                            st.session_state.get("last_topic", "Retrieval Practice"),
                            st.session_state.quiz_data
                        )
                        st.success(f"Self-Marking Quiz Created! [Click here to open Form]({form_url})")
                    except Exception as e:
                        st.error(f"Failed to create Google Form: {e}")
        else:
            st.info(" Connect Google Drive in Sidebar to Export")

    st.divider()

    # --- 7. QUESTIONS DISPLAY LOOP ---
    st.subheader(f"Topic: {st.session_state.get('last_topic', 'Retrieval Practice')} ({st.session_state.get('last_level', 'GCSE')})")

    for i, item in enumerate(st.session_state.quiz_data):
        st.markdown('<div class="pdf-card">', unsafe_allow_html=True)
        
        q_text = item['q']
        if is_arabic(q_text):
            st.markdown(f'<div dir="rtl" style="text-align: right;"><h3>Q{i+1}: {q_text}</h3></div>', unsafe_allow_html=True)
        else:
            st.markdown(f"### Q{i+1}: {q_text}")

        # Render options list
        for opt in item['options']:
            if opt == item['correct_option']:
                st.markdown(f"- **{opt}** *(Correct Answer)*")
            else:
                st.markdown(f"- {opt}")

        st.markdown("<br>", unsafe_allow_html=True)
        is_revealed = st.session_state.revealed_answers[i]
        btn_label = "🙈 Hide Guidance" if is_revealed else "👁️ Reveal Guidance"
        
        if st.button(f"{btn_label} Q{i+1}", key=f"individual_btn_{i}"):
            st.session_state.revealed_answers[i] = not is_revealed
            st.rerun()

        if st.session_state.revealed_answers[i]:
            st.write("**Mark Scheme / Feedback:**")
            st.info(item['explanation'])
                
        st.markdown('</div>', unsafe_allow_html=True)
        st.divider()

else:
    st.divider()
    st.info("👈 Enter a topic in the sidebar and click 'Generate Quiz' to start.")
