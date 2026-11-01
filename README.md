# AI-Powered Resume Analyzer with Intelligent Job Recommendation & Skill Gap Analysis

An advanced, production-ready AI/ML Flask web application that extracts candidate information from resume PDFs (via PyPDF2 & SpaCy), evaluates ATS scores across local database openings, detects technical skill gaps, and streams **real-time live job vacancies** from **LinkedIn, Indeed, and Glassdoor** via the **JSearch API (RapidAPI)** with built-in quota protection.

---

## 🌟 Key Features

1. **Resume Parsing & NLP Extraction (`parser.py`)**:
   - PyPDF2 text extraction with validation heuristics.
   - SpaCy (`en_core_web_sm`) Named Entity Recognition (NER) & PhraseMatcher.
   - Curated technical ontology detecting 150+ skills across programming, web frameworks, databases, cloud, and devops.

2. **Scikit-learn ATS Match Engine (`matcher.py`)**:
   - TF-IDF Vectorizer (unigrams + bigrams) and Cosine Similarity scoring.
   - Composite ATS matching: 65% skill coverage + 35% contextual text similarity.
   - Missing skill gap detection, qualitative ratings, and actionable learning roadmaps.

3. **Dynamic Database Catalog (`database.py` & `jobs.db`)**:
   - SQLite relational database with 180 job postings and 1,822 skill mappings.
   - Target job role selection with deduplication and max-aggregated similarity scoring across multiple company openings.

4. **Real-Time Live Job Recommendation Engine (`services/live_job_service.py`)**:
   - Fetches live vacancies from LinkedIn, Indeed, and Glassdoor using the **JSearch API** on RapidAPI.
   - **Quota Protection Toggle (`USE_MOCK_JOBS`)**: Uses `data/sample_live_jobs.json` during development/testing to preserve the 200 free monthly RapidAPI requests.
   - Scores and ranks live openings against the candidate's parsed resume skills using Scikit-learn TF-IDF & Cosine Similarity.
   - Direct application links, salary disclosures, remote badges, and matched/missing skill indicators.

---

## 🚀 Quick Start Guide

### 1. Prerequisites
- Python 3.10+ (tested with Python 3.12 / 3.14)
- Virtual environment (`venv`)

### 2. Installation
```powershell
# Activate your virtual environment
.\venv\Scripts\Activate.ps1

# Install required dependencies
pip install -r requirements.txt
```

### 3. Environment Configuration (`.env`)
Create or edit the `.env` file in the project root:
```env
# Set USE_MOCK_JOBS=True during development to protect API quota
USE_MOCK_JOBS=True

# RapidAPI Credentials (used when USE_MOCK_JOBS=False)
RAPIDAPI_KEY=your_rapidapi_key_here
RAPIDAPI_HOST=jsearch.p.rapidapi.com
```

### 4. Running the Application
```powershell
python app.py
```
Open your browser and navigate to `http://127.0.0.1:5000`.

---

## 🧪 Testing & Validation

Run the dedicated test suites in your terminal:
```powershell
# Validate Live Job Recommendations & Mock Toggle Mode
python test_live_jobs.py

# Validate Database, Parser, Matcher & Flask Endpoints
python test_pipeline.py
```

---

## 📡 API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Main single-page web dashboard |
| `GET` | `/api/roles` | Distinct job titles available in the local database |
| `GET` | `/api/jobs` | Full catalog of database job postings |
| `POST` | `/api/analyze` | Upload resume PDF or re-evaluate candidate against target role |
| `GET/POST`| `/api/live-recommendations` | Fetch and match real-time live job vacancies (LinkedIn, Indeed, Glassdoor) |

