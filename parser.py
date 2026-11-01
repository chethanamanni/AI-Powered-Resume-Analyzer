"""
parser.py - Resume Parser Module
Extracts plain text, contact info (name, email, phone, links), education,
and technical skills from resume PDF documents using PyPDF2 and SpaCy.
"""

import re
import io
from typing import Dict, List, Any, Optional, Union
import PyPDF2
import spacy
from spacy.matcher import PhraseMatcher


class ResumeParser:
    """Parser class to extract structured candidate information from resume PDFs."""

    RESUME_SECTION_KEYWORDS = (
        "resume",
        "curriculum vitae",
        "professional summary",
        "summary",
        "objective",
        "work experience",
        "professional experience",
        "employment",
        "experience",
        "education",
        "technical skills",
        "skills",
        "projects",
        "certifications",
        "achievements",
    )

    # Curated skill ontology mapped to canonical skill identifiers
    SKILL_ONTOLOGY = {
        # Programming Languages
        "python": ["python", "python3", "py"],
        "javascript": ["javascript", "js", "ecmascript"],
        "typescript": ["typescript", "ts"],
        "java": ["java", "core java", "j2ee"],
        "c++": ["c++", "cpp"],
        "c#": ["c#", "csharp", ".net"],
        "c": ["c language"],
        "go": ["golang", "go language"],
        "ruby": ["ruby", "ruby on rails"],
        "php": ["php", "laravel"],
        "swift": ["swift"],
        "kotlin": ["kotlin"],
        "dart": ["dart"],
        "r": ["r programming", "r language"],
        "scala": ["scala"],
        "bash": ["bash", "shell scripting", "powershell"],
        "rust": ["rust"],

        # Frontend Technologies
        "react": ["react", "react.js", "reactjs"],
        "angular": ["angular", "angularjs", "angular 2+"],
        "vue.js": ["vue", "vue.js", "vuejs"],
        "next.js": ["next.js", "nextjs"],
        "html5": ["html", "html5"],
        "css3": ["css", "css3"],
        "tailwind css": ["tailwind", "tailwind css", "tailwindcss"],
        "bootstrap": ["bootstrap", "bootstrap 5"],
        "redux": ["redux", "redux toolkit"],
        "sass": ["sass", "scss"],
        "webpack": ["webpack", "vite"],
        "responsive design": ["responsive design", "mobile-first design"],

        # Backend & APIs
        "node.js": ["node", "node.js", "nodejs"],
        "express.js": ["express", "express.js", "expressjs"],
        "flask": ["flask"],
        "fastapi": ["fastapi"],
        "django": ["django", "django rest framework"],
        "spring boot": ["spring boot", "spring framework", "spring"],
        "rest api": ["rest api", "restful api", "rest apis", "restful web services"],
        "graphql": ["graphql"],
        "grpc": ["grpc"],
        "microservices": ["microservices", "microservice architecture"],

        # Databases & Storage
        "sql": ["sql", "transact-sql"],
        "mysql": ["mysql"],
        "postgresql": ["postgresql", "postgres"],
        "mongodb": ["mongodb", "mongo"],
        "sqlite": ["sqlite", "sqlite3"],
        "redis": ["redis"],
        "elasticsearch": ["elasticsearch"],
        "cassandra": ["cassandra"],
        "firebase": ["firebase", "firestore"],
        "snowflake": ["snowflake"],
        "bigquery": ["bigquery"],

        # Cloud & DevOps
        "docker": ["docker", "containerization"],
        "kubernetes": ["kubernetes", "k8s"],
        "aws": ["aws", "amazon web services", "ec2", "s3", "lambda"],
        "azure": ["azure", "microsoft azure"],
        "gcp": ["gcp", "google cloud platform", "google cloud"],
        "ci/cd": ["ci/cd", "cicd", "continuous integration", "continuous deployment"],
        "jenkins": ["jenkins"],
        "github actions": ["github actions"],
        "terraform": ["terraform"],
        "ansible": ["ansible"],
        "linux": ["linux", "ubuntu", "centos", "unix"],
        "helm": ["helm"],
        "prometheus": ["prometheus"],
        "grafana": ["grafana"],

        # Data Science & Machine Learning
        "machine learning": ["machine learning", "ml"],
        "deep learning": ["deep learning", "neural networks"],
        "nlp": ["nlp", "natural language processing"],
        "computer vision": ["computer vision", "cv"],
        "scikit-learn": ["scikit-learn", "sklearn"],
        "tensorflow": ["tensorflow", "tf"],
        "pytorch": ["pytorch", "torch"],
        "pandas": ["pandas"],
        "numpy": ["numpy"],
        "scipy": ["scipy"],
        "matplotlib": ["matplotlib"],
        "seaborn": ["seaborn"],
        "data analysis": ["data analysis", "exploratory data analysis", "eda"],
        "statistics": ["statistics", "statistical modeling"],
        "spacy": ["spacy"],
        "hugging face": ["hugging face", "transformers"],
        "opencv": ["opencv"],
        "mlflow": ["mlflow"],
        "jupyter": ["jupyter", "jupyter notebook"],
        "tableau": ["tableau"],
        "powerbi": ["power bi", "powerbi"],

        # Big Data & Data Engineering
        "apache spark": ["spark", "apache spark", "pyspark"],
        "kafka": ["kafka", "apache kafka"],
        "airflow": ["airflow", "apache airflow"],
        "hadoop": ["hadoop", "hdfs"],
        "etl": ["etl", "elt", "data pipeline", "data pipelines"],
        "data warehousing": ["data warehouse", "data warehousing"],
        "dbt": ["dbt"],

        # Mobile Development
        "flutter": ["flutter"],
        "react native": ["react native"],
        "android": ["android", "android sdk"],
        "ios": ["ios", "ios development"],

        # Testing & QA
        "selenium": ["selenium", "selenium webdriver"],
        "pytest": ["pytest"],
        "cypress": ["cypress"],
        "playwright": ["playwright"],
        "postman": ["postman"],
        "api testing": ["api testing"],
        "automation testing": ["automation testing", "test automation", "qa automation"],
        "jest": ["jest"],
        "jmeter": ["jmeter"],
        "cucumber": ["cucumber", "bdd"],

        # Cybersecurity
        "cybersecurity": ["cybersecurity", "information security"],
        "network security": ["network security"],
        "penetration testing": ["penetration testing", "pen testing", "ethical hacking"],
        "vulnerability assessment": ["vulnerability assessment", "vapt"],
        "wireshark": ["wireshark"],
        "siem": ["siem", "splunk"],
        "firewall": ["firewall", "firewalls"],
        "cryptography": ["cryptography", "encryption"],
        "burp suite": ["burp suite"],
        "metasploit": ["metasploit"],
        "owasp": ["owasp", "owasp top 10"],
        "iam": ["iam", "identity and access management"],

        # Version Control & Tools
        "git": ["git", "github", "gitlab", "bitbucket"],
        "jira": ["jira", "agile", "scrum"],
        "figma": ["figma"]
    }

    def __init__(self):
        """Initialize the SpaCy NLP pipeline and PhraseMatcher."""
        try:
            self.nlp = spacy.load("en_core_web_sm")
        except OSError:
            from spacy.cli import download
            download("en_core_web_sm")
            self.nlp = spacy.load("en_core_web_sm")

        self._init_matcher()

    def _init_matcher(self):
        """Build SpaCy phrase matcher using the skills ontology and database catalog."""
        self.matcher = PhraseMatcher(self.nlp.vocab, attr="LOWER")
        self.alias_to_canonical = {}

        # 1. Register predefined curated skill ontology
        for canonical, aliases in self.SKILL_ONTOLOGY.items():
            all_forms = set(aliases + [canonical])
            patterns = []
            for phrase in all_forms:
                self.alias_to_canonical[phrase.lower()] = canonical
                patterns.append(self.nlp.make_doc(phrase.lower()))
            self.matcher.add(canonical, patterns)

        # 2. Dynamically register additional skills from database skills_master table
        try:
            from database import job_db
            db_skills = job_db.get_all_skills_master()
            for s in db_skills:
                skill_name = s.get("Skill_Name", "").strip()
                if skill_name:
                    canonical = skill_name.lower()
                    if canonical not in self.alias_to_canonical:
                        self.alias_to_canonical[canonical] = canonical
                        self.matcher.add(canonical, [self.nlp.make_doc(canonical)])
                    # Check if ATS_Keyword exists as an alias
                    ats_kw = s.get("ATS_Keyword")
                    if ats_kw and isinstance(ats_kw, str):
                        ats_clean = ats_kw.strip().lower()
                        if ats_clean and ats_clean not in self.alias_to_canonical:
                            self.alias_to_canonical[ats_clean] = canonical
                            self.matcher.add(canonical, [self.nlp.make_doc(ats_clean)])
        except Exception:
            pass  # Fallback gracefully if database is not yet initialized

    def extract_text_from_pdf(self, pdf_input: Union[str, io.BytesIO, bytes]) -> str:
        """
        Extract text from PDF file path, BytesIO stream, or raw bytes.
        Cleans extra whitespace and non-printable characters.
        """
        if isinstance(pdf_input, bytes):
            pdf_stream = io.BytesIO(pdf_input)
        elif isinstance(pdf_input, str):
            pdf_stream = open(pdf_input, "rb")
        else:
            pdf_stream = pdf_input

        text_content = []
        try:
            reader = PyPDF2.PdfReader(pdf_stream)
            for page_idx, page in enumerate(reader.pages):
                extracted = page.extract_text()
                if extracted:
                    text_content.append(extracted)
        except Exception as e:
            raise ValueError(f"Failed to extract text from PDF: {str(e)}")
        finally:
            if isinstance(pdf_input, str) and not pdf_stream.closed:
                pdf_stream.close()

        raw_text = "\n".join(text_content)
        # Clean up excess spaces and control characters
        cleaned_text = re.sub(r"[ \t]+", " ", raw_text)
        cleaned_text = re.sub(r"\n\s*\n+", "\n\n", cleaned_text).strip()
        return cleaned_text

    def extract_email(self, text: str) -> Optional[str]:
        """Extract primary email address from resume text."""
        email_pattern = r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+'
        matches = re.findall(email_pattern, text)
        if matches:
            # Filter out obvious false positives like file extensions
            for m in matches:
                m_clean = m.strip().rstrip(".")
                if not m_clean.endswith(('.png', '.jpg', '.pdf', '.docx')):
                    return m_clean
        return None

    def extract_phone(self, text: str) -> Optional[str]:
        """Extract candidate phone number from resume text."""
        # Handles formats: +91 9876543210, (123) 456-7890, +1-555-123-4567, 9876543210
        patterns = [
            r'(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',
            r'(?:\+?91[-.\s]?)?[6-9]\d{9}',  # Indian phone numbers
            r'\b\d{10}\b'
        ]
        for pat in patterns:
            match = re.search(pat, text)
            if match:
                phone = match.group(0).strip()
                # Ensure it's not a year or zip code
                digits_only = re.sub(r'\D', '', phone)
                if len(digits_only) >= 10:
                    return phone
        return None

    def extract_links(self, text: str) -> Dict[str, Optional[str]]:
        """Extract GitHub, LinkedIn, and portfolio links from text."""
        linkedin_pattern = r'(?:https?:\/\/)?(?:www\.)?linkedin\.com\/in\/[a-zA-Z0-9_-]+'
        github_pattern = r'(?:https?:\/\/)?(?:www\.)?github\.com\/[a-zA-Z0-9_-]+'
        portfolio_pattern = r'https?:\/\/(?:www\.)?[a-zA-Z0-9-]+(?:\.[a-zA-Z]{2,})+(?:\/[^\s]*)?'

        linkedin = re.search(linkedin_pattern, text, re.IGNORECASE)
        github = re.search(github_pattern, text, re.IGNORECASE)

        all_urls = re.findall(portfolio_pattern, text)
        portfolio = None
        for url in all_urls:
            if not re.search(r'linkedin|github', url, re.IGNORECASE):
                portfolio = url
                break

        return {
            "linkedin": linkedin.group(0) if linkedin else None,
            "github": github.group(0) if github else None,
            "portfolio": portfolio
        }

    def extract_name(self, text: str) -> Optional[str]:
        """
        Extract candidate name using SpaCy NER PERSON tags and top-of-resume heuristics.
        """
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        header_chunk = "\n".join(lines[:10])  # Search top 10 lines

        doc = self.nlp(header_chunk)
        for ent in doc.ents:
            if ent.label_ == "PERSON":
                candidate = ent.text.strip()
                # Ignore noise and headers
                invalid_words = [
                    "resume", "curriculum", "vitae", "cv", "summary", "experience",
                    "skills", "profile", "education", "contact", "email", "phone",
                    "linkedin", "github", "page", "developer", "engineer"
                ]
                if not any(bad in candidate.lower() for bad in invalid_words):
                    # Names are usually 2 to 4 words with alphabets
                    parts = candidate.split()
                    if 1 <= len(parts) <= 4 and all(p.isalpha() for p in parts):
                        return candidate

        # Fallback heuristic: First non-empty line with 2-3 capitalized words
        for line in lines[:4]:
            words = line.split()
            if 2 <= len(words) <= 3 and all(w.isalpha() and w[0].isupper() for w in words):
                if not any(w.lower() in ["curriculum", "resume", "cv", "profile"] for w in words):
                    return line

        return "Candidate Name Not Found"

    def extract_education(self, text: str) -> List[str]:
        """Extract education degrees, majors, and institutions."""
        degree_patterns = [
            r'\b(?:B\.?Tech|B\.?E\.?|Bachelor of Technology|Bachelor of Engineering)\b.*',
            r'\b(?:M\.?Tech|M\.?E\.?|Master of Technology|Master of Engineering)\b.*',
            r'\b(?:B\.?S\.?|B\.?Sc|Bachelor of Science)\b.*',
            r'\b(?:M\.?S\.?|M\.?Sc|Master of Science)\b.*',
            r'\b(?:B\.?C\.?A|Bachelor of Computer Applications)\b.*',
            r'\b(?:M\.?C\.?A|Master of Computer Applications)\b.*',
            r'\b(?:Ph\.?D|Doctor of Philosophy)\b.*',
            r'\b(?:Diploma in [A-Za-z\s]+)\b.*'
        ]

        found_degrees = []
        for pat in degree_patterns:
            matches = re.finditer(pat, text, re.IGNORECASE)
            for m in matches:
                deg = m.group(0).strip()
                # Truncate at line break or punctuation
                deg = deg.split('\n')[0].strip()
                if len(deg) < 100 and deg not in found_degrees:
                    found_degrees.append(deg)

        # Look for institution clues if degrees were minimal
        institution_patterns = [
            r'([A-Z][A-Za-z\s]+(?:University|Institute of Technology|College of Engineering|College|Academy))'
        ]
        for pat in institution_patterns:
            matches = re.finditer(pat, text)
            for m in matches:
                inst = m.group(0).strip()
                if 8 < len(inst) < 80 and inst not in found_degrees:
                    found_degrees.append(inst)

        return found_degrees[:4]  # Return top relevant education matches

    def extract_skills(self, text: str) -> List[str]:
        """
        Extract software engineering technical skills from resume text.
        Returns a sorted list of unique canonical skill strings.
        """
        doc = self.nlp(text.lower())
        matches = self.matcher(doc)

        found_skills = set()
        for match_id, start, end in matches:
            span_text = doc[start:end].text.strip().lower()
            canonical = self.alias_to_canonical.get(span_text, self.nlp.vocab.strings[match_id])
            found_skills.add(canonical)

        # Regex fallback for skills with symbols that might be tokenized atypically (C++, C#, .NET)
        special_symbols = {
            r'\bc\+\+\b': 'c++',
            r'\bc#\b': 'c#',
            r'\b\.net\b': 'c#',
            r'\bci\/cd\b': 'ci/cd',
            r'\brestful\b': 'rest api',
            r'\bnode\.?js\b': 'node.js',
            r'\breact\.?js\b': 'react',
            r'\bvue\.?js\b': 'vue.js',
            r'\bnext\.?js\b': 'next.js'
        }
        for regex_pat, canon in special_symbols.items():
            if re.search(regex_pat, text, re.IGNORECASE):
                found_skills.add(canon)

        return sorted(list(found_skills))

    def validate_resume_text(self, text: str) -> tuple[bool, str]:
        """
        Confirm that extracted PDF text has enough resume-specific structure to
        be evaluated. This intentionally uses several independent signals so a
        generic document containing one keyword is not accepted as a resume.
        """
        normalized_text = re.sub(r"\s+", " ", text).strip().lower()
        if len(normalized_text) < 80:
            return False, "The PDF does not contain enough text to be a resume."

        section_matches = {
            keyword
            for keyword in self.RESUME_SECTION_KEYWORDS
            if re.search(rf"\b{re.escape(keyword)}\b", normalized_text)
        }
        section_matches.discard("resume")
        section_matches.discard("curriculum vitae")

        has_contact_signal = bool(
            self.extract_email(text)
            or self.extract_phone(text)
            or self.extract_links(text)["linkedin"]
            or self.extract_links(text)["github"]
        )
        has_resume_content = bool(
            self.extract_skills(text)
            or self.extract_education(text)
            or re.search(
                r"\b(?:developer|engineer|analyst|manager|designer|intern|"
                r"experience)\b",
                normalized_text,
            )
        )

        if len(section_matches) < 2 or not has_resume_content:
            return False, (
                "This PDF does not appear to be a resume. "
                "Upload a document containing resume sections such as "
                "Experience, Education, Skills, or Projects."
            )

        if not has_contact_signal and len(section_matches) < 3:
            return False, (
                "This PDF does not contain enough candidate profile information "
                "to be evaluated as a resume."
            )

        return True, ""

    def parse(self, pdf_input: Union[str, io.BytesIO, bytes]) -> Dict[str, Any]:
        """
        High-level parse function returning all structured resume data.
        """
        raw_text = self.extract_text_from_pdf(pdf_input)
        name = self.extract_name(raw_text)
        email = self.extract_email(raw_text)
        phone = self.extract_phone(raw_text)
        links = self.extract_links(raw_text)
        education = self.extract_education(raw_text)
        skills = self.extract_skills(raw_text)

        return {
            "name": name,
            "email": email,
            "phone": phone,
            "links": links,
            "education": education,
            "skills": skills,
            "total_skills_found": len(skills),
            "raw_text": raw_text
        }
