import streamlit as st
import google.generativeai as genai
import re
import requests
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# --- 1. PAGE CONFIG & STYLING ---
st.set_page_config(page_title="Retrieval Practice Pro", layout="wide", page_icon="✅")

st.markdown("""
    <style>
    /* Standard Screen Styling */
    .stButton > button {
        height: 40px !important;
        font-size: 14px !important;
        font-weight: 500 !important;
        border-radius: 8px !important;
    }
    .question-card {
        border: 1px solid #cbd5e1 !important;
        background-color: #ffffff !important;
        padding: 16px 20px !important;
        margin-bottom: 16px !important;
        border-radius: 8px !important;
    }

    /* --- PRINT STYLING (Applies ONLY when saving to PDF) --- */
    @media print {
        /* Hide sidebar, buttons, and Streamlit header chrome */
        section[data-testid="stSidebar"],
        header,
        footer,
        .stButton,
        [data-testid="stHeader"] {
            display: none !important;
        }

        /* Ensure main page content uses full print width */
        .main .block-container {
            max-width: 100% !important;
            padding: 0 !important;
        }

        /* Prevent question cards from splitting awkwardly across page breaks */
        .question-card {
            page-break-inside: avoid;
        }

        /* Force ALL answer boxes to render on the printed PDF */
        .answer-box {
            display: block !important;
        }
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. INITIALIZE SESSION STATE ---
if "quiz_data" not in st.session_state:
    st.session_state.quiz_data = []

api_key = st.secrets.get("GEMINI_API_KEY", "")

def is_arabic(text):
    return bool(re.search(r'[\u0600-\u06FF]', text))

def clean_latex_for_forms(text):
    """
    Converts LaTeX math commands, fractions, and symbols into clean native 
    Unicode characters suitable for Google Forms text fields.
    """
    if not text:
        return text
    
    cleaned = text

    # Convert basic LaTeX fractions like \frac{a}{b} -> (a/b)
    cleaned = re.sub(r'\\frac\{([^}]+)\}\{([^}]+)\}', r'(\1/\2)', cleaned)
    
    # Superscripts & Subscripts mapping
    sub_map = str.maketrans("0123456789+-=()abcdefghijklmnopqrstuvwxyz", 
                            "₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎ₐᵦcdₑfgₕᵢⱼₖₗₘₙₒₚqᵣₛₜᵤᵥwₓy₂")
    sup_map = str.maketrans("0123456789+-=()abcdefghijklmnopqrstuvwxyz", 
                            "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ᵃᵇᶜᵈᵉᶠᵍʰⁱʲᵏˡᵐⁿᵒᵖqʳˢᵗᵘᵛʷˣʸᶻ")

    # Handle _{subscript} or _x
    cleaned = re.sub(r'_\{([^}]+)\}', lambda m: m.group(1).translate(sub_map), cleaned)
    cleaned = re.sub(r'_([0-9a-z])', lambda m: m.group(1).translate(sub_map), cleaned)

    # Handle ^{superscript} or ^x
    cleaned = re.sub(r'\^\{([^}]+)\}', lambda m: m.group(1).translate(sup_map), cleaned)
    cleaned = re.sub(r'\^([0-9a-z])', lambda m: m.group(1).translate(sup_map), cleaned)

    # Comprehensive LaTeX Symbol Replacements
    latex_replacements = {
        r'\times': '×',
        r'\div': '÷',
        r'\pm': '±',
        r'\mp': '∓',
        r'\degree': '°',
        r'\circ': '°',
        r'\rightarrow': '→',
        r'\leftarrow': '←',
        r'\Rightarrow': '⇒',
        r'\Leftarrow': '⇐',
        r'\Delta': 'Δ',
        r'\delta': 'δ',
        r'\theta': 'θ',
        r'\pi': 'π',
        r'\alpha': 'α',
        r'\beta': 'β',
        r'\gamma': 'γ',
        r'\lambda': 'λ',
        r'\mu': 'μ',
        r'\omega': 'ω',
        r'\Omega': 'Ω',
        r'\infty': '∞',
        r'\approx': '≈',
        r'\neq': '≠',
        r'\leq': '≤',
        r'\geq': '≥',
        r'\sqrt': '√',
        r'\cdot': '·'
    }

    for latex_cmd, unicode_char in latex_replacements.items():
        cleaned = cleaned.replace(latex_cmd, unicode_char)

    # Remove remaining LaTeX dollar delimiters ($E=mc^2$ -> E=mc²)
    cleaned = re.sub(r'\$+(.*?)\$+', r'\1', cleaned)

    return cleaned.strip()

# --- 3. DIRECT GOOGLE OAUTH HANDLER ---
SCOPES = [
    'https://www.googleapis.com/auth/forms.body',
    'https://www.googleapis.com/auth/drive.file'
]

CLIENT_ID = st.secrets["google_oauth"]["client_id"]
CLIENT_SECRET = st.secrets["google_oauth"]["client_secret"]
REDIRECT_URI = st.secrets["google_oauth"]["redirect_uri"]

def get_auth_url():
    """Generates pure OAuth URL without PKCE dependency."""
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
    """Exchanges return code directly via HTTP POST."""
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

# Catch ?code= from Google redirect
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

# --- 4. GOOGLE DRIVE & FORMS FUNCTIONS ---
def get_or_create_folder(drive_service, folder_name="Retrieval Practice Quizzes"):
    """Finds an existing folder by name or creates a new one in Google Drive."""
    query = f"name = '{folder_name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    response = drive_service.files().list(q=query, fields="files(id, name)").execute()
    folders = response.get('files', [])

    if folders:
        return folders[0]['id']
    else:
        folder_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder'
        }
        folder = drive_service.files().create(body=folder_metadata, fields='id').execute()
        return folder['id']

def create_google_form(topic, questions):
    creds = get_valid_credentials()
    if not creds:
        raise Exception("Not connected to Google Account.")

    forms_service = build('forms', 'v1', credentials=creds)
    drive_service = build('drive', 'v3', credentials=creds)

    form_title = f"{topic} - Retrieval Practice"
    
    # 1. Create base Google Form
    form = forms_service.forms().create(body={"info": {"title": form_title}}).execute()
    form_id = form["formId"]
    
    # 2. Configure Form Settings: Enable Quiz
    batch_requests = [
        {
            "updateSettings": {
                "settings": {
                    "quizSettings": {
                        "isQuiz": True
                    }
                },
                "updateMask": "quizSettings.isQuiz"
            }
        }
    ]
    
    # 3. Add open-ended practice questions
    for i, q in enumerate(questions):
        clean_q = clean_latex_for_forms(q["q"])
        clean_a = clean_latex_for_forms(q["a"])

        batch_requests.append({
            "createItem": {
                "item": {
                    "title": f"Q{i+1}: {clean_q}",
                    "questionItem": {
                        "question": {
                            "required": True,
                            "grading": {
                                "generalFeedback": {
                                    "text": f"OFFICIAL MARK SCHEME:\n{clean_a}"
                                }
                            },
                            "textQuestion": {
                                "paragraph": True
                            }
                        }
                    }
                },
                "location": {"index": i}
            }
        })

    # 4. Streamlined Self-Assessment Grid with Embedded Instructions
    total_q_count = len(questions)
    
    grid_rows = [{"title": f"Question {i+1}"} for i in range(total_q_count)]
    grid_cols = [{"value": "Earned Mark"}, {"value": "Incorrect / No Mark"}]
    
    batch_requests.append({
        "createItem": {
            "item": {
                "title": f"FINAL STEP — Self-Assessment Grid (Total Marks: {total_q_count})",
                "description": (
                    "📋 INSTRUCTION GUIDE FOR STUDENTS:\n\n"
                    "1. On FIRST submission: Complete questions 1 to " + str(total_q_count) + ", leave this section blank, and click SUBMIT.\n"
                    "2. Click 'View score' on the confirmation page to review the Mark Scheme for each question.\n"
                    "3. Re-open/edit your response and evaluate your work in the grid below:\n"
                    "   • Select 'Earned Mark' if your answer matched the key scheme points.\n"
                    "   • Select 'Incorrect / No Mark' if key elements were missing.\n"
                    "4. Submit the form again to send your score to Google Classroom."
                ),
                "questionGroupItem": {
                    "questions": [
                        {
                            "required": False,
                            "rowQuestion": {
                                "title": row["title"]
                            },
                            "grading": {
                                "pointValue": 1,
                                "correctAnswers": {
                                    "answers": [{"value": "Earned Mark"}]
                                }
                            }
                        } for row in grid_rows
                    ],
                    "grid": {
                        "columns": {
                            "type": "RADIO",
                            "options": grid_cols
                        }
                    }
                }
            },
            "location": {"index": total_q_count}
        }
    })

    # Execute Batch Request
    forms_service.forms().batchUpdate(formId=form_id, body={"requests": batch_requests}).execute()

    # 5. Move the created form into the target Drive folder
    try:
        folder_id = get_or_create_folder(drive_service, folder_name="Retrieval Practice Quizzes")
        file = drive_service.files().get(fileId=form_id, fields='parents').execute()
        previous_parents = ",".join(file.get('parents', []))
        
        drive_service.files().update(
            fileId=form_id,
            addParents=folder_id,
            removeParents=previous_parents,
            fields='id, parents'
        ).execute()
    except Exception as err:
        st.warning(f"Form created, but failed to move to folder: {err}")

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
                with st.spinner("Creating Google Form in your Drive folder..."):
                    try:
                        form_url = create_google_form(
                            st.session_state.get("last_topic", "Retrieval Practice"),
                            st.session_state.quiz_data
                        )
                        st.success(f"Form Created in 'Retrieval Practice Quizzes' folder! [Click here to open Form]({form_url})")
                    except Exception as e:
                        st.error(f"Failed to create Google Form: {e}")
        else:
            st.info(" Connect Google Drive in Sidebar to Export")

    st.markdown("<br>", unsafe_allow_html=True)

    # --- 7. QUESTIONS DISPLAY LOOP ---
    st.subheader(f"Topic: {st.session_state.get('last_topic', 'Retrieval Practice')} ({st.session_state.get('last_level', 'GCSE')})")

    for i, item in enumerate(st.session_state.quiz_data):
        q_text = item['q']
        a_text = item['a']
        is_revealed = st.session_state.revealed_answers[i]
        btn_label = "🙈 Hide Answer" if is_revealed else "👁️ Reveal Answer"

        st.markdown('<div class="question-card">', unsafe_allow_html=True)
        
        if is_arabic(q_text):
            st.markdown(f'<div dir="rtl" style="text-align: right;"><h3>Q{i+1}: {q_text}</h3></div>', unsafe_allow_html=True)
        else:
            st.markdown(f"### Q{i+1}: {q_text}")

        if st.button(f"{btn_label} Q{i+1}", key=f"individual_btn_{i}"):
            st.session_state.revealed_answers[i] = not is_revealed
            st.rerun()

        # Display block toggle on screen, automatically forced to 'block' in PDF export
        display_style = "block" if is_revealed else "none"
        
        if is_arabic(a_text):
            st.markdown(f'''
                <div class="answer-box" style="display: {display_style};">
                    <br><b>Mark Scheme / Guidance:</b>
                    <div dir="rtl" style="text-align: right; background-color: #eff6ff; padding: 12px; border-radius: 6px; border-right: 4px solid #004b95;">{a_text}</div>
                </div>
            ''', unsafe_allow_html=True)
        else:
            st.markdown(f'''
                <div class="answer-box" style="display: {display_style};">
                    <br><b>Mark Scheme / Guidance:</b>
                    <div style="background-color: #f0fdf4; padding: 12px; border-radius: 6px; border-left: 4px solid #16a34a; color: #166534;">{a_text}</div>
                </div>
            ''', unsafe_allow_html=True)
                
        st.markdown('</div>', unsafe_allow_html=True)

else:
    st.divider()
    st.info("👈 Enter a topic in the sidebar and click 'Generate Questions' to start.")
