"""Validation tests for search-only job recommendation links."""

from unittest.mock import Mock, patch

import config
import requests
from app import attach_search_urls
from services.live_job_service import (
    build_search_url,
    find_active_apply_link,
    get_valid_apply_link,
    get_job_vacancies,
    is_link_active,
    normalize_job_search_urls,
)


def run_tests():
    with patch("services.live_job_service.requests.head") as mock_head:
        mock_head.return_value.status_code = 200
        assert is_link_active("https://jobs.example.com/active") is True
        mock_head.assert_called_once_with(
            "https://jobs.example.com/active",
            allow_redirects=True,
            timeout=3,
        )

    with (
        patch("services.live_job_service.requests.head") as mock_head,
        patch("services.live_job_service.requests.get") as mock_get,
    ):
        mock_head.return_value.status_code = 404
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        assert is_link_active("https://jobs.example.com/dead") is False
        mock_get.assert_called_once_with(
            "https://jobs.example.com/dead",
            allow_redirects=True,
            timeout=3,
            stream=True,
        )
        mock_response.close.assert_called_once()

    with (
        patch(
            "services.live_job_service.requests.head",
            side_effect=requests.exceptions.Timeout("HEAD timed out"),
        ),
        patch("services.live_job_service.requests.get") as mock_get,
    ):
        mock_get.return_value.status_code = 200
        assert is_link_active("https://jobs.example.com/head-unsupported") is True
        mock_get.assert_called_once()

    job_with_secondary = {
        "job_apply_link": "https://jobs.example.com/dead",
        "apply_options": [
            {"publisher": "Example", "apply_link": "https://jobs.example.com/active"}
        ],
    }
    with (
        patch(
            "services.live_job_service.requests.head",
            side_effect=[Mock(status_code=404), Mock(status_code=200)],
        ),
        patch(
            "services.live_job_service.requests.get",
            return_value=Mock(status_code=404),
        ) as mock_get,
    ):
        assert find_active_apply_link(job_with_secondary) == "https://jobs.example.com/active"
        mock_get.assert_called_once()

    with (
        patch(
            "services.live_job_service.requests.head",
            side_effect=[
                Mock(status_code=404),
                Mock(status_code=404),
                Mock(status_code=404),
                Mock(status_code=404),
            ],
        ),
        patch(
            "services.live_job_service.requests.get",
            return_value=Mock(status_code=404),
        ),
    ):
        assert find_active_apply_link(job_with_secondary) is None
        assert get_valid_apply_link(
            {
                **job_with_secondary,
                "job_title": "Senior Data Engineer",
                "employer_name": "Acme & Sons",
            }
        ) == (
            "https://www.google.com/search?q=Acme%20%26%20Sons%20"
            "Senior%20Data%20Engineer%20apply"
        )

    job = {
        "job_title": "Senior Data Engineer",
        "employer_name": "Acme & Sons",
        "location": "Seattle, WA",
        "job_apply_link": "https://jobs.example.com/expired",
        "apply_options": [
            {"publisher": "Example", "apply_link": "https://jobs.example.com/expired-too"}
        ],
        "job_google_link": "https://www.google.com/search?q=stale",
        "apply_url": "https://jobs.example.com/expired",
        "apply_link": "https://jobs.example.com/expired",
        "search_fallback_url": "https://www.google.com/search?q=stale",
    }

    normalized = normalize_job_search_urls([job])[0]
    assert normalized["search_url"] == (
        "https://www.google.com/search?q=Acme%20%26%20Sons%20"
        "Senior%20Data%20Engineer%20apply"
    )
    assert not any(
        field in normalized
        for field in (
            "job_apply_link",
            "job_google_link",
            "apply_url",
            "apply_link",
            "search_fallback_url",
            "apply_options",
        )
    )

    frontend_job = {
        "job_title": "Platform Engineer",
        "company": "Example Corp",
        "location": "Remote",
        "apply_url": "https://jobs.example.com/dead",
        "job_apply_link": "https://jobs.example.com/dead",
    }
    attach_search_urls([frontend_job])
    assert frontend_job["search_url"] == (
        "https://www.google.com/search?q=Platform+Engineer+Example+Corp+apply"
    )
    assert "apply_url" not in frontend_job and "job_apply_link" not in frontend_job

    assert build_search_url({"job_title": "QA Engineer", "employer_name": "Example"}) == (
        "https://www.google.com/search?q=Example%20QA%20Engineer%20apply"
    )

    api_job = {
        "job_id": "fallback-job",
        "job_title": "Senior Data Engineer",
        "employer_name": "Acme & Sons",
        "job_country": "IN",
        "job_apply_link": "https://jobs.example.com/dead",
        "apply_options": [
            {"publisher": "Example", "apply_link": "https://jobs.example.com/dead-too"}
        ],
    }
    api_response = Mock()
    api_response.json.return_value = {"data": [api_job]}
    with (
        patch.object(config, "USE_MOCK_JOBS", False),
        patch.object(config, "RAPIDAPI_KEY", "test-api-key"),
        patch("services.live_job_service.requests.get", return_value=api_response) as mock_api_get,
        patch("services.live_job_service.is_link_active", return_value=False),
    ):
        fetched_jobs = get_job_vacancies()
        assert mock_api_get.call_args.kwargs["params"]["date_posted"] == "week"
        assert fetched_jobs[0]["validated_apply_link"] == (
            "https://www.google.com/search?q=Acme%20%26%20Sons%20"
            "Senior%20Data%20Engineer%20apply"
        )

    print("All search-only job URL tests passed.")


if __name__ == "__main__":
    run_tests()
