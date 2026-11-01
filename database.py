"""
database.py - Database Layer for AI Resume Analyzer
Connects to SQLite database (jobs.db) and provides automatic initialization
from AI_Resume_Analyzer_Database_Final_Corrected.xlsx if needed.
"""

import os
import sqlite3
from typing import Dict, List, Any, Optional


class JobDatabase:
    """Database interface for jobs, skills, and resume records."""

    def __init__(self, db_path: Optional[str] = None, excel_path: Optional[str] = None):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.db_path = db_path or os.path.join(base_dir, "jobs.db")
        self.excel_path = excel_path or os.path.join(
            base_dir, "AI_Resume_Analyzer_Database_Final_Corrected.xlsx"
        )
        self._ensure_database_ready()

    def get_connection(self) -> sqlite3.Connection:
        """Create and return a database connection with dictionary cursor support."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_database_ready(self):
        """Check if jobs.db exists and has records; if not, ingest from Excel."""
        needs_init = False
        if not os.path.exists(self.db_path) or os.path.getsize(self.db_path) == 0:
            needs_init = True
        else:
            try:
                with self.get_connection() as conn:
                    cur = conn.cursor()
                    cur.execute("SELECT COUNT(*) FROM jobs")
                    count = cur.fetchone()[0]
                    if count == 0:
                        needs_init = True
            except Exception:
                needs_init = True

        if needs_init:
            self._import_from_excel()

    def _import_from_excel(self):
        """Import all sheets from the Excel file into SQLite jobs.db."""
        if not os.path.exists(self.excel_path):
            raise FileNotFoundError(
                f"Cannot initialize database. Excel file not found: {self.excel_path}"
            )

        print(f"[DB] Initializing '{self.db_path}' from '{self.excel_path}'...")
        try:
            import pandas as pd
            xl = pd.ExcelFile(self.excel_path)
            conn = sqlite3.connect(self.db_path)
            for sheet_name in xl.sheet_names:
                df = pd.read_excel(xl, sheet_name)
                # Use clean lowercase table names
                table_name = sheet_name.strip().lower()
                df.to_sql(table_name, conn, if_exists="replace", index=False)
            
            # Create indexes for optimal join performance
            cur = conn.cursor()
            cur.execute("CREATE INDEX IF NOT EXISTS idx_job_skills_job_id ON job_skills(Job_ID)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_job_skills_skill_id ON job_skills(Skill_ID)")
            conn.commit()
            conn.close()
            print(f"[DB] Database successfully initialized from Excel.")
        except Exception as e:
            print(f"[DB ERROR] Failed to import from Excel: {e}")
            raise

    def get_job_count(self) -> int:
        """Return total count of job records."""
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM jobs")
            return cur.fetchone()[0]

    def get_skill_count(self) -> int:
        """Return total count of skills in master catalog."""
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM skills_master")
            return cur.fetchone()[0]

    def get_all_jobs(self) -> List[Dict[str, Any]]:
        """
        Query all jobs joined with job_skills and skills_master.
        Groups skills into required (Mandatory) and recommended (Preferred).
        """
        query = """
            SELECT 
                j.Job_ID, j.Job_Title, j.Company, j.Location, 
                j.Experience_Required, j.Salary_LPA, j.Employment_Type, j.Job_Description,
                s.Skill_ID, s.Skill_Name, js.Priority
            FROM jobs j
            LEFT JOIN job_skills js ON j.Job_ID = js.Job_ID
            LEFT JOIN skills_master s ON js.Skill_ID = s.Skill_ID
            ORDER BY j.Job_ID
        """
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(query)
            rows = cur.fetchall()

        jobs_dict: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            job_id = row["Job_ID"]
            if job_id not in jobs_dict:
                jobs_dict[job_id] = {
                    "id": job_id,
                    "title": row["Job_Title"],
                    "company": row["Company"],
                    "location": row["Location"],
                    "experience_level": row["Experience_Required"],
                    "salary_lpa": row["Salary_LPA"],
                    "employment_type": row["Employment_Type"],
                    "category": row["Job_Title"],
                    "description": row["Job_Description"] or "",
                    "required_skills": [],
                    "recommended_skills": [],
                    "raw_skills": []
                }

            skill_name = row["Skill_Name"]
            priority = row["Priority"]
            if skill_name:
                skill_clean = skill_name.strip().lower()
                jobs_dict[job_id]["raw_skills"].append(skill_name.strip())
                if priority == "Mandatory":
                    if skill_clean not in jobs_dict[job_id]["required_skills"]:
                        jobs_dict[job_id]["required_skills"].append(skill_clean)
                else:
                    if skill_clean not in jobs_dict[job_id]["recommended_skills"]:
                        jobs_dict[job_id]["recommended_skills"].append(skill_clean)

        return list(jobs_dict.values())

    def get_job_by_id(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Query a single job by Job_ID with all its required & recommended skills."""
        query = """
            SELECT 
                j.Job_ID, j.Job_Title, j.Company, j.Location, 
                j.Experience_Required, j.Salary_LPA, j.Employment_Type, j.Job_Description,
                s.Skill_ID, s.Skill_Name, js.Priority
            FROM jobs j
            LEFT JOIN job_skills js ON j.Job_ID = js.Job_ID
            LEFT JOIN skills_master s ON js.Skill_ID = s.Skill_ID
            WHERE j.Job_ID = ?
        """
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(query, (job_id,))
            rows = cur.fetchall()

        if not rows:
            return None

        first = rows[0]
        job_data = {
            "id": first["Job_ID"],
            "title": first["Job_Title"],
            "company": first["Company"],
            "location": first["Location"],
            "experience_level": first["Experience_Required"],
            "salary_lpa": first["Salary_LPA"],
            "employment_type": first["Employment_Type"],
            "category": first["Job_Title"],
            "description": first["Job_Description"] or "",
            "required_skills": [],
            "recommended_skills": [],
            "raw_skills": []
        }

        for row in rows:
            skill_name = row["Skill_Name"]
            priority = row["Priority"]
            if skill_name:
                skill_clean = skill_name.strip().lower()
                job_data["raw_skills"].append(skill_name.strip())
                if priority == "Mandatory":
                    if skill_clean not in job_data["required_skills"]:
                        job_data["required_skills"].append(skill_clean)
                else:
                    if skill_clean not in job_data["recommended_skills"]:
                        job_data["recommended_skills"].append(skill_clean)

        return job_data

    def get_distinct_job_titles(self) -> List[str]:
        """Return list of distinct job titles in database."""
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT DISTINCT Job_Title FROM jobs ORDER BY Job_Title")
            return [r[0] for r in cur.fetchall()]

    def get_all_skills_master(self) -> List[Dict[str, Any]]:
        """Return all skills from skills_master catalog."""
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT Skill_ID, Skill_Name, Category, ATS_Keyword FROM skills_master")
            return [dict(r) for r in cur.fetchall()]


# Singleton database instance
job_db = JobDatabase()

