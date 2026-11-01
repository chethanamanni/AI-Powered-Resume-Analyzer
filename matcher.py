"""
matcher.py - ATS Scoring, Role Matching & Skill Gap Analysis
Utilizes Scikit-learn (TfidfVectorizer & Cosine Similarity) along with
database job queries to generate ATS scores, recommend jobs, and detect skill gaps.
"""

import os
import json
import urllib.parse
from typing import Dict, List, Any, Optional, Tuple
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from database import JobDatabase, job_db


class JobMatcher:
    """Matches parsed resume profiles against dynamic database job roles or custom job descriptions."""

    def __init__(self, db: Optional[JobDatabase] = None, jobs_path: Optional[str] = None):
        """
        Initialize matcher.
        Prioritizes querying SQLite database (jobs.db); falls back to jobs.json if DB unavailable.
        """
        self.db = db or job_db
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.jobs_path = jobs_path or os.path.join(base_dir, "jobs.json")
        self.role_catalog_path = os.path.join(base_dir, "role_catalog.json")
        self.standard_roles: List[Dict[str, Any]] = []
        self.evaluation_framework: Dict[str, Any] = {}
        self._load_standard_roles()
        self.reload_jobs()

    def _load_standard_roles(self) -> None:
        """Load curated role profiles used by the role selector."""
        try:
            with open(self.role_catalog_path, "r", encoding="utf-8") as f:
                catalog = json.load(f)
            self.standard_roles = catalog.get("roles", [])
            self.evaluation_framework = catalog.get("evaluation_framework", {})
        except (OSError, json.JSONDecodeError) as e:
            print(f"[MATCHER WARNING] Failed to load role catalog: {e}")
            self.standard_roles = []
            self.evaluation_framework = {}

    def get_standard_roles(self) -> List[Dict[str, Any]]:
        """Return curated standard roles for job-specification selection."""
        return self.standard_roles

    def get_standard_role_by_id(self, role_id: str) -> Optional[Dict[str, Any]]:
        """Find a curated role by its stable catalog ID."""
        return next(
            (role for role in self.standard_roles if role.get("id") == role_id),
            None
        )

    def get_evaluation_framework(self) -> Dict[str, Any]:
        """Return the shared candidate evaluation rubric and KPI guidance."""
        return self.evaluation_framework

    def reload_jobs(self):
        """Reload job profiles from database."""
        self.jobs = []
        try:
            if self.db:
                self.jobs = self.db.get_all_jobs()
        except Exception as e:
            print(f"[MATCHER WARNING] Failed to load jobs from database: {e}")

        # Fallback to jobs.json if database returned no records
        if not self.jobs and os.path.exists(self.jobs_path):
            try:
                with open(self.jobs_path, "r", encoding="utf-8") as f:
                    self.jobs = json.load(f)
                print(f"[MATCHER] Loaded {len(self.jobs)} fallback jobs from jobs.json.")
            except Exception as e:
                print(f"[MATCHER ERROR] Failed to load fallback jobs.json: {e}")

    def get_all_jobs(self) -> List[Dict[str, Any]]:
        """Return the list of all available job roles."""
        return self.jobs

    def get_job_by_id(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Find a job by its unique identifier."""
        # 1. Query DB directly for most up-to-date details
        try:
            if self.db:
                job = self.db.get_job_by_id(job_id)
                if job:
                    return job
        except Exception:
            pass

        # 2. In-memory fallback
        for job in self.jobs:
            if job.get("id") == job_id or job.get("Job_ID") == job_id:
                return job
        return None

    def get_jobs_by_role_name(self, role_name: str) -> List[Dict[str, Any]]:
        """Find all job postings matching a given role title or ID (case-insensitive)."""
        role_lower = role_name.strip().lower()
        matching = []
        for job in self.jobs:
            if (
                job.get("title", "").strip().lower() == role_lower
                or job.get("id", "").strip().lower() == role_lower
                or job.get("category", "").strip().lower() == role_lower
            ):
                matching.append(job)
        return matching

    def calculate_tfidf_similarity(self, resume_text: str, job_text: str) -> float:
        """
        Calculate TF-IDF Cosine Similarity score between resume and job text.
        Returns a percentage value between 0.0 and 100.0.
        """
        if not resume_text.strip() or not job_text.strip():
            return 0.0

        vectorizer = TfidfVectorizer(
            ngram_range=(1, 2),
            stop_words="english",
            max_features=5000
        )
        try:
            tfidf_matrix = vectorizer.fit_transform([resume_text, job_text])
            similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
            # Cosine similarity for full documents typically ranges 0.10 - 0.65.
            scaled_score = min(100.0, float(similarity * 150))
            return round(scaled_score, 1)
        except Exception:
            return 0.0

    def evaluate_role_match(
        self,
        candidate_skills: List[str],
        resume_text: str,
        job: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Evaluate a candidate profile against a specific job role.
        Calculates:
        - Matched skills
        - Missing skills (Skill Gap)
        - Skill coverage percentage
        - TF-IDF similarity score
        - Composite ATS Score
        - Actionable recommendations
        """
        candidate_skills_set = set(s.lower() for s in candidate_skills)
        required_skills = [s.lower() for s in job.get("required_skills", [])]
        recommended_skills = [s.lower() for s in job.get("recommended_skills", [])]

        # 1. Skill Gap Analysis
        matched_skills = [s for s in required_skills if s in candidate_skills_set]
        missing_skills = [s for s in required_skills if s not in candidate_skills_set]
        matched_recommended = [s for s in recommended_skills if s in candidate_skills_set]

        # Skill coverage calculation
        if required_skills:
            coverage_pct = (len(matched_skills) / len(required_skills)) * 100.0
        else:
            coverage_pct = 100.0

        # Recommended skills bonus (up to 10 extra points)
        rec_bonus = 0.0
        if recommended_skills:
            rec_bonus = (len(matched_recommended) / len(recommended_skills)) * 10.0

        raw_skill_score = min(100.0, coverage_pct + rec_bonus)

        # 2. Textual TF-IDF Similarity
        job_document = (
            f"{job.get('title', '')} {job.get('company', '')} {job.get('description', '')} "
            f"{' '.join(required_skills)} {' '.join(recommended_skills)}"
        )
        tfidf_score = self.calculate_tfidf_similarity(resume_text, job_document)

        # 3. Composite ATS Score (Weighted: 65% Skill Match + 35% Contextual TF-IDF)
        ats_score = round((0.65 * raw_skill_score) + (0.35 * tfidf_score), 1)
        ats_score = max(0.0, min(100.0, ats_score))

        # Qualitative Rating
        if ats_score >= 75.0:
            rating = "Strong Match"
            rating_color = "#10b981"  # Emerald
        elif ats_score >= 50.0:
            rating = "Moderate Match"
            rating_color = "#f59e0b"  # Amber
        else:
            rating = "Low Match"
            rating_color = "#ef4444"  # Rose

        # Actionable Recommendations for skill gaps
        recommendations = []
        if missing_skills:
            top_missing = missing_skills[:4]
            recommendations.append(
                f"Prioritize acquiring fundamental knowledge in: {', '.join(top_missing).title()}."
            )
            recommendations.append(
                "Incorporate hands-on projects or certifications featuring these missing skills into your resume."
            )
        if len(matched_skills) < len(required_skills) * 0.5:
            recommendations.append(
                "Highlight relevant coursework, open-source contributions, or transferable tools aligned with this role."
            )
        if ats_score >= 75.0:
            recommendations.append(
                "Strong technical alignment! Ensure project bullet points emphasize quantitative business impact (e.g., % latency reduced, $ saved)."
            )

        # Keep the learning plan structured so every role selection can render
        # the same chronological experience in the dashboard and report.
        learning_roadmap = []
        for skill in missing_skills:
            skill_title = skill.title()
            learning_roadmap.append({
                "skill": skill_title,
                "steps": [
                    {
                        "step": 1,
                        "title": "Core Fundamentals",
                        "description": f"Learn the core concepts, terminology, and standard workflows for {skill_title}.",
                        "timeframe": "1-2 weeks"
                    },
                    {
                        "step": 2,
                        "title": "Hands-on Projects",
                        "description": f"Build a small {skill_title} project using realistic role-related data or tasks.",
                        "timeframe": "2-3 weeks"
                    },
                    {
                        "step": 3,
                        "title": "Portfolio / Certification",
                        "description": f"Document measurable outcomes and add the {skill_title} project to your portfolio, or complete a recognized assessment.",
                        "timeframe": "1-2 weeks"
                    }
                ]
            })

        career_guidance = [
            f"Prioritize {len(missing_skills)} missing required skill(s) for {job.get('title', 'this role')}."
            if missing_skills else
            f"Maintain your required-skill coverage for {job.get('title', 'this role')} through progressively harder projects.",
            "Translate each learning project into a quantified resume bullet that shows business or user impact.",
            "Re-run the analysis after completing each roadmap milestone to track your ATS improvement."
        ]
        if missing_skills:
            career_guidance.insert(
                1,
                f"Start with {missing_skills[0].title()} and follow the roadmap in order before adding another gap."
            )

        # Generate safe search fallback link for role
        role_title = (job.get("title") or "Software Engineer").strip()
        role_company = (job.get("company") or "").strip()
        role_search_parts = [p for p in [role_title, role_company, "apply"] if p]
        role_apply_link = f"https://www.google.com/search?q={urllib.parse.quote_plus(' '.join(role_search_parts))}"
        safe_link = job.get("apply_link") or job.get("job_apply_link") or role_apply_link

        return {
            "job_id": job.get("id"),
            "job_title": job.get("title"),
            "company": job.get("company", "Tech Enterprise"),
            "location": job.get("location", "Flexible"),
            "salary_lpa": job.get("salary_lpa", "Competitive"),
            "employment_type": job.get("employment_type", "Full-time"),
            "category": job.get("category", job.get("title", "Engineering")),
            "experience_level": job.get("experience_level", "Mid Level"),
            "apply_link": safe_link,
            "job_apply_link": safe_link,
            "ats_score": ats_score,
            "rating": rating,
            "rating_color": rating_color,
            "skill_coverage_pct": round(coverage_pct, 1),
            "matched_skills_count": len(matched_skills),
            "total_required_skills": len(required_skills),
            "matched_skills": matched_skills,
            "missing_skills": missing_skills,
            "matched_recommended": matched_recommended,
            "tfidf_similarity": tfidf_score,
            "recommendations": recommendations,
            "learning_roadmap": learning_roadmap,
            "career_guidance": career_guidance
        }


    def evaluate_target_role(
        self,
        candidate_skills: List[str],
        resume_text: str,
        target_role_name: str
    ) -> Optional[Dict[str, Any]]:
        """
        Evaluate candidate specifically against a user-selected target job role.
        If multiple database postings exist for that title, max-aggregates by choosing the highest-scoring match.
        """
        matching_jobs = self.get_jobs_by_role_name(target_role_name)
        if not matching_jobs:
            # Try by direct ID
            single = self.get_job_by_id(target_role_name)
            if single:
                matching_jobs = [single]

        if not matching_jobs:
            return None

        evals = [self.evaluate_role_match(candidate_skills, resume_text, j) for j in matching_jobs]
        evals.sort(key=lambda x: x["ats_score"], reverse=True)
        best_eval = evals[0]

        best_eval["open_positions_count"] = len(matching_jobs)
        distinct_companies = list(dict.fromkeys([j.get("company") for j in matching_jobs if j.get("company")]))
        best_eval["hiring_companies"] = distinct_companies
        best_eval["is_target_role"] = True
        return best_eval

    def match_all_jobs(
        self,
        candidate_skills: List[str],
        resume_text: str,
        unique_by_title: bool = True,
        limit: Optional[int] = 5
    ) -> List[Dict[str, Any]]:
        """
        Evaluate candidate against database jobs and rank them in
        descending order of ATS Score.
        """
        all_evals = []
        for job in self.jobs:
            eval_result = self.evaluate_role_match(candidate_skills, resume_text, job)
            all_evals.append(eval_result)

        # If deduplication not requested, return raw sorted list
        if not unique_by_title:
            all_evals.sort(key=lambda x: x["ats_score"], reverse=True)
            if limit and limit > 0:
                return all_evals[:limit]
            return all_evals

        # 1. Group records by normalized job_title
        grouped_by_title: Dict[str, List[Dict[str, Any]]] = {}
        for eval_res in all_evals:
            norm_title = eval_res.get("job_title", "").strip().title()
            title_key = norm_title.lower()
            if not title_key:
                continue
            if title_key not in grouped_by_title:
                grouped_by_title[title_key] = []
            grouped_by_title[title_key].append(eval_res)

        # 2. For each unique job role, max-aggregate to select the highest-scoring posting
        unique_ranked_roles = []
        for title_key, job_group in grouped_by_title.items():
            # Sort this role's postings by ATS score descending
            job_group.sort(key=lambda x: x["ats_score"], reverse=True)
            best_match = job_group[0]

            # Aggregate multiple openings data
            openings_count = len(job_group)
            distinct_companies = list(dict.fromkeys([
                j.get("company") for j in job_group if j.get("company")
            ]))

            best_match["open_positions_count"] = openings_count
            best_match["hiring_companies"] = distinct_companies
            if len(distinct_companies) > 1:
                summary_companies = ", ".join(distinct_companies[:2])
                extra = len(distinct_companies) - 2
                best_match["companies_summary"] = (
                    f"{summary_companies} +{extra} more" if extra > 0 else summary_companies
                )
            else:
                best_match["companies_summary"] = distinct_companies[0] if distinct_companies else best_match.get("company", "")

            unique_ranked_roles.append(best_match)

        # 3. Sort unique job roles by highest match score
        unique_ranked_roles.sort(key=lambda x: x["ats_score"], reverse=True)

        # 4. Limit to requested count
        if limit and limit > 0:
            return unique_ranked_roles[:limit]
        return unique_ranked_roles

    def evaluate_with_target_role(
        self,
        candidate_skills: List[str],
        resume_text: str,
        target_role: str = "all",
        custom_title: str = "",
        custom_description: str = "",
        limit_secondary: int = 5
    ) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """
        Evaluates a user-selected target job role (or best fit) and generates
        secondary job recommendations for alternative roles.
        Returns:
            (target_analysis, secondary_recommendations)
        """
        # Compute all unique role evaluations
        all_unique_roles = self.match_all_jobs(
            candidate_skills=candidate_skills,
            resume_text=resume_text,
            unique_by_title=True,
            limit=None
        )

        target_analysis = None

        if target_role.startswith("catalog:"):
            role_id = target_role.removeprefix("catalog:")
            standard_role = self.get_standard_role_by_id(role_id)
            if standard_role:
                target_analysis = self.evaluate_role_match(
                    candidate_skills=candidate_skills,
                    resume_text=resume_text,
                    job={
                        "id": standard_role["id"],
                        "title": standard_role["title"],
                        "category": standard_role["department"],
                        "description": " ".join(standard_role["core_responsibilities"]),
                        "required_skills": standard_role["required_skills"],
                        "recommended_skills": standard_role["tech_stack"],
                    }
                )
                target_analysis["kpis"] = standard_role.get("kpis", [])
                target_analysis["seniority_levels"] = standard_role.get("seniority_levels", [])
                target_analysis["role_profile"] = standard_role
                target_analysis["is_selected_target"] = True
                secondary_recommendations = all_unique_roles[:limit_secondary]
            else:
                target_analysis = None
                secondary_recommendations = all_unique_roles[:limit_secondary]
        elif target_role == "custom" and custom_description:
            target_analysis = self.analyze_custom_job(
                candidate_skills=candidate_skills,
                resume_text=resume_text,
                job_title=custom_title or "Custom Target Role",
                job_description=custom_description
            )
            target_analysis["is_selected_target"] = True
            # Secondary recommendations: top unique roles from database
            secondary_recommendations = all_unique_roles[:limit_secondary]

        elif target_role and target_role.strip().lower() != "all":
            # User selected a specific target role
            target_analysis = self.evaluate_target_role(candidate_skills, resume_text, target_role)
            if not target_analysis and all_unique_roles:
                target_analysis = all_unique_roles[0]
                target_analysis["is_selected_target"] = False
            else:
                target_analysis["is_selected_target"] = True

            # Filter out the target role title from secondary recommendations
            target_title_lower = target_analysis.get("job_title", "").strip().lower()
            secondary_recommendations = [
                r for r in all_unique_roles
                if r.get("job_title", "").strip().lower() != target_title_lower
            ][:limit_secondary]

        else:
            # Auto-Recommend: top match becomes target, remaining become secondary recommendations
            if all_unique_roles:
                target_analysis = all_unique_roles[0]
                target_analysis["is_selected_target"] = False
                secondary_recommendations = all_unique_roles[1:limit_secondary + 1]
            else:
                target_analysis = None
                secondary_recommendations = []

        return target_analysis, secondary_recommendations

    def analyze_custom_job(
        self,
        candidate_skills: List[str],
        resume_text: str,
        job_title: str,
        job_description: str,
        custom_skills: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Analyze a candidate against an ad-hoc custom job description provided by the user.
        """
        if custom_skills is None or len(custom_skills) == 0:
            from parser import ResumeParser
            parser = ResumeParser()
            custom_skills = parser.extract_skills(job_description)

        custom_job = {
            "id": "custom_job",
            "title": job_title if job_title.strip() else "Custom Job Role",
            "company": "Custom Job",
            "location": "Custom",
            "salary_lpa": "Not Disclosed",
            "employment_type": "Full-time",
            "category": "Custom",
            "experience_level": "Custom",
            "description": job_description,
            "required_skills": custom_skills,
            "recommended_skills": []
        }

        return self.evaluate_role_match(candidate_skills, resume_text, custom_job)
