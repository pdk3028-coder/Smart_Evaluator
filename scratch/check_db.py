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
        f.write("--- Unique Position values in employees ---\n")
        rows = c.execute("SELECT DISTINCT position FROM employees").fetchall()
        for r in rows:
            f.write(f"Position: {repr(r['position'])}\n")
            
        f.write("\n--- Sample Employees (Top 15) ---\n")
        rows = c.execute("SELECT id, name, emp_id, team_name, position FROM employees LIMIT 15").fetchall()
        for r in rows:
            f.write(f"ID: {r['id']}, Name: {r['name']}, Position: {repr(r['position'])}\n")
            
        f.write("\n--- Existing Evaluation Projects with Evaluatee Positions ---\n")
        query = """
            SELECT p.id, p.title, p.evaluation_type, e.name, e.position 
            FROM evaluation_projects p
            JOIN employees e ON p.evaluatee_id = e.id
        """
        rows = c.execute(query).fetchall()
        for r in rows:
            f.write(f"Project ID: {r['id']}, Title: {repr(r['title'])}, EvalType: {repr(r['evaluation_type'])}, Evaluatee: {r['name']}, Position: {repr(r['position'])}\n")
            
    conn.close()
    print("Database check info written to scratch/db_info.txt")

if __name__ == '__main__':
    check()
