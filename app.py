"""
app.py - Main Flask Application
Scaffolds routes:
  - GET /               -> Serves single-page dashboard with database-backed job roles
  - GET /api/roles      -> Returns unique list of job titles from database
  - GET /api/jobs       -> Returns catalog of all job roles from database
  - POST /api/analyze   -> Handles resume upload & evaluation against selected target role
  - POST /api/upload    -> Alias/backward-compatible endpoint for analyze
"""

import os
import io
import json
import urllib.parse
from typing import Any, Dict, List
from flask import Flask, render_template, request, jsonify
from werkzeug.utils import secure_filename
from database import job_db
from parser import ResumeParser
from matcher import JobMatcher
import config
from services.live_job_service import get_job_vacancies, match_live_jobs

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB max upload limit
ALLOWED_EXTENSIONS = {"pdf"}


def attach_search_urls(jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Attach one Google search URL to each job recommendation."""
    for job in jobs:
        for field in ("apply_url", "apply_link", "job_apply_link", "job_google_link", "search_fallback_url"):
            job.pop(field, None)
        job_title = str(job.get("job_title") or "Software Engineer").strip()
        company_name = str(
            job.get("company_name")
            or job.get("company")
            or job.get("employer_name")
            or job.get("companies_summary")
            or ""
        ).strip()
        query_str = f"{job_title} {company_name} apply"
        job["search_url"] = f"https://www.google.com/search?q={urllib.parse.quote_plus(query_str)}"
    return jobs


# Connect to database and verify records on startup
print(f"[INIT] Connecting to database: {job_db.db_path}...")
job_count = job_db.get_job_count()
skill_count = job_db.get_skill_count()
print(f"[INIT] Successfully connected to database: {job_db.db_path}")
print(f"[INIT] Loaded {job_count} active job records and {skill_count} skills from database.")

# Initialize Parser and Matcher singletons
print("[INIT] Loading ResumeParser and NLP models...")
resume_parser = ResumeParser()
print("[INIT] Loading JobMatcher with dynamic database records...")
job_matcher = JobMatcher(db=job_db)
print("[INIT] System initialized and ready on http://127.0.0.1:5000")


def allowed_file(filename: str) -> bool:
    """Check if uploaded file has a valid PDF extension."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route("/")
def index():
    """Render the single-page dashboard."""
    roles = job_db.get_distinct_job_titles()
    return render_template(
        "index.html",
        roles=roles,
        jobs=job_matcher.get_all_jobs(),
        standard_roles=job_matcher.get_standard_roles(),
        job_count=job_count,
        skill_count=skill_count,
        use_mock_jobs=config.USE_MOCK_JOBS
    )


@app.route("/api/roles", methods=["GET"])
def get_unique_roles():
    """
    Return unique list of job titles from local job database.
    Used by frontend drop-down menu to select target job role.
    """
    distinct_titles = job_db.get_distinct_job_titles()
    return jsonify({
        "success": True,
        "total_roles": len(distinct_titles),
        "roles": distinct_titles,
        "standard_roles": job_matcher.get_standard_roles(),
        "evaluation_framework": job_matcher.get_evaluation_framework()
    })


@app.route("/api/jobs", methods=["GET"])
def get_jobs():
    """Return all job roles queried dynamically from database."""
    jobs = job_matcher.get_all_jobs()
    return jsonify({
        "success": True,
        "database_connected": True,
        "total_jobs": len(jobs),
        "jobs": jobs
    })


@app.route("/api/analyze", methods=["POST"])
@app.route("/api/upload", methods=["POST"])
def analyze_resume():
    """
    Handle resume upload and target role analysis.
    Supports:
    1. Multipart/form-data: PDF resume + target_role
    2. Application/json: pre-parsed candidate profile + target_role (for dynamic switching)
    """
    # -------------------------------------------------------------
    # Case A: JSON Payload (Dynamic role switching without re-upload)
    # -------------------------------------------------------------
    if request.is_json:
        data = request.get_json() or {}
        candidate_skills = data.get("skills", [])
        resume_text = data.get("resume_text", "")
        target_role = data.get("target_role") or data.get("target_role_id", "all")
        custom_title = data.get("custom_title", "")
        custom_description = data.get("custom_description", "")

        try:
            target_analysis, secondary_recs = job_matcher.evaluate_with_target_role(
                candidate_skills=candidate_skills,
                resume_text=resume_text,
                target_role=target_role,
                custom_title=custom_title,
                custom_description=custom_description,
                limit_secondary=5
            )

            # Fetch matching live job vacancies (JSearch / Mock dataset)
            try:
                live_q = target_analysis.get("job_title", "") if target_analysis else (candidate_skills[0] if candidate_skills else "Software Engineer")
                live_vacancies = get_job_vacancies(query=live_q, location="Remote")
                live_recommendations = match_live_jobs(user_skills=candidate_skills, job_list=live_vacancies, resume_text=resume_text)
                attach_search_urls(live_recommendations)
            except Exception as live_err:
                app.logger.warning(f"Could not load live recommendations: {live_err}")
                live_recommendations = []
            attach_search_urls(secondary_recs)

            return jsonify({
                "success": True,
                "target_role": target_analysis.get("job_title") if target_analysis else target_role,
                "target_analysis": target_analysis,
                "recommendations": secondary_recs,
                "total_secondary_recommendations": len(secondary_recs),
                "total_unique_roles_recommended": len(secondary_recs),
                "live_recommendations": live_recommendations,
                "live_mode": "mock" if config.USE_MOCK_JOBS else "live"
            })
        except Exception as e:
            app.logger.error(f"Error in dynamic role analyze: {str(e)}", exc_info=True)
            return jsonify({"success": False, "error": str(e)}), 500

    # -------------------------------------------------------------
    # Case B: Multipart File Upload (Resume PDF + Target Role)
    # -------------------------------------------------------------
    if "resume" not in request.files:
        return jsonify({
            "success": False,
            "error": "No resume file provided in the request."
        }), 400

    file = request.files["resume"]
    if file.filename == "":
        return jsonify({
            "success": False,
            "error": "No file selected."
        }), 400

    if not allowed_file(file.filename):
        return jsonify({
            "success": False,
            "error": "Invalid file format. Please upload a PDF document (.pdf)."
        }), 400

    target_role = request.form.get("target_role", "all").strip()
    custom_title = request.form.get("custom_title", "").strip()
    custom_description = request.form.get("custom_description", "").strip()

    try:
        # Read PDF stream into memory
        file_bytes = file.read()
        if len(file_bytes) == 0:
            return jsonify({
                "success": False,
                "error": "The uploaded PDF file is empty."
            }), 400

        if not file_bytes.startswith(b"%PDF-"):
            return jsonify({
                "success": False,
                "error": "The uploaded file is not a valid PDF document."
            }), 400

        # 1. Parse Resume using SpaCy and PyPDF2
        parsed_data = resume_parser.parse(file_bytes)

        if not parsed_data["raw_text"].strip():
            return jsonify({
                "success": False,
                "error": "Could not extract text from this PDF. Ensure it contains selectable text and is not a scanned image."
            }), 400

        is_resume, validation_error = resume_parser.validate_resume_text(
            parsed_data["raw_text"]
        )
        if not is_resume:
            return jsonify({
                "success": False,
                "error": validation_error
            }), 400

        candidate_skills = parsed_data["skills"]
        resume_text = parsed_data["raw_text"]

        # 2. Evaluate against user-selected Target Role & generate Secondary Recommendations
        target_analysis, secondary_recs = job_matcher.evaluate_with_target_role(
            candidate_skills=candidate_skills,
            resume_text=resume_text,
            target_role=target_role,
            custom_title=custom_title,
            custom_description=custom_description,
            limit_secondary=5
        )

        # 3. Live Job Recommendations (JSearch / Mock dataset)
        try:
            live_q = target_analysis.get("job_title", "") if target_analysis else (candidate_skills[0] if candidate_skills else "Software Engineer")
            live_vacancies = get_job_vacancies(query=live_q, location="Remote")
            live_recommendations = match_live_jobs(user_skills=candidate_skills, job_list=live_vacancies, resume_text=resume_text)
            attach_search_urls(live_recommendations)
        except Exception as live_err:
            app.logger.warning(f"Could not load live recommendations: {live_err}")
            live_recommendations = []
        attach_search_urls(secondary_recs)

        return jsonify({
            "success": True,
            "filename": secure_filename(file.filename),
            "target_role": target_analysis.get("job_title") if target_analysis else target_role,
            "candidate": {
                "name": parsed_data["name"],
                "email": parsed_data["email"],
                "phone": parsed_data["phone"],
                "links": parsed_data["links"],
                "education": parsed_data["education"],
                "skills": parsed_data["skills"],
                "total_skills": len(parsed_data["skills"])
            },
            "target_analysis": target_analysis,
            "recommendations": secondary_recs,
            "total_secondary_recommendations": len(secondary_recs),
            "total_unique_roles_recommended": len(secondary_recs),
            "live_recommendations": live_recommendations,
            "live_mode": "mock" if config.USE_MOCK_JOBS else "live",
            "resume_text": resume_text,
            "resume_text_snippet": (resume_text[:400] + "...") if len(resume_text) > 400 else resume_text
        })

    except Exception as e:
        app.logger.error(f"Error during resume processing: {str(e)}", exc_info=True)
        return jsonify({
            "success": False,
            "error": f"An unexpected error occurred during processing: {str(e)}"
        }), 500


@app.route("/api/live-recommendations", methods=["GET", "POST"])
def get_live_recommendations():
    """
    Fetch and recommend real-time live job postings from LinkedIn, Indeed, and Glassdoor
    via JSearch API (or local mock dataset when USE_MOCK_JOBS=True) and Scikit-learn TF-IDF matching.
    Supports GET (query params) and POST (JSON / form data).
    """
    skills = []
    query = ""
    location = "Remote"
    resume_text = ""

    if request.method == "POST":
        if request.is_json:
            data = request.get_json() or {}
            skills = data.get("skills", [])
            query = data.get("query", "")
            location = data.get("location", "Remote")
            resume_text = data.get("resume_text", "")
        else:
            skills_raw = request.form.get("skills", "")
            skills = [s.strip() for s in skills_raw.split(",") if s.strip()] if isinstance(skills_raw, str) else []
            query = request.form.get("query", "")
            location = request.form.get("location", "Remote")
            resume_text = request.form.get("resume_text", "")
    else:  # GET
        skills_raw = request.args.get("skills", "")
        skills = [s.strip() for s in skills_raw.split(",") if s.strip()] if skills_raw else []
        query = request.args.get("query", "")
        location = request.args.get("location", "Remote")
        resume_text = request.args.get("resume_text", "")

    # Default query fallback if empty
    if not query:
        query = skills[0] if skills else "Software Engineer"

    try:
        raw_vacancies = get_job_vacancies(query=query, location=location)
        ranked_jobs = match_live_jobs(user_skills=skills, job_list=raw_vacancies, resume_text=resume_text)
        attach_search_urls(ranked_jobs)

        return jsonify({
            "success": True,
            "mode": "mock" if config.USE_MOCK_JOBS else "live",
            "mock_active": config.USE_MOCK_JOBS,
            "query": query,
            "location": location,
            "total_vacancies": len(raw_vacancies),
            "total_recommended": len(ranked_jobs),
            "jobs": ranked_jobs
        })
    except Exception as e:
        app.logger.error(f"Error in live recommendations: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "error": f"Failed to retrieve live recommendations: {str(e)}"
        }), 500



@app.errorhandler(413)
def request_entity_too_large(error):
    """Handle files exceeding maximum size."""
    return jsonify({
        "success": False,
        "error": "The uploaded file is too large. Maximum file size allowed is 16 MB."
    }), 413


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
