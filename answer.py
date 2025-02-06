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
    match = re.search(r'Q\s?(\d+)', question)
    if match:
        q_number = match.group(1)
        question_text = re.sub(r'Q\s?\d+', '', question).strip()
        return q_number, question_text
    return "Unknown", question

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

correct_answers_file = st.file_uploader("📌 Upload Correct Answers (Excel)", type=["xlsx"])
student_pdfs = st.file_uploader("📌 Upload Student Answer Sheets (PDF)", type=["pdf"], accept_multiple_files=True)

if correct_answers_file and student_pdfs:
    try:
        # Load correct answers
        correct_answers = pd.read_excel(correct_answers_file)
        
        # Ensure 'No' column is present in correct answers file
        if 'No' not in correct_answers.columns:
            st.error("❌ The uploaded correct answers file is missing a 'No' column.")
        
        all_results = []

        for student_pdf in student_pdfs:
            pdf_text = extract_text_from_pdf(student_pdf)
            questions, answers = extract_questions_answers(pdf_text)
            roll_number = extract_roll_number(pdf_text)
            
            student_answers = pd.DataFrame({'Question': questions, 'Answers': answers})
            
            # Debugging step to check if questions and answers are extracted properly
            st.write("Extracted Questions and Answers:", student_answers.head())
            
            # Extract question number and question text
            student_answers[['No', 'Question']] = student_answers['Question'].apply(lambda x: pd.Series(extract_question_number(x)))
            
            # Debugging step to check if the 'No' and 'Question' columns are created correctly
            st.write("After Extracting Question Numbers:", student_answers.head())
            
            student_answers['Answers'] = student_answers['Answers'].apply(clean_answer_column)
            
            # Debugging step to check before merging
            st.write("Student Answers DataFrame:", student_answers.head())
            st.write("Correct Answers DataFrame:", correct_answers.head())

            # Merge student answers with correct answers
            df_merged = pd.merge(student_answers, correct_answers, on='No', suffixes=('_student', '_correct'), how="inner")
            
            if "Answers_student" not in df_merged.columns:
                df_merged.rename(columns={"Answers": "Answers_student"}, inplace=True)
            
            # Calculate similarity and assign marks
            df_merged['Similarity (%)'] = df_merged.apply(
                lambda row: calculate_similarity(row.get('Answers_student', ''), row.get('Answers_correct', '')),
                axis=1
            )
            df_merged['Assigned Marks'] = df_merged.apply(
                lambda row: assign_marks(row['Similarity (%)'], row['Marks']),
                axis=1
            )

            # Calculate total marks
            total_marks_obtained = df_merged['Assigned Marks'].sum()
            total_possible_marks = correct_answers['Marks'].sum()
            df_merged['Roll Number'] = roll_number
            df_merged['Total Marks'] = total_marks_obtained
            
            all_results.append(df_merged[['Roll Number', 'No', 'Question', 'Answers_student', 'Similarity (%)', 'Assigned Marks']])

        # Combine all student results
        final_results = pd.concat(all_results, ignore_index=True)
        
        st.subheader("📌 Consolidated Results")
        st.dataframe(final_results)

        output_file = "graded_answers_all.csv"
        final_results.to_csv(output_file, index=False)
        st.download_button("⬇️ Download Consolidated Results", data=open(output_file, "rb"), file_name="graded_answers_all.csv", mime="text/csv")
    
    except Exception as e:
        st.error(f"🚨 Error processing files: {e}")
