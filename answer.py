import streamlit as st
import pandas as pd
import fitz  # PyMuPDF for reading PDFs
import re
from rapidfuzz import fuzz
import os

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


# Function to process a single student's PDF and evaluate answers
def process_student_pdf(correct_answers_file, student_pdf):
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
            return None
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

            return roll_number, df_merged, total_marks_obtained, total_possible_marks

    except Exception as e:
        st.error(f"🚨 Error processing files: {e}")
        return None

# Main Streamlit function to handle multiple PDFs
def main():
    # File upload inputs
    correct_answers_file = st.file_uploader("Upload Correct Answers File", type="xlsx")
    student_pdfs = st.file_uploader("Upload Student PDF Files", type="pdf", accept_multiple_files=True)

    if correct_answers_file and student_pdfs:
        all_results = []

        # Process each student PDF
        for student_pdf in student_pdfs:
            result = process_student_pdf(correct_answers_file, student_pdf)
            if result:
                roll_number, df_merged, total_marks_obtained, total_possible_marks = result
                all_results.append({
                    "Roll Number": roll_number,
                    "Total Marks Obtained": total_marks_obtained,
                    "Total Possible Marks": total_possible_marks,
                    "Details": df_merged
                })

        # Display results for all students
        for result in all_results:
            st.subheader(f"📌 Roll Number: {result['Roll Number']}")
            st.write(f"### ✅ Total Marks: {result['Total Marks Obtained']:.2f} / {result['Total Possible Marks']:.2f}")
            st.dataframe(result["Details"])

            # Save and download individual results
            output_file = f"{result['Roll Number']}_graded_answers.csv"
            result["Details"].to_csv(output_file, index=False)
            st.download_button(f"⬇️ Download Results for {result['Roll Number']}", data=open(output_file, "rb"), file_name=output_file, mime="text/csv")

if __name__ == "__main__":
    main()
