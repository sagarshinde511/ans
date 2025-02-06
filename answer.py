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
    return answer.replace('Answer: ', '').strip()

# Function to calculate similarity
def calculate_similarity(answer1, answer2):
    return fuzz.ratio(str(answer1), str(answer2))

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
st.title("Automated Answer Sheet Grading")
st.sidebar.header("Upload Files")

correct_answers_file = st.sidebar.file_uploader("Upload Correct Answers (Excel)", type=["xlsx"])
student_pdf = st.sidebar.file_uploader("Upload Student Answer Sheet (PDF)", type=["pdf"])

if correct_answers_file and student_pdf:
    # Load correct answers
    correct_answers = pd.read_excel(correct_answers_file)
    
    # Process student answers
    pdf_text = extract_text_from_pdf(student_pdf)
    questions, answers = extract_questions_answers(pdf_text)
    roll_number = extract_roll_number(pdf_text)
    
    student_answers = pd.DataFrame({'Question': questions, 'Answers': answers})
    student_answers[['No', 'Question']] = student_answers['Question'].apply(lambda x: pd.Series(extract_question_number(x)))
    student_answers['Answers'] = student_answers['Answers'].apply(clean_answer_column)
    
    # Merge and compute similarity
    df_merged = pd.merge(student_answers, correct_answers, on='No', suffixes=('_student', '_correct'))
    df_merged['Similarity (%)'] = df_merged.apply(lambda row: calculate_similarity(row['Answers_student'], row['Answers_correct']), axis=1)
    df_merged['Assigned Marks'] = df_merged.apply(lambda row: assign_marks(row['Similarity (%)'], row['Marks']), axis=1)
    
    # Compute total marks
    total_marks_obtained = df_merged['Assigned Marks'].sum()
    total_possible_marks = correct_answers['Marks'].sum()
    
    # Display results
    st.subheader(f"📌 Roll Number: {roll_number}")
    st.write(f"### Total Marks: {total_marks_obtained:.2f} / {total_possible_marks:.2f}")
    st.dataframe(df_merged[['No', 'Question', 'Answers_student', 'Similarity (%)', 'Assigned Marks']])
    
    # Download results
    df_merged.to_csv("graded_answers.csv", index=False)
    st.download_button("Download Results", "graded_answers.csv", "text/csv")
