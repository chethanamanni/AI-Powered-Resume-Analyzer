"""
test_pipeline.py - Automated Verification Script
Validates:
1. SQLite Database integration (jobs.db) with 180 jobs and 150 skills
2. ResumeParser extraction (Contact, Education, Skills)
3. JobMatcher dynamic database matching, ATS scoring & skill gap detection
4. Flask App routes (/ , /api/jobs, /api/upload, /api/analyze)
"""

import os
import io
import json
import PyPDF2
from database import job_db
from parser import ResumeParser
from matcher import JobMatcher
from app import app


def create_sample_pdf_bytes() -> bytes:
    """Create a valid PDF file in memory with sample resume text."""
    pdf_content = (
        b"%PDF-1.4\n"
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n"
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> endobj\n"
        b"4 0 obj << /Length 450 >>\nstream\n"
        b"BT\n/F1 12 Tf\n50 720 Td\n"
        b"(Alex Mercer) Tj\n"
        b"0 -18 Td\n(alex.mercer@example.com | +1 555-234-5678) Tj\n"
        b"0 -18 Td\n(linkedin.com/in/alexmercer | github.com/alexmercer) Tj\n"
        b"0 -24 Td\n(EDUCATION) Tj\n"
        b"0 -18 Td\n(Bachelor of Technology in Computer Science) Tj\n"
        b"0 -18 Td\n(National Institute of Technology, 2023) Tj\n"
        b"0 -24 Td\n(TECHNICAL SKILLS) Tj\n"
        b"0 -18 Td\n(Languages: Python, JavaScript, TypeScript, SQL, Bash) Tj\n"
        b"0 -18 Td\n(Frameworks & Backend: FastAPI, Flask, React, Node.js, REST API) Tj\n"
        b"0 -18 Td\n(Databases: PostgreSQL, Redis, MongoDB) Tj\n"
        b"0 -18 Td\n(DevOps: Docker, Git, Linux, CI/CD, AWS) Tj\n"
        b"ET\nendstream\nendobj\n"
        b"5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n"
        b"xref\n0 6\n"
        b"0000000000 65535 f \n"
        b"0000000010 00000 n \n"
        b"0000000060 00000 n \n"
        b"0000000117 00000 n \n"
        b"0000000247 00000 n \n"
        b"0000000750 00000 n \n"
        b"trailer << /Size 6 /Root 1 0 R >>\n"
        b"startxref\n827\n%%EOF"
    )
    return pdf_content


