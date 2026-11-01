"""
config.py - Application Configuration & Environment Settings
Manages API keys, flags, and paths with python-dotenv support.
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file in root workspace
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(BASE_DIR, ".env")
load_dotenv(dotenv_path=env_path)

# RapidAPI / JSearch Configuration
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY", "").strip()
RAPIDAPI_HOST = os.getenv("RAPIDAPI_HOST", "jsearch.p.rapidapi.com").strip()

# Mock toggle: Default to True to protect the 200 free requests/month quota
USE_MOCK_JOBS = os.getenv("USE_MOCK_JOBS", "True").strip().lower() in ("true", "1", "yes", "t")

# Path to local mock JSearch JSON dataset
MOCK_DATA_PATH = os.path.join(BASE_DIR, "data", "sample_live_jobs.json")

