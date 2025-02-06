import streamlit as st
import pandas as pd
import fitz  # PyMuPDF for reading PDFs
import re
from rapidfuzz import fuzz
import os
import mysql.connector

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

def insert_student_result(roll_number, marks):
    cursor = None  # Initialize cursor to None
    try:
        # Connect to the database
        connection = mysql.connector.connect(
            host="82.180.143.66",
            user="u263681140_students",
            password="testStudents@123",
            database="u263681140_students"
        )
        
        # Create a cursor object
        cursor = connection.cursor()
        
        # SQL query to insert data
        query = """
        INSERT INTO StudentResult (RollNumber, Subject, Marks) 
        VALUES (%s, %s, %s)
        """
        subject = "Cloud Computing"  # Set default subject
        marks = int(marks)
        # Prepare the data to be inserted
        data = (roll_number, "Cloud Computing", marks)

        # Execute the query
        cursor.execute(query, data)

        # Commit the transaction
        connection.commit()
        st.write(f"Data inserted for Roll Number {roll_number}")

    except mysql.connector.Error as err:
        st.write(f"Error: {err}")
    finally:
        # Close the cursor and connection only if cursor was created
        if cursor:
            cursor.close()
        if connection:
            connection.close()
def read_student_results():
    try:
        # Connect to the database
        connection = mysql.connector.connect(
            host="82.180.143.66",
            user="u263681140_students",
            password="testStudents@123",
            database="u263681140_students"
        )
        
        # Create a cursor object
        cursor = connection.cursor()

        # SQL query to select all data from StudentResult table
        query = "SELECT * FROM StudentResult"

        # Execute the query
        cursor.execute(query)

        # Fetch all records from the table
        records = cursor.fetchall()

        # Debugging: print records to see its structure
        print(f"Fetched records: {records}")

        # Check if records are not empty
        if not records:
            st.write("No records found in the database.")
            return pd.DataFrame(columns=['RollNumber', 'Subject', 'Marks'])  # Return empty dataframe

        # Ensure the number of columns returned matches the expected structure
        columns = ['RollNumber', 'Subject', 'Marks']
        
        # Create a Pandas DataFrame from the fetched records
        df = pd.DataFrame(records, columns=columns)

        # Return the DataFrame
        return df

    except mysql.connector.Error as err:
        st.write(f"Error: {err}")
        return pd.DataFrame(columns=['RollNumber', 'Subject', 'Marks'])  # Return empty dataframe in case of error

    finally:
        # Close the cursor and connection
        if cursor:
            cursor.close()
        if connection:
            connection.close()

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
    # Create tabs
    tab1, tab2 = st.tabs(["Check Marks", "Check Result"])

    with tab1:
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
                    insert_student_result(roll_number, total_marks_obtained)

            for result in all_results:
                st.subheader(f"📌 Roll Number: {result['Roll Number']}")
                st.write(f"### ✅ Total Marks: {result['Total Marks Obtained']:.2f} / {result['Total Possible Marks']:.2f}")
                st.dataframe(result["Details"])

                # Save and download individual results
                output_file = f"{result['Roll Number']}_graded_answers.csv"
                result["Details"].to_csv(output_file, index=False)
                st.download_button(f"⬇️ Download Results for {result['Roll Number']}", data=open(output_file, "rb"), file_name=output_file, mime="text/csv")

    with tab2:
        # Display student results from database
        df_results = read_student_results()
        if df_results is not None:
            st.dataframe(df_results)
        else:
            st.write("No student results found in the database.")

if __name__ == "__main__":
    main()
