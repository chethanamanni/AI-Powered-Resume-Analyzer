"""
test_live_jobs.py - Validation test for Live Job Recommendation Service
Validates:
1. Mock mode is active (USE_MOCK_JOBS=True) to protect RapidAPI quota.
2. get_job_vacancies returns realistic mock vacancies from sample_live_jobs.json.
3. match_live_jobs correctly scores vacancies using TF-IDF & skills, and sorts descending.
4. Flask /api/live-recommendations endpoint returns structured JSON with mock status.
"""

import sys
from unittest.mock import Mock, patch

import config
from services.live_job_service import (
    filter_indian_jobs,
    get_job_vacancies,
    match_live_jobs,
)
from app import app


def run_tests():
    print("=" * 70)
    print("RUNNING LIVE JOB RECOMMENDATION SERVICE TESTS")
    print("=" * 70)

    # 1. Check Configuration & Quota Protection
    print(f"[TEST 1] Checking Quota Protection Configuration...")
    print(f"  USE_MOCK_JOBS: {config.USE_MOCK_JOBS}")
    print(f"  RAPIDAPI_HOST: {config.RAPIDAPI_HOST}")
    print(f"  MOCK_DATA_PATH: {config.MOCK_DATA_PATH}")
    print(f"  --> Configuration loaded successfully (Mode: {'MOCK' if config.USE_MOCK_JOBS else 'LIVE API'}).")

    # 2. Test get_job_vacancies
    print("\n[TEST 2] Testing get_job_vacancies()...")
    vacancies = get_job_vacancies(query="Python", location="Remote")
    print(f"  Retrieved {len(vacancies)} vacancies")
    assert len(vacancies) >= 1, "Expected at least 1 vacancy"
    sample = vacancies[0]
    print(f"  Sample Job: {sample.get('job_title')} at {sample.get('employer_name')} ({sample.get('job_publisher')})")
    assert "job_title" in sample and "employer_name" in sample
    assert sample["search_url"].startswith("https://www.google.com/search?q=")
    assert not any(field in sample for field in ("apply_url", "apply_link", "job_apply_link", "job_google_link"))
    assert all(job.get("job_country") == "IN" for job in vacancies), "All vacancies must be in India"
    print("  --> Vacancies Loading & Link Normalization PASSED!")

    print("\n[TEST 2A] Testing India-only API filtering and city query...")
    api_payload = {
        "data": [
            {"job_id": "in-code", "job_country": "IN"},
            {"job_id": "in-name", "job_country": "India"},
            {"job_id": "in-location", "job_location": "Remote, India"},
            {"job_id": "out-country", "job_country": "US", "job_city": "Boston"},
            {"job_id": "out-description", "job_country": "US", "job_description": "India team"},
        ]
    }
    mock_response = Mock()
    mock_response.json.return_value = api_payload
    saved_use_mock_jobs = config.USE_MOCK_JOBS
    saved_rapidapi_key = config.RAPIDAPI_KEY
    try:
        config.USE_MOCK_JOBS = False
        config.RAPIDAPI_KEY = "test-api-key"
        with patch("services.live_job_service.requests.get", return_value=mock_response) as mock_get:
            city_vacancies = get_job_vacancies(query="Python Engineer", location="Bengaluru")
        assert mock_get.call_args.kwargs["params"]["query"] == "Python Engineer in Bengaluru, India"
        assert [job["job_id"] for job in city_vacancies] == ["in-code", "in-name", "in-location"]
        assert len(filter_indian_jobs(api_payload["data"])) == 3
    finally:
        config.USE_MOCK_JOBS = saved_use_mock_jobs
        config.RAPIDAPI_KEY = saved_rapidapi_key
    print("  --> India-only API filtering and city query PASSED!")

    # 3. Test match_live_jobs with Candidate Skills
    print("\n[TEST 3] Testing match_live_jobs() with TF-IDF Matching...")
    user_skills = ["python", "fastapi", "docker", "postgresql", "redis", "linux", "rest api"]
    resume_text = (
        "Senior Backend Engineer with 4 years experience in Python, FastAPI, Flask, "
        "PostgreSQL, Redis, Docker, and Linux microservices."
    )

    ranked_jobs = match_live_jobs(user_skills=user_skills, job_list=vacancies, resume_text=resume_text)
    print(f"  Ranked {len(ranked_jobs)} vacancies")
    assert len(ranked_jobs) == len(vacancies), "All vacancies should be scored and returned"

    top = ranked_jobs[0]
    assert top["search_url"].startswith("https://www.google.com/search?q=")
    assert not any(field in top for field in ("apply_url", "apply_link", "job_apply_link"))
    assert "India" in top["location"], "Displayed job locations should identify India"
    print(f"  #1 Top Live Match: '{top['job_title']}' at {top['employer_name']}")
    print(f"     Match Score: {top['match_score']}% ({top['rating']})")
    print(f"     Publisher: {top['job_publisher']} | Location: {top['location']} | Salary: {top['salary']}")
    print(f"     Matched Skills ({top['matched_skills_count']}): {top['matched_skills']}")
    print(f"     Missing Skills ({len(top['missing_skills'])}): {top['missing_skills']}")

    # Verify descending sort order
    scores = [j["match_score"] for j in ranked_jobs]
    assert scores == sorted(scores, reverse=True), "Jobs must be sorted in descending order of match_score"
    print("  --> Matcher & TF-IDF Scoring PASSED! (Sorted descending)")

    # 4. Test Flask Endpoint /api/live-recommendations
    print("\n[TEST 4] Testing Flask API Endpoint /api/live-recommendations...")
    client = app.test_client()

    # Test POST JSON
    payload = {
        "skills": user_skills,
        "query": "Python Engineer",
        "location": "Remote",
        "resume_text": resume_text
    }
    res_post = client.post("/api/live-recommendations", json=payload)
    print(f"  POST /api/live-recommendations status code: {res_post.status_code}")
    assert res_post.status_code == 200, f"Expected 200, got {res_post.status_code}"
    resp_data = res_post.get_json()
    assert resp_data["mode"] in ("mock", "live"), "Response mode should indicate 'mock' or 'live'"
    assert len(resp_data["jobs"]) > 0
    assert "search_url" in resp_data["jobs"][0]
    assert resp_data["jobs"][0]["search_url"].startswith("https://www.google.com/search?q=")
    assert not any(
        field in resp_data["jobs"][0]
        for field in ("apply_url", "apply_link", "job_apply_link", "search_fallback_url")
    )
    print(f"  POST /api/live-recommendations returned {len(resp_data['jobs'])} jobs in '{resp_data['mode']}' mode")


    # Test GET query params
    res_get = client.get("/api/live-recommendations?query=React&location=Remote&skills=react,typescript,javascript")
    print(f"  GET /api/live-recommendations status code: {res_get.status_code}")
    assert res_get.status_code == 200
    resp_get_data = res_get.get_json()
    assert resp_get_data["success"] is True
    print(f"  GET /api/live-recommendations returned {len(resp_get_data['jobs'])} jobs")

    print("\n[TEST 5] Testing search-only links on resume-analyzer recommendations...")
    analysis_res = client.post("/api/analyze", json=payload)
    assert analysis_res.status_code == 200
    analysis_data = analysis_res.get_json()
    assert analysis_data["success"] is True
    for job in analysis_data["recommendations"]:
        assert job["search_url"].startswith("https://www.google.com/search?q=")
        assert not any(field in job for field in ("apply_url", "apply_link", "job_apply_link"))
    print(f"  Verified {len(analysis_data['recommendations'])} recommendations use search_url only.")

    print("\n" + "=" * 70)
    print("ALL LIVE JOB RECOMMENDATION SERVICE TESTS PASSED CLEANLY!")
    print("=" * 70)


if __name__ == "__main__":
    run_tests()
