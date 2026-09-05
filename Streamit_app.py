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
    
    # 3. Add open-ended practice questions (0 points each)
    for i, q in enumerate(questions):
        clean_q = clean_latex_for_forms(q["q"])
        clean_a = clean_latex_for_forms(q["a"])

        batch_requests.append({
            "createItem": {
                "item": {
                    "title": clean_q,
                    "questionItem": {
                        "question": {
                            "required": True,
                            "grading": {
                                "generalFeedback": {
                                    "text": f"Mark Scheme Guidance:\n{clean_a}"
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

    # 4. Add Self-Assessment Question with GRADED point keys for Classroom import
    total_q_count = len(questions)
    
    # Create graded choices mapping: Each selection (e.g. "3 / 5") awards its numeric value
    # In Google Forms API, assigning pointValue to the question ensures the selected choice populates the grade.
    batch_requests.append({
        "createItem": {
            "item": {
                "title": f"FINAL STEP — Self-Assessed Score (out of {total_q_count})",
                "description": (
                    "STEPS TO COMPLETE YOUR GRADE:\n"
                    "1. On FIRST submission, leave this blank and click Submit.\n"
                    "2. Click 'View score' on the screen to review the Mark Scheme.\n"
                    "3. Open the Form link again or click 'Edit your response' to select your mark.\n"
                    "4. Submit the form again so your grade registers in Classroom."
                ),
                "questionItem": {
                    "question": {
                        "required": False,
                        "grading": {
                            "pointValue": total_q_count  # Total possible score for Google Classroom
                        },
                        "choiceQuestion": {
                            "type": "RADIO",
                            "options": [
                                {"value": f"{score} / {total_q_count}"} for score in range(total_q_count + 1)
                            ]
                        }
                    }
                }
            },
            "location": {"index": total_q_count}
        }
    })
    
    forms_service.forms().batchUpdate(formId=form_id, body={"requests": batch_requests}).execute()

    # 5. Move created form into target Drive folder
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
