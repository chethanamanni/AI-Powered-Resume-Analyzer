"""
services/live_job_service.py - Real-Time Live Job Recommendation Service
Fetches live vacancies from JSearch API (RapidAPI) across LinkedIn, Indeed, Glassdoor.
Features mock toggle mode (USE_MOCK_JOBS) to protect free API quotas during development.
Matches live vacancies against parsed resume skills using Scikit-learn TF-IDF & Cosine Similarity.
Generates Google search URLs for live job recommendations.
"""

import os
import json
import logging
import re
import urllib.parse
from typing import List, Dict, Any, Optional
import requests
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

import config
from parser import ResumeParser

logger = logging.getLogger(__name__)

# Shared ResumeParser instance for extracting skills from job descriptions
_parser_instance: Optional[ResumeParser] = None


def get_parser() -> ResumeParser:
    """Lazy-load the shared ResumeParser singleton."""
    global _parser_instance
    if _parser_instance is None:
        _parser_instance = ResumeParser()
    return _parser_instance


def build_search_url(job: Dict[str, Any]) -> str:
    """Build a Google search for the job title, employer, and active postings."""
    title = str(job.get("job_title") or "Software Engineer").strip()
    employer = str(job.get("employer_name") or "").strip()
    query = f"{employer} {title} apply".strip()
    return f"https://www.google.com/search?q={urllib.parse.quote(query)}"


def is_link_active(url: str, timeout: int = 3) -> bool:
    """Return whether a URL responds successfully, falling back from HEAD to GET."""
    if not isinstance(url, str) or not url.strip():
        return False

    try:
        response = requests.head(url, allow_redirects=True, timeout=timeout)
        try:
            if response.status_code < 400:
                return True
        finally:
            response.close()
    except requests.exceptions.RequestException as exc:
        logger.debug("HEAD request failed for application URL %s: %s", url, exc)

    try:
        response = requests.get(
            url,
            allow_redirects=True,
            timeout=timeout,
            stream=True,
        )
        try:
            return response.status_code < 400
        finally:
            response.close()
    except requests.exceptions.RequestException as exc:
        logger.debug("GET request failed for application URL %s: %s", url, exc)
        return False


def _apply_link_candidates(job: Dict[str, Any]) -> List[str]:
    """Return unique primary and JSearch secondary application URLs."""
    candidates = []
    primary = job.get("job_apply_link")
    if isinstance(primary, str) and primary.strip():
        candidates.append(primary.strip())

    apply_options = job.get("apply_options", [])
    if isinstance(apply_options, list):
        for option in apply_options:
            if not isinstance(option, dict):
                continue
            for field in ("apply_link", "job_apply_link", "link", "url"):
                candidate = option.get(field)
                if isinstance(candidate, str) and candidate.strip():
                    candidates.append(candidate.strip())
                    break

    return list(dict.fromkeys(candidates))


def find_active_apply_link(job: Dict[str, Any], timeout: int = 3) -> Optional[str]:
    """Return the first active primary or secondary application URL."""
    for candidate in _apply_link_candidates(job):
        if is_link_active(candidate, timeout=timeout):
            return candidate
    return None


def get_valid_apply_link(job: Dict[str, Any]) -> str:
    """Return an active application URL or a Google search fallback."""
    active_link = find_active_apply_link(job)
    if active_link:
        return active_link

    employer = str(job.get("employer_name") or "").strip()
    title = str(job.get("job_title") or "").strip()
    query = f"{employer} {title} apply".strip()
    return f"https://www.google.com/search?q={urllib.parse.quote(query)}"


