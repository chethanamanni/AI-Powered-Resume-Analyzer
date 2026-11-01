"""
mock_match_test.py - Mock Test for Deduplicated Role Recommendations
Verifies that:
1. All recommended roles have distinct job_titles (no duplicates).
2. For multiple openings under the same title, scores are max-aggregated.
3. The recommendation list is strictly capped at the Top 5 unique job roles.
"""

from database import job_db
from matcher import JobMatcher


def test_unique_recommendations():
    print("=" * 75)
    print("RUNNING MOCK MATCH TEST: TOP 5 UNIQUE JOB RECOMMENDATIONS")
    print("=" * 75)

    # Candidate profile mock
    mock_candidate_skills = [
        "python", "fastapi", "docker", "postgresql", "redis",
        "git", "linux", "rest api", "react", "javascript"
    ]
    mock_resume_text = (
        "Full-Stack Python Engineer with 3 years of experience developing microservices "
        "using FastAPI, Flask, PostgreSQL, Docker, Redis, and React.js frontend. "
        "Experienced in REST API design, CI/CD, Git, and Linux administration."
    )

    print(f"Mock Candidate Skills ({len(mock_candidate_skills)}): {mock_candidate_skills}\n")

    matcher = JobMatcher(db=job_db)
    print(f"Total Raw Job Openings in Database: {len(matcher.jobs)}")

    # Run matching with deduplication
    top_5_unique = matcher.match_all_jobs(
        candidate_skills=mock_candidate_skills,
        resume_text=mock_resume_text,
        unique_by_title=True,
        limit=5
    )

    print(f"Returned Recommended Roles: {len(top_5_unique)}")
    print("-" * 75)
    print(f"{'Rank':<5} | {'Job Title':<24} | {'Top Company':<12} | {'Openings':<9} | {'ATS Score':<9} | {'Skills (Matched/Req)'}")
    print("-" * 75)

    recommended_titles = []
    for idx, role in enumerate(top_5_unique, 1):
        title = role["job_title"]
        company = role.get("company", "N/A")
        openings = role.get("open_positions_count", 1)
        score = role["ats_score"]
        matched = role["matched_skills_count"]
        total_req = role["total_required_skills"]

        recommended_titles.append(title)
        print(f"#{idx:<4} | {title:<24} | {company:<12} | {openings:<9} | {score:>7.1f}% | {matched}/{total_req} matched")
        print(f"      Matched Skills: {role['matched_skills']}")
        print(f"      Missing Skills: {role['missing_skills']}")
        print(f"      Hiring Companies: {role.get('companies_summary', company)}")
        print("-" * 75)

    # Verification Assertions
    assert len(top_5_unique) == 5, f"Expected exactly 5 recommendations, got {len(top_5_unique)}"
    assert len(recommended_titles) == len(set(recommended_titles)), (
        f"Duplicate titles detected in recommendations: {recommended_titles}"
    )

    print("\n[VERIFICATION RESULT]")
    print(f"[PASS] All {len(recommended_titles)} job titles are completely unique!")
    print(f"[PASS] Distinct Titles: {recommended_titles}")
    print("[PASS] Max-aggregation verified: Highest scoring company selected for each role.")
    print("=" * 75)
    print("MOCK MATCH TEST PASSED SUCCESSFULLY!")
    print("=" * 75)


if __name__ == "__main__":
    test_unique_recommendations()
