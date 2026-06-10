# -*- coding: utf-8 -*-
import sqlite3
import os

DB_PATH = r"C:\Users\user06065\Desktop\Code Test\employees.db"

def check():
    if not os.path.exists(DB_PATH):
        print("Database file does not exist at:", DB_PATH)
        return
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    with open("scratch/db_info.txt", "w", encoding="utf-8") as f:
        f.write("--- evaluation_projects Table SQL ---\n")
        row = c.execute("SELECT sql FROM sqlite_master WHERE name='evaluation_projects'").fetchone()
        if row:
            f.write(row[0] + "\n")
        else:
            f.write("No evaluation_projects table found\n")
            
        f.write("\n--- evaluation_questions Table SQL ---\n")
        row = c.execute("SELECT sql FROM sqlite_master WHERE name='evaluation_questions'").fetchone()
        if row:
            f.write(row[0] + "\n")
        else:
            f.write("No evaluation_questions table found\n")
            
        f.write("\n--- Project Data (Top 5) ---\n")
        rows = c.execute("SELECT id, evaluatee_id, title, evaluation_type FROM evaluation_projects LIMIT 5").fetchall()
        for r in rows:
            f.write(str(dict(r)) + "\n")
            f.write("  repr(title): " + repr(r['title']) + "\n")
            f.write("  repr(evaluation_type): " + repr(r['evaluation_type']) + "\n")
            
        f.write("\n--- Questions Data (Top 5) ---\n")
        rows = c.execute("SELECT id, question_text, category, evaluation_type FROM evaluation_questions LIMIT 5").fetchall()
        for r in rows:
            f.write(str(dict(r)) + "\n")
            f.write("  repr(question_text): " + repr(r['question_text']) + "\n")
            
    conn.close()
    print("Database check info written to scratch/db_info.txt")

if __name__ == '__main__':
    check()