def run_tests():
    print("=" * 60)
    print("STARTING DATABASE & PIPELINE VERIFICATION")
    print("=" * 60)

    # 1. Verify Database
    print("\n[TEST 1] Testing Database Connection & Queries...")
    job_count = job_db.get_job_count()
    skill_count = job_db.get_skill_count()
    print(f"  Connected to: {job_db.db_path}")
    print(f"  Total Jobs in DB: {job_count}")
    print(f"  Total Skills in Master: {skill_count}")
    assert job_count >= 180, f"Expected at least 180 jobs, found {job_count}"
    assert skill_count >= 150, f"Expected at least 150 skills, found {skill_count}"

    sample_job = job_db.get_job_by_id("JOB0001")
    assert sample_job is not None, "JOB0001 should exist in database"
    print(f"  Sample Job (JOB0001): {sample_job['title']} @ {sample_job['company']} ({sample_job['location']})")
    print(f"    Required Skills ({len(sample_job['required_skills'])}): {sample_job['required_skills']}")
    print(f"    Recommended Skills ({len(sample_job['recommended_skills'])}): {sample_job['recommended_skills']}")
    print("  --> Database tests PASSED!")

    # 2. Test ResumeParser
    print("\n[TEST 2] Testing ResumeParser...")
    pdf_bytes = create_sample_pdf_bytes()
    parser = ResumeParser()
    parsed = parser.parse(pdf_bytes)

    print(f"  Extracted Name: {parsed['name']}")
    print(f"  Extracted Email: {parsed['email']}")
    print(f"  Extracted Phone: {parsed['phone']}")
    print(f"  Extracted Education: {parsed['education']}")
    print(f"  Extracted Skills ({len(parsed['skills'])}): {parsed['skills']}")

    assert parsed["email"] == "alex.mercer@example.com", "Email mismatch"
    assert "python" in parsed["skills"], "Python should be detected"
    assert "docker" in parsed["skills"], "Docker should be detected"
    assert "fastapi" in parsed["skills"], "FastAPI should be detected"
    print("  --> ResumeParser tests PASSED!")

    # 3. Test JobMatcher with Database
    print("\n[TEST 3] Testing JobMatcher with Database...")
    matcher = JobMatcher(db=job_db)
    all_jobs = matcher.get_all_jobs()
    print(f"  Loaded {len(all_jobs)} dynamic jobs from database")
    assert len(all_jobs) >= 180, f"Expected >= 180 jobs, got {len(all_jobs)}"

    ranked_results = matcher.match_all_jobs(parsed["skills"], parsed["raw_text"], unique_by_title=True, limit=5)
    top_role = ranked_results[0]
    print(f"  Top Ranked Role: {top_role['job_title']} @ {top_role['company']} with ATS Score: {top_role['ats_score']}%")
    print(f"  Matched Skills ({len(top_role['matched_skills'])}): {top_role['matched_skills']}")
    print(f"  Missing Skills ({len(top_role['missing_skills'])}): {top_role['missing_skills']}")
    print(f"  Recommendations: {top_role['recommendations']}")

    # Assert uniqueness and top 5 count
    titles = [r["job_title"] for r in ranked_results]
    assert len(titles) == len(set(titles)), f"Duplicate titles found: {titles}"
    assert len(ranked_results) == 5, f"Expected 5 unique roles, got {len(ranked_results)}"
    print(f"  Verified Uniqueness: All 5 roles are distinct ({', '.join(titles)})")

    assert top_role["ats_score"] > 40, "Expected positive ATS score"
    print("  --> JobMatcher database tests PASSED!")

    # 4. Test Flask API Endpoints
    print("\n[TEST 4] Testing Flask API Endpoints...")
    client = app.test_client()

    # GET /
    res_index = client.get("/")
    assert res_index.status_code == 200, f"GET / failed with {res_index.status_code}"
    assert b"AI Resume Analyzer" in res_index.data, "Dashboard title not found in HTML"
    print("  GET / returned 200 OK")

    # GET /api/jobs
    res_jobs = client.get("/api/jobs")
    assert res_jobs.status_code == 200
    jobs_data = res_jobs.get_json()
    assert jobs_data["success"] is True
    assert jobs_data["total_jobs"] >= 180
    print(f"  GET /api/jobs returned 200 OK ({jobs_data['total_jobs']} jobs from database)")

    # POST /api/upload
    data = {
        "resume": (io.BytesIO(pdf_bytes), "sample_alex_mercer.pdf"),
        "target_role": "all"
    }
    res_upload = client.post("/api/upload", data=data, content_type="multipart/form-data")
    assert res_upload.status_code == 200, f"POST /api/upload failed: {res_upload.data}"
    upload_resp = res_upload.get_json()
    assert upload_resp["success"] is True
    assert upload_resp["total_unique_roles_recommended"] == 5
    rec_titles = [r["job_title"] for r in upload_resp["recommendations"]]
    assert len(rec_titles) == len(set(rec_titles)), f"Duplicates in API: {rec_titles}"
    assert len(upload_resp["recommendations"]) == 5
    print(f"  POST /api/upload returned 200 OK (Recommended {upload_resp['total_unique_roles_recommended']} unique database jobs)")

    # POST /api/analyze (dynamic role re-calculation with database job ID)
    res_analyze = client.post(
        "/api/analyze",
        data=json.dumps({
            "skills": parsed["skills"],
            "resume_text": parsed["raw_text"],
            "target_role_id": "JOB0001"
        }),
        content_type="application/json"
    )
    assert res_analyze.status_code == 200
    analyze_resp = res_analyze.get_json()
    assert analyze_resp["success"] is True
    assert analyze_resp["target_analysis"]["job_id"] == "JOB0001"
    print("  POST /api/analyze returned 200 OK (Switched to database role JOB0001 dynamically)")

    print("\n" + "=" * 60)
    print("ALL DATABASE & PIPELINE TESTS PASSED SUCCESSFULLY!")
    print("=" * 60)


if __name__ == "__main__":
    run_tests()