def _attach_validated_apply_links(jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Attach an active application URL or search fallback to every job."""
    for job in jobs:
        job["validated_apply_link"] = get_valid_apply_link(job)
    return jobs


def normalize_job_search_urls(jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Remove provider application URLs and retain a generated Google search URL."""
    for job in jobs:
        for field in (
            "job_apply_link",
            "job_google_link",
            "apply_url",
            "apply_link",
            "search_fallback_url",
            "apply_options",
        ):
            job.pop(field, None)
        job["search_url"] = build_search_url(job)
    return jobs


def filter_indian_jobs(jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Keep only vacancies identified as being in India."""
    indian_jobs = []
    for job in jobs:
        country = str(job.get("job_country") or "").strip()
        location = " ".join(
            str(job.get(field) or "")
            for field in ("job_location", "job_location_name", "job_city", "job_state", "job_country")
        )
        if country.upper() == "IN" or re.search(r"\bindia\b", location, re.IGNORECASE):
            indian_jobs.append(job)
    return indian_jobs


def get_job_vacancies(query: str = "Software Engineer", location: str = "Remote") -> List[Dict[str, Any]]:
    """
    Fetch job vacancies from either local mock dataset or live RapidAPI JSearch endpoint.

    Parameters:
        query: Target job title or skill keywords (e.g., 'Python Developer', 'DevOps')
        location: Target geographic location or 'Remote'

    Returns:
        List of raw job dictionaries conforming to JSearch schema with validated apply links.
    """
    clean_query = (query or "Software Engineer").strip()
    clean_location = (location or "Remote").strip()

    # -------------------------------------------------------------
    # 1. Mock Toggle Mode: Preserves API quota during development
    # -------------------------------------------------------------
    if config.USE_MOCK_JOBS:
        logger.info(f"[LIVE JOBS MOCK] Mock mode is active (USE_MOCK_JOBS=True). Loading {config.MOCK_DATA_PATH}")
        try:
            if not os.path.exists(config.MOCK_DATA_PATH):
                logger.error(f"[LIVE JOBS MOCK] Mock data file not found at {config.MOCK_DATA_PATH}")
                return []

            with open(config.MOCK_DATA_PATH, "r", encoding="utf-8") as f:
                payload = json.load(f)

            raw_jobs = payload.get("data", [])
            logger.info(f"[LIVE JOBS MOCK] Successfully loaded {len(raw_jobs)} mock vacancies.")

            # Filter relevant mock jobs if specific search query provided
            if clean_query and clean_query.lower() not in ("all", "software engineer", "developer"):
                q_words = [w.lower() for w in clean_query.split() if len(w) > 2]
                matched = []
                for job in raw_jobs:
                    title_desc = f"{job.get('job_title', '')} {job.get('job_description', '')}".lower()
                    if any(w in title_desc for w in q_words):
                        matched.append(job)
                # If specific filter found jobs, return filtered list; otherwise return all mock jobs
                if matched:
                    return normalize_job_search_urls(
                        _attach_validated_apply_links(filter_indian_jobs(matched))
                    )

            return normalize_job_search_urls(
                _attach_validated_apply_links(filter_indian_jobs(raw_jobs))
            )

        except Exception as e:
            logger.error(f"[LIVE JOBS MOCK ERROR] Failed reading mock dataset: {e}", exc_info=True)
            return []

    # -------------------------------------------------------------
    # 2. Live API Mode: Sends GET request to JSearch via RapidAPI
    # -------------------------------------------------------------
    logger.info(f"[LIVE JOBS API] Live mode active. Querying JSearch API for: '{clean_query}' in '{clean_location}'")

    if not config.RAPIDAPI_KEY or config.RAPIDAPI_KEY == "your_rapidapi_key_here":
        logger.warning(
            "[LIVE JOBS API WARNING] No valid RAPIDAPI_KEY configured in .env. Falling back to local mock data to prevent crashes."
        )
        return get_job_vacancies_mock_fallback()

    url = f"https://{config.RAPIDAPI_HOST}/search"
    if clean_location.casefold() == "remote":
        search_term = f"{clean_query} remote in India"
    elif clean_location.casefold() == "india":
        search_term = f"{clean_query} in India"
    elif re.search(r"\bindia\b", clean_location, re.IGNORECASE):
        search_term = f"{clean_query} in {clean_location}"
    else:
        search_term = f"{clean_query} in {clean_location}, India"

    headers = {
        "X-RapidAPI-Key": config.RAPIDAPI_KEY,
        "X-RapidAPI-Host": config.RAPIDAPI_HOST
    }

    params = {
        "query": search_term,
        "page": "1",
        "num_pages": "1",
        "date_posted": "week",
    }

    try:
        response = requests.get(url, headers=headers, params=params, timeout=12)
        response.raise_for_status()

        data = response.json()
        job_list = data.get("data", [])
        indian_jobs = filter_indian_jobs(job_list)
        logger.info(
            "[LIVE JOBS API] Received %s postings from JSearch; %s are in India.",
            len(job_list),
            len(indian_jobs),
        )
        return normalize_job_search_urls(_attach_validated_apply_links(indian_jobs))

    except requests.exceptions.RequestException as e:
        logger.error(f"[LIVE JOBS API ERROR] HTTP request to JSearch failed: {e}. Falling back to mock data.")
        return get_job_vacancies_mock_fallback()


def get_job_vacancies_mock_fallback() -> List[Dict[str, Any]]:
    """Helper fallback to return mock data if live API fails or key is missing."""
    if os.path.exists(config.MOCK_DATA_PATH):
        try:
            with open(config.MOCK_DATA_PATH, "r", encoding="utf-8") as f:
                jobs = json.load(f).get("data", [])
                return normalize_job_search_urls(
                    _attach_validated_apply_links(filter_indian_jobs(jobs))
                )
        except (OSError, json.JSONDecodeError) as exc:
            logger.error(
                "[LIVE JOBS MOCK ERROR] Failed reading fallback mock dataset: %s",
                exc,
                exc_info=True,
            )
    return []


def format_salary(job: Dict[str, Any]) -> str:
    """Format salary information from JSearch job schema."""
    min_sal = job.get("job_min_salary")
    max_sal = job.get("job_max_salary")
    currency = job.get("job_salary_currency", "USD")
    period = job.get("job_salary_period", "year").lower()

    if min_sal and max_sal:
        return f"{currency} {min_sal:,.0f} - {max_sal:,.0f} / {period}"
    elif min_sal:
        return f"{currency} {min_sal:,.0f}+ / {period}"
    elif max_sal:
        return f"Up to {currency} {max_sal:,.0f} / {period}"
    return "Salary Not Disclosed"


def format_location(job: Dict[str, Any]) -> str:
    """Format city, state, country, and remote status."""
    city = job.get("job_city")
    state = job.get("job_state")
    country = job.get("job_country")
    if str(country or "").strip().upper() == "IN":
        country = "India"
    is_remote = job.get("job_is_remote", False)

    parts = [p for p in (city, state, country) if p]
    base_loc = ", ".join(parts) if parts else "Location Flexible"

    if is_remote:
        return f"{base_loc} (Remote)" if parts else "Remote"
    return base_loc


def match_live_jobs(
    user_skills: List[str],
    job_list: List[Dict[str, Any]],
    resume_text: str = ""
) -> List[Dict[str, Any]]:
    """
    Match live job vacancies against candidate skills and resume text using
    TF-IDF Vectorizer and Cosine Similarity.

    Parameters:
        user_skills: Candidate's extracted technical skills
        job_list: Raw vacancies list from JSearch
        resume_text: Full parsed resume text for contextual TF-IDF comparison

    Returns:
        List of structured job recommendation cards sorted by match percentage descending.
    """
    if not job_list:
        return []

    parser = get_parser()
    candidate_skills_set = set(s.strip().lower() for s in user_skills if s.strip())

    # Text representing candidate profile for TF-IDF
    candidate_document = f"{' '.join(user_skills)} {resume_text}".strip()
    if not candidate_document:
        candidate_document = "software engineer developer"

    ranked_jobs = []

    for job in job_list:
        job_id = job.get("job_id", "")
        title = job.get("job_title", "Software Engineer")
        employer = job.get("employer_name", "Tech Company")
        publisher = job.get("job_publisher", "Job Portal")
        description = job.get("job_description", "")
        logo = job.get("employer_logo")

        search_url = build_search_url(job)

        # 1. Extract technical skills from live job description & title
        combined_job_text = f"{title} {description}"
        detected_job_skills = parser.extract_skills(combined_job_text)

        # Fallback if no skills extracted from description
        if not detected_job_skills:
            # Check highlights/qualifications
            highlights = job.get("job_highlights", {}).get("Qualifications", [])
            for h in highlights:
                detected_job_skills.extend(parser.extract_skills(h))
            detected_job_skills = sorted(list(set(detected_job_skills)))

        # 2. Skill Gap Analysis
        matched_skills = [s for s in detected_job_skills if s.lower() in candidate_skills_set]
        missing_skills = [s for s in detected_job_skills if s.lower() not in candidate_skills_set]

        # Skill coverage calculation (0 - 100)
        if detected_job_skills:
            skill_coverage = (len(matched_skills) / len(detected_job_skills)) * 100.0
        else:
            # If no specific skills detected, check candidate overlap directly
            skill_coverage = 40.0

        # 3. Contextual TF-IDF Cosine Similarity
        tfidf_similarity = 0.0
        try:
            vectorizer = TfidfVectorizer(ngram_range=(1, 2), stop_words="english", max_features=4000)
            tfidf_matrix = vectorizer.fit_transform([candidate_document, combined_job_text])
            raw_cosine = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
            # Scale cosine similarity (typically 0.10 - 0.60) to 0 - 100%
            tfidf_similarity = min(100.0, float(raw_cosine * 150))
        except Exception:
            tfidf_similarity = 0.0

        # 4. Composite ATS Match Score (60% Skill Match + 40% TF-IDF Cosine Similarity)
        match_score = round((0.60 * skill_coverage) + (0.40 * tfidf_similarity), 1)
        match_score = max(5.0, min(99.0, match_score))

        # Qualitative Rating
        if match_score >= 70.0:
            rating = "Strong Match"
            rating_color = "#10b981"  # Emerald
        elif match_score >= 45.0:
            rating = "Moderate Match"
            rating_color = "#f59e0b"  # Amber
        else:
            rating = "Low Match"
            rating_color = "#ef4444"  # Rose

        # Description snippet
        desc_clean = " ".join(description.split())
        desc_snippet = (desc_clean[:220] + "...") if len(desc_clean) > 220 else desc_clean

        ranked_jobs.append({
            "job_id": job_id,
            "job_title": title,
            "employer_name": employer,
            "employer_logo": logo,
            "job_publisher": publisher,
            "search_url": search_url,
            "location": format_location(job),
            "is_remote": bool(job.get("job_is_remote", False)),
            "salary": format_salary(job),
            "match_score": match_score,
            "rating": rating,
            "rating_color": rating_color,
            "skill_coverage_pct": round(skill_coverage, 1),
            "tfidf_similarity": round(tfidf_similarity, 1),
            "matched_skills": matched_skills,
            "missing_skills": missing_skills,
            "matched_skills_count": len(matched_skills),
            "total_detected_skills": len(detected_job_skills),
            "description_snippet": desc_snippet
        })

    # Sort descending by match score
    ranked_jobs.sort(key=lambda x: x["match_score"], reverse=True)
    return ranked_jobs
