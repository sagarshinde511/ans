import streamlit as st
import pandas as pd
import fitz  # PyMuPDF for reading PDFs
import re
from rapidfuzz import fuzz

# Function to extract text from PDF
def extract_text_from_pdf(pdf_file):
    doc = fitz.open(stream=pdf_file.read(), filetype="pdf")
    text = ""
    for page in doc:
        text += page.get_text("text") + "\n"
    return text

# Function to extract roll number
def extract_roll_number(text):
    match = re.search(r'Roll Number:\s*(\d+)', text)
    return match.group(1) if match else "Unknown"

# Function to extract questions and answers
def extract_questions_answers(pdf_text):
    lines = pdf_text.split("\n")
    questions, answers = [], []
    current_question, current_answer = None, ""

    for line in lines:
        line = line.strip()
        if line.startswith("Q "):
            if current_question:
                questions.append(current_question)
                answers.append(current_answer.strip())
            current_question = line
            current_answer = ""
        elif current_question:
            current_answer += " " + line

    if current_question:
        questions.append(current_question)
        answers.append(current_answer.strip())
    return questions, answers

# Function to extract question number
def extract_question_number(question):
    match = re.search(r'Q\s?\d+', question)
    if match:
        q_number = match.group(0).replace(" ", "")
        question_text = re.sub(r'Q\s?\d+', '', question).strip()
        return q_number, question_text
    return None, question

# Function to clean answers
def clean_answer_column(answer):
    return str(answer).replace('Answer: ', '').strip() if answer else ""

# Function to calculate similarity
def calculate_similarity(answer1, answer2):
    return fuzz.ratio(str(answer1), str(answer2)) if answer1 and answer2 else 0

# Function to assign marks
def assign_marks(similarity, total_marks):
    if similarity >= 90:
        return total_marks
    elif similarity >= 70:
        return total_marks * 0.75
    elif similarity >= 50:
        return total_marks * 0.50
    else:
        return 0

# Streamlit UI
st.title("📄 Automated Answer Sheet Grading")
st.sidebar.header("📂 Upload Files")

correct_answers_file = st.sidebar.file_uploader("📌 Upload Correct Answers (Excel)", type=["xlsx"])
student_pdf = st.sidebar.file_uploader("📌 Upload Student Answer Sheet (PDF)", type=["pdf"])

if correct_answers_file and student_pdf:
    try:
        # Load correct answers
        correct_answers = pd.read_excel(correct_answers_file)
        
        # Process student answers
        pdf_text = extract_text_from_pdf(student_pdf)
        questions, answers = extract_questions_answers(pdf_text)
        roll_number = extract_roll_number(pdf_text)
        
        student_answers = pd.DataFrame({'Question': questions, 'Answers': answers})
        student_answers[['No', 'Question']] = student_answers['Question'].apply(lambda x: pd.Series(extract_question_number(x)))
        student_answers['Answers'] = student_answers['Answers'].apply(clean_answer_column)

        # Ensure 'No' column exists in correct answers
        if 'No' not in correct_answers.columns:
            st.error("❌ The uploaded correct answers file is missing a 'No' column.")
        else:
            # Merge and compute similarity
            df_merged = pd.merge(student_answers, correct_answers, on='No', suffixes=('_student', '_correct'), how="inner")

            # Handle missing columns gracefully
            if "Answers_student" not in df_merged.columns:
                df_merged.rename(columns={"Answers": "Answers_student"}, inplace=True)

            df_merged['Similarity (%)'] = df_merged.apply(
                lambda row: calculate_similarity(row.get('Answers_student', ''), row.get('Answers_correct', '')),
                axis=1
            )
            df_merged['Assigned Marks'] = df_merged.apply(
                lambda row: assign_marks(row['Similarity (%)'], row['Marks']),
                axis=1
            )

            # Compute total marks
            total_marks_obtained = df_merged['Assigned Marks'].sum()
            total_possible_marks = correct_answers['Marks'].sum()

            # Display results
            st.subheader(f"📌 Roll Number: {roll_number}")
            st.write(f"### ✅ Total Marks: {total_marks_obtained:.2f} / {total_possible_marks:.2f}")

            # Ensure only available columns are displayed
            columns_to_display = ['No', 'Question', 'Answers_student', 'Similarity (%)', 'Assigned Marks']
            available_columns = [col for col in columns_to_display if col in df_merged.columns]
            st.dataframe(df_merged[available_columns])

            # Save and download results
            output_file = "graded_answers.csv"
            df_merged.to_csv(output_file, index=False)
            st.download_button("⬇️ Download Results", data=open(output_file, "rb"), file_name="graded_answers.csv", mime="text/csv")
    
    except Exception as e:
        st.error(f"🚨 Error processing files: {e}")
