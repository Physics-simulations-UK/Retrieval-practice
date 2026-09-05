import os
import re
import streamlit as st
import google.generativeai as genai
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# ------------------------------------------------------------------------------
# CONFIGURATION & CONSTANTS
# ------------------------------------------------------------------------------
SCOPES = [
    'https://www.googleapis.com/auth/forms.body',
    'https://www.googleapis.com/auth/drive.file'
]

st.set_page_config(
    page_title="Edexcel Retrieval Practice Generator",
    page_icon="📝",
    layout="wide"
)

# Initialize Session States
if "quiz_data" not in st.session_state:
    st.session_state.quiz_data = []
if "revealed_answers" not in st.session_state:
    st.session_state.revealed_answers = []
if "last_level" not in st.session_state:
    st.session_state.last_level = ""
if "last_topic" not in st.session_state:
    st.session_state.last_topic = ""

# ------------------------------------------------------------------------------
# HELPER FUNCTIONS
# ------------------------------------------------------------------------------
def clean_latex_for_forms(text: str) -> str:
    """Converts LaTeX math notation ($...$) into readable plain text for Google Forms."""
    if not text:
        return ""
    # Strip basic inline LaTeX delimiters
    cleaned = re.sub(r'\$(.*?)\$', r'\1', text)
    cleaned = cleaned.replace('\\times', '×').replace('\\div', '÷').replace('\\pm', '±')
    return cleaned.strip()

def get_valid_credentials():
    """Handles OAuth2 Desktop client flow for Google Forms/Drive API."""
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists('credentials.json'):
                st.error("Missing `credentials.json` for Google OAuth API authentication.")
                return None
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
            
    return creds

def get_or_create_folder(drive_service, folder_name="Retrieval Practice Quizzes"):
    """Finds or creates a Google Drive folder to store generated Forms."""
    query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    results = drive_service.files().list(q=query, fields="files(id, name)").execute()
    items = results.get('files', [])
    
    if items:
        return items[0]['id']
    else:
        file_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder'
        }
        folder = drive_service.files().create(body=file_metadata, fields='id').execute()
        return folder.get('id')

def create_google_form(topic: str, questions: list) -> str:
    """
    Creates a Google Form Quiz with:
    1. Paragraph text fields for student practice.
    2. Mark Scheme guidance embedded in question feedback.
    3. Weighted Answer Key on the final self-assessment question for Grade Import.
    """
    creds = get_valid_credentials()
    if not creds:
        raise Exception("Failed to authenticate with Google Account.")

    forms_service = build('forms', 'v1', credentials=creds)
    drive_service = build('drive', 'v3', credentials=creds)

    form_title = f"{topic} - Retrieval Practice"
    
    # 1. Create Base Form
    form = forms_service.forms().create(body={"info": {"title": form_title}}).execute()
    form_id = form["formId"]
    
    # 2. Enable Quiz Settings
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
    
    # 3. Append Open-Ended Practice Questions
    for i, q in enumerate(questions):
        clean_q = clean_latex_for_forms(q["q"])
        clean_a = clean_latex_for_forms(q["a"])

        batch_requests.append({
            "createItem": {
                "item": {
                    "title": f"Q{i+1}. {clean_q}",
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

    # 4. Append Self-Assessment Question with Answer Keys mapped to point values
    total_q_count = len(questions)
    score_options = [{"value": f"{score} / {total_q_count}"} for score in range(total_q_count + 1)]

    batch_requests.append({
        "createItem": {
            "item": {
                "title": f"FINAL STEP — Self-Assessed Score (out of {total_q_count})",
                "description": (
                    "INSTRUCTIONS FOR GRADE REGISTRATION:\n"
                    "1. On FIRST submission, leave this question blank and click Submit.\n"
                    "2. Click 'View score' on your screen to review your answers against the Mark Scheme.\n"
                    "3. Click 'Edit your response' (or re-open the Form link) to return to this question.\n"
                    "4. Select the total score you earned and submit again to register your score in Google Classroom."
                ),
                "questionItem": {
                    "question": {
                        "required": False,
                        "grading": {
                            "pointValue": total_q_count,
                            "correctAnswers": {
                                "answers": [{"value": f"{score} / {total_q_count}"} for score in range(total_q_count + 1)]
                            }
                        },
                        "choiceQuestion": {
                            "type": "RADIO",
                            "options": score_options
                        }
                    }
                }
            },
            "location": {"index": total_q_count}
        }
    })
    
    # Batch update the Google Form
    forms_service.forms().batchUpdate(formId=form_id, body={"requests": batch_requests}).execute()

    # 5. Relocate Form into standard Drive Folder
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
        st.warning(f"Form created successfully, but could not be moved to subfolder: {err}")

    return f"https://docs.google.com/forms/d/{form_id}/edit"

# ------------------------------------------------------------------------------
# STREAMLIT UI LAYOUT
# ------------------------------------------------------------------------------
st.title("📝 Edexcel Retrieval Practice Generator")

# Sidebar Configuration
with st.sidebar:
    st.header("Settings")
    api_key = st.text_input("Gemini API Key", type="password", help="Enter your Google AI Studio API key.")
    if not api_key and "GEMINI_API_KEY" in st.secrets:
        api_key = st.secrets["GEMINI_API_KEY"]

    level = st.selectbox("Qualification Level", ["GCSE", "A-Level", "IGCSE"])
    num_q = st.slider("Number of Questions", min_value=3, max_value=10, value=5)

topic = st.text_input("Enter Topic (e.g., 'GCSE Physics - Specific Heat Capacity')", "")
generate_clicked = st.button("Generate Questions", type="primary")

# ------------------------------------------------------------------------------
# QUESTION GENERATION LOGIC (STREAMING)
# ------------------------------------------------------------------------------
if generate_clicked:
    if not api_key:
        st.error("API Key missing! Please enter it in the sidebar or st.secrets.")
    elif not topic:
        st.warning("Please enter a topic first.")
    else:
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-1.5-flash')
            
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
                response = model.generate_content(prompt, stream=True)
                
                raw_text = ""
                for chunk in response:
                    raw_text += chunk.text
                
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
                    st.error("The AI response could not be parsed properly. Please try generating again.")
        except Exception as e:
            st.error(f"Error during generation: {e}")

# ------------------------------------------------------------------------------
# DISPLAY QUESTIONS & GOOGLE FORM CREATION
# ------------------------------------------------------------------------------
if st.session_state.quiz_data:
    st.subheader(f"Generated Questions ({st.session_state.last_level}: {st.session_state.last_topic})")
    
    for idx, item in enumerate(st.session_state.quiz_data):
        with st.container():
            st.markdown(f"**Q{idx+1}:** {item['q']}")
            
            # Answer Toggle Button
            if st.button(f"Show/Hide Answer #{idx+1}", key=f"btn_{idx}"):
                st.session_state.revealed_answers[idx] = not st.session_state.revealed_answers[idx]
                
            if st.session_state.revealed_answers[idx]:
                st.info(f"**Mark Scheme:** {item['a']}")
            st.divider()

    # Google Form Export Button
    if st.button("Export Quiz to Google Forms", type="secondary"):
        with st.spinner("Creating Google Form and setting up Grade Import keys..."):
            try:
                form_url = create_google_form(st.session_state.last_topic, st.session_state.quiz_data)
                st.success("Google Form Quiz created successfully!")
                st.markdown(f"👉 **[Click here to open and edit your Google Form]({form_url})**")
            except Exception as e:
                st.error(f"Failed to create Google Form: {e}")
