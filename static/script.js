/**
 * script.js - Client-Side Controller for AI Resume Analyzer
 * Handles drag-and-drop, PDF file upload, asynchronous API requests,
 * dynamic radial gauge rendering, skill gap badge generation, and job switching.
 */

document.addEventListener("DOMContentLoaded", () => {
  // DOM Elements
  const dropZone = document.getElementById("drop-zone");
  const fileInput = document.getElementById("resume-file");
  const fileInfo = document.getElementById("file-info");
  const fileNameDisplay = document.getElementById("file-name");
  const fileSizeDisplay = document.getElementById("file-size");
  const removeFileBtn = document.getElementById("remove-file-btn");
  const uploadForm = document.getElementById("resume-upload-form");
  const analyzeBtn = document.getElementById("analyze-btn");
  const btnSpinner = document.getElementById("spinner");
  const btnText = document.getElementById("btn-text");
  const alertBanner = document.getElementById("alert-banner");
  const targetRoleSelect = document.getElementById("target-role-select");
  const customJobContainer = document.getElementById("custom-job-container");

  // Results DOM Elements
  const resultsSection = document.getElementById("results-section");
  const candidateAvatar = document.getElementById("candidate-avatar");
  const candidateName = document.getElementById("candidate-name");
  const skillsCountPill = document.getElementById("skills-count-pill");
  const contactEmail = document.getElementById("contact-email");
  const contactPhone = document.getElementById("contact-phone");
  const contactLinkedin = document.getElementById("contact-linkedin");
  const contactGithub = document.getElementById("contact-github");
  const educationList = document.getElementById("education-list");
  const candidateSkillsCloud = document.getElementById("candidate-skills-cloud");

  // Gauge & Gap Elements
  const targetRoleLabel = document.getElementById("target-role-label");
  const gaugeFillCircle = document.getElementById("gauge-fill-circle");
  const atsScoreNum = document.getElementById("ats-score-num");
  const atsRatingLabel = document.getElementById("ats-rating-label");
  const metricSkillCoverage = document.getElementById("metric-skill-coverage");
  const metricTfidf = document.getElementById("metric-tfidf");
  const coveragePill = document.getElementById("coverage-pill");
  const matchedCount = document.getElementById("matched-count");
  const missingCount = document.getElementById("missing-count");
  const matchedSkillsCloud = document.getElementById("matched-skills-cloud");
  const missingSkillsCloud = document.getElementById("missing-skills-cloud");
  const recommendationsList = document.getElementById("recommendations-list");
  const learningRoadmap = document.getElementById("learning-roadmap");
  const careerGuidanceList = document.getElementById("career-guidance-list");
  const learningFlowchart = document.getElementById("learning-flowchart");
  const downloadReportBtn = document.getElementById("download-report-btn");
  const jobsRecommendationsGrid = document.getElementById("jobs-recommendations-grid");
  const liveJobsCard = document.getElementById("live-jobs-card");
  const liveJobsGrid = document.getElementById("live-jobs-grid");
  const liveQueryInput = document.getElementById("live-query-input");
  const liveLocationInput = document.getElementById("live-location-input");
  const refreshLiveJobsBtn = document.getElementById("refresh-live-jobs-btn");
  const liveSpinner = document.getElementById("live-spinner");
  const liveBtnText = document.getElementById("live-btn-text");

  // State
  let currentFile = null;
  let cachedCandidate = null;
  let cachedResumeText = "";
  let activeAnalysis = null;

  // 1. Drag & Drop Handlers
  ["dragenter", "dragover"].forEach((eventName) => {
    dropZone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropZone.classList.add("drag-over");
    });
  });

  ["dragleave", "drop"].forEach((eventName) => {
    dropZone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropZone.classList.remove("drag-over");
    });
  });

  dropZone.addEventListener("drop", (e) => {
    const files = e.dataTransfer.files;
    if (files.length > 0) {
      handleFileSelection(files[0]);
    }
  });

  dropZone.addEventListener("click", (e) => {
    // Only open file dialog if click didn't come from remove button
    if (e.target !== removeFileBtn && !removeFileBtn.contains(e.target)) {
      fileInput.click();
    }
  });

  fileInput.addEventListener("change", (e) => {
    if (e.target.files.length > 0) {
      handleFileSelection(e.target.files[0]);
    }
  });

  removeFileBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    resetFileState();
  });

  function handleFileSelection(file) {
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      showAlert("Please select a valid PDF document (.pdf).", "danger");
      resetFileState();
      return;
    }

    if (file.size > 16 * 1024 * 1024) {
      showAlert("File size exceeds 16MB limit.", "danger");
      resetFileState();
      return;
    }

    hideAlert();
    currentFile = file;
    fileNameDisplay.textContent = file.name;
    fileSizeDisplay.textContent = `(${formatBytes(file.size)})`;
    fileInfo.classList.remove("hidden");
    analyzeBtn.disabled = false;
  }

  function resetFileState() {
    currentFile = null;
    fileInput.value = "";
    fileInfo.classList.add("hidden");
    analyzeBtn.disabled = true;
  }

  function formatBytes(bytes) {
    if (bytes === 0) return "0 Bytes";
    const k = 1024;
    const sizes = ["Bytes", "KB", "MB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
  }

  // 2. Custom Role Collapsible Toggle
  targetRoleSelect.addEventListener("change", (e) => {
    if (e.target.value === "custom") {
      customJobContainer.classList.remove("hidden");
    } else {
      customJobContainer.classList.add("hidden");
    }
  });

  // 3. Form Submission & Resume Analysis
  uploadForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!currentFile) return;

    setLoadingState(true);
    hideAlert();

    const formData = new FormData(uploadForm);
    formData.set("resume", currentFile);

    try {
      const response = await fetch("/api/upload", {
        method: "POST",
        body: formData,
      });

      const data = await response.json();

      if (!response.ok || !data.success) {
        throw new Error(data.error || "Failed to analyze resume.");
      }

      // Cache candidate state for dynamic role switching
      cachedCandidate = data.candidate;
      cachedResumeText = data.resume_text || data.resume_text_snippet || "";

      renderResults(data);
      resultsSection.classList.remove("hidden");
      resultsSection.scrollIntoView({ behavior: "smooth" });
    } catch (err) {
      showAlert(err.message, "danger");
    } finally {
      setLoadingState(false);
    }
  });

  function setLoadingState(loading) {
    if (loading) {
      analyzeBtn.disabled = true;
      btnSpinner.classList.remove("hidden");
      btnText.textContent = "Analyzing Resume & Skills...";
    } else {
      analyzeBtn.disabled = currentFile === null;
      btnSpinner.classList.add("hidden");
      btnText.textContent = "Analyze Resume & Detect Gaps";
    }
  }

  function showAlert(message, type) {
    alertBanner.textContent = message;
    alertBanner.className = `alert-banner alert-${type}`;
    alertBanner.classList.remove("hidden");
  }

  function hideAlert() {
    alertBanner.classList.add("hidden");
  }

  // 4. Results Rendering Engine
  function renderResults(data) {
    const cand = data.candidate;

    // Render Candidate Meta
    candidateName.textContent = cand.name || "Candidate Profile";
    candidateAvatar.textContent = getInitials(cand.name);
    skillsCountPill.textContent = `${cand.total_skills} Skills Detected`;

    // Email & Phone
    contactEmail.querySelector(".text").textContent = cand.email || "Email not specified";
    contactPhone.querySelector(".text").textContent = cand.phone || "Phone not specified";

    // Social Links
    if (cand.links && cand.links.linkedin) {
      contactLinkedin.classList.remove("hidden");
      contactLinkedin.querySelector("a").href = cand.links.linkedin;
    } else {
      contactLinkedin.classList.add("hidden");
    }

    if (cand.links && cand.links.github) {
      contactGithub.classList.remove("hidden");
      contactGithub.querySelector("a").href = cand.links.github;
    } else {
      contactGithub.classList.add("hidden");
    }

    // Education
    educationList.innerHTML = "";
    if (cand.education && cand.education.length > 0) {
      cand.education.forEach((edu) => {
        const li = document.createElement("li");
        li.textContent = edu;
        educationList.appendChild(li);
      });
    } else {
      educationList.innerHTML = "<li>No specific degree entries detected in resume text.</li>";
    }

    // Candidate Skills Cloud
    candidateSkillsCloud.innerHTML = "";
    if (cand.skills && cand.skills.length > 0) {
      cand.skills.forEach((skill) => {
        const pill = document.createElement("span");
        pill.className = "skill-pill";
        pill.textContent = skill.toUpperCase();
        candidateSkillsCloud.appendChild(pill);
      });
    } else {
      candidateSkillsCloud.innerHTML = "<span class='text-muted'>No recognized technical skills found.</span>";
    }

    // Render Target Analysis
    if (data.target_analysis) {
      renderTargetAnalysis(data.target_analysis);
    }

    // Render Top 5 Unique Job Recommendations
    if (data.recommendations) {
      renderJobRecommendations(data.recommendations);
    }

    // Prefill live job search input with target role or top skill
    if (liveQueryInput) {
      const defaultQuery = data.target_role || (cand.skills && cand.skills[0]) || "Software Engineer";
      if (!liveQueryInput.value) {
        liveQueryInput.value = defaultQuery;
      }
    }

    // Render Real-Time Live Job Vacancies (JSearch / Mock)
    if (data.live_recommendations && data.live_recommendations.length > 0) {
      renderLiveRecommendations(data.live_recommendations);
    } else if (cand.skills && cand.skills.length > 0) {
      const q = liveQueryInput ? liveQueryInput.value : (data.target_role || "Software Engineer");
      fetchLiveRecommendations(cand.skills, q, "Remote");
    }
  }


  function getInitials(name) {
    if (!name || name === "Candidate Name Not Found") return "CP";
    const parts = name.trim().split(" ");
    if (parts.length === 1) return parts[0].substring(0, 2).toUpperCase();
    return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
  }

  function escapeHtml(str) {
    if (!str) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  // Render Target Role Score & Skill Gap
  function renderTargetAnalysis(analysis) {
    activeAnalysis = analysis;
    const companyInfo = analysis.company ? ` @ ${analysis.company}` : '';
    const locInfo = analysis.location ? ` (${analysis.location})` : '';
    targetRoleLabel.textContent = `${analysis.job_title}${companyInfo}${locInfo}`;

    // Animate ATS Gauge
    const score = analysis.ats_score;
    atsScoreNum.textContent = score;
    atsRatingLabel.textContent = analysis.rating;
    const scoreBand = score < 40 ? "low" : score <= 70 ? "medium" : "high";
    const scoreColors = {
      low: { foreground: "#f87171", background: "rgba(239, 68, 68, 0.16)" },
      medium: { foreground: "#fcd34d", background: "rgba(245, 158, 11, 0.16)" },
      high: { foreground: "#6ee7b7", background: "rgba(16, 185, 129, 0.16)" }
    };
    atsRatingLabel.style.color = scoreColors[scoreBand].foreground;
    atsRatingLabel.style.background = scoreColors[scoreBand].background;

    // Radial circumference = 2 * PI * 65 ≈ 408.4
    const circumference = 408.4;
    const offset = circumference - (score / 100) * circumference;
    gaugeFillCircle.classList.remove("score-low", "score-medium", "score-high");
    gaugeFillCircle.classList.add(`score-${scoreBand}`);
    gaugeFillCircle.style.stroke = `url(#gauge-gradient-${scoreBand})`;
    gaugeFillCircle.style.strokeDashoffset = offset;

    // Metrics
    metricSkillCoverage.textContent = `${analysis.skill_coverage_pct}%`;
    metricTfidf.textContent = `${analysis.tfidf_similarity}%`;

    // Gap Header Pill
    coveragePill.textContent = `${analysis.matched_skills_count} of ${analysis.total_required_skills} Required Skills`;

    // Matched Skills Badges
    matchedCount.textContent = analysis.matched_skills.length;
    matchedSkillsCloud.innerHTML = "";
    if (analysis.matched_skills.length > 0) {
      analysis.matched_skills.forEach((skill) => {
        const pill = document.createElement("span");
        pill.className = "skill-pill skill-pill-matched";
        pill.innerHTML = `<svg class="skill-pill-icon" viewBox="0 0 24 24" aria-hidden="true"><polyline points="20 6 9 17 4 12"></polyline></svg><span>${skill.toUpperCase()}</span>`;
        matchedSkillsCloud.appendChild(pill);
      });
    } else {
      matchedSkillsCloud.innerHTML = "<span class='text-muted'>No required skills directly matched.</span>";
    }

    // Missing Skills Badges (Gap)
    missingCount.textContent = analysis.missing_skills.length;
    missingSkillsCloud.innerHTML = "";
    if (analysis.missing_skills.length > 0) {
      analysis.missing_skills.forEach((skill) => {
        const pill = document.createElement("span");
        pill.className = "skill-pill skill-pill-missing";
        pill.innerHTML = `<svg class="skill-pill-icon" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg><span>${skill.toUpperCase()}</span>`;
        missingSkillsCloud.appendChild(pill);
      });
    } else {
      missingSkillsCloud.innerHTML = "<span class='text-success'>★ Perfect match! All required skills present.</span>";
    }

    // Recommendations List
    recommendationsList.innerHTML = "";
    if (analysis.recommendations && analysis.recommendations.length > 0) {
      analysis.recommendations.forEach((rec) => {
        const li = document.createElement("li");
        li.textContent = rec;
        recommendationsList.appendChild(li);
      });
    }

    renderLearningRoadmap(analysis.learning_roadmap || []);
    renderCareerGuidance(analysis);
  }

  function renderLearningRoadmap(roadmap) {
    learningRoadmap.innerHTML = "";
    if (!roadmap.length) {
      learningRoadmap.innerHTML = "<p class='text-muted'>No learning gaps detected. Continue with advanced projects and role-specific practice.</p>";
      return;
    }

    roadmap.forEach((item) => {
      const skillPlan = document.createElement("article");
      skillPlan.className = "roadmap-skill";
      skillPlan.innerHTML = `<h5>${item.skill}</h5><div class="roadmap-steps"></div>`;
      const steps = skillPlan.querySelector(".roadmap-steps");
      item.steps.forEach((step) => {
        const stepEl = document.createElement("div");
        stepEl.className = "roadmap-step";
        stepEl.innerHTML = `
          <span class="roadmap-step-number">${step.step}</span>
          <div><strong>Step ${step.step}: ${step.title}</strong>
          <p>${step.description}</p><small>${step.timeframe}</small></div>
        `;
        steps.appendChild(stepEl);
      });
      learningRoadmap.appendChild(skillPlan);
    });
  }

  function renderCareerGuidance(analysis) {
    careerGuidanceList.innerHTML = "";
    (analysis.career_guidance || []).forEach((suggestion) => {
      const li = document.createElement("li");
      li.textContent = suggestion;
      careerGuidanceList.appendChild(li);
    });

    learningFlowchart.innerHTML = "";
    const stages = [
      { label: "Selected role", value: analysis.job_title || "Target role" },
      { label: "Assess gaps", value: `${analysis.missing_skills.length} skill(s)` },
      { label: "Build fundamentals", value: "1-2 weeks" },
      { label: "Ship projects", value: "2-3 weeks" },
      { label: "Show readiness", value: "Portfolio / certification" }
    ];
    stages.forEach((stage, index) => {
      const node = document.createElement("div");
      node.className = "flow-node";
      node.innerHTML = `<span>${stage.label}</span><strong>${stage.value}</strong>`;
      learningFlowchart.appendChild(node);
      if (index < stages.length - 1) {
        const arrow = document.createElement("span");
        arrow.className = "flow-arrow";
        arrow.textContent = "→";
        learningFlowchart.appendChild(arrow);
      }
    });
  }

  // Render Ranked Recommendations
  function renderJobRecommendations(roles) {
    jobsRecommendationsGrid.innerHTML = "";

    roles.forEach((role, idx) => {
      const card = document.createElement("div");
      card.className = "job-card";
      card.dataset.jobId = role.job_id;

      const searchUrl = role.search_url || `https://www.google.com/search?q=${encodeURIComponent((role.job_title || "Software Engineer") + " " + (role.company || "") + " apply").replace(/%20/g, "+")}`;

      card.innerHTML = `
        <div>
          <div class="job-card-top">
            <span class="job-card-rank">#${idx + 1} Best Fit</span>
            <span class="job-card-score" style="color: ${role.rating_color};">${role.ats_score}%</span>
          </div>
          <h4 class="job-card-title">${role.job_title}</h4>
          <span class="job-card-company">${role.company || 'Tech Enterprise'}</span>
          <div class="job-card-details">
            <span class="detail-chip"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 10c0 5-8 11-8 11S4 15 4 10a8 8 0 1 1 16 0Z"></path><circle cx="12" cy="10" r="2.5"></circle></svg>${role.location || 'Flexible'}</span>
            ${role.salary_lpa ? `<span class="detail-chip salary-tag"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7H14a3.5 3.5 0 0 1 0 7H6"></path></svg>${role.salary_lpa}</span>` : ''}
          </div>
          ${role.open_positions_count && role.open_positions_count > 1 ? `<div style="margin-top: 4px;"><span class="badge badge-accent" style="font-size: 0.72rem;">${role.open_positions_count} openings (${role.companies_summary})</span></div>` : ''}
        </div>

        <div>
          <div class="job-card-meta">
            <span>Skills Matched: <strong>${role.matched_skills_count}/${role.total_required_skills}</strong></span>
            <span>Gaps: <strong>${role.missing_skills.length}</strong></span>
          </div>
          <button type="button" class="btn-switch-role" data-job-id="${role.job_id}" style="margin-top: 10px;">
            Inspect Role & Skill Gap
          </button>

          <a class="btn btn-primary btn-sm mt-3" href="${escapeHtml(searchUrl)}" target="_blank" rel="noopener noreferrer">Search Active Posting</a>
        </div>
      `;

      // Handle Switch Role Button Click
      const switchBtn = card.querySelector(".btn-switch-role");
      switchBtn.addEventListener("click", () => {
        switchActiveRole(role.job_id);
      });
      card.addEventListener("click", (event) => {
        if (!event.target.closest("button") && !event.target.closest("input")) switchActiveRole(role.job_id);
      });

      jobsRecommendationsGrid.appendChild(card);
    });

    if (window.Alpine && typeof window.Alpine.initTree === "function") {
      window.Alpine.initTree(jobsRecommendationsGrid);
    }
  }


  // 5. Switch Active Target Role Dynamically
  async function switchActiveRole(jobId) {
    if (!cachedCandidate) return;

    try {
      const res = await fetch("/api/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          skills: cachedCandidate.skills,
          resume_text: cachedResumeText,
          target_role_id: jobId,
        }),
      });

      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(data.error || "Failed to switch role.");
      }

      renderTargetAnalysis(data.target_analysis);
      document.querySelectorAll(".job-card").forEach((card) => {
        card.classList.toggle("job-card-active", card.dataset.jobId === String(jobId));
      });
      // Smooth scroll to target analysis card
      document.querySelector(".analysis-grid").scrollIntoView({ behavior: "smooth" });
    } catch (err) {
      showAlert(err.message, "danger");
    }
  }

  downloadReportBtn.addEventListener("click", () => {
    if (!activeAnalysis || !window.jspdf) {
      showAlert("Analyze a resume before downloading a report.", "danger");
      return;
    }

    const { jsPDF } = window.jspdf;
    const doc = new jsPDF();
    const margin = 16;
    const pageWidth = doc.internal.pageSize.getWidth();
    let y = 18;
    const addWrapped = (text, size = 10, gap = 6) => {
      doc.setFontSize(size);
      const lines = doc.splitTextToSize(String(text), pageWidth - margin * 2);
      if (y + lines.length * 5 + gap > 280) {
        doc.addPage();
        y = 18;
      }
      doc.text(lines, margin, y);
      y += lines.length * 5 + gap;
    };

    addWrapped("AI Career Guidance & Analysis", 18, 9);
    addWrapped(`${activeAnalysis.job_title} at ${activeAnalysis.company || "Target company"}`);
    addWrapped(`ATS score: ${activeAnalysis.ats_score}/100 | Skill coverage: ${activeAnalysis.skill_coverage_pct}% | Contextual TF-IDF: ${activeAnalysis.tfidf_similarity}%`);
    addWrapped(`Matched skills: ${activeAnalysis.matched_skills.join(", ") || "None"}`);
    addWrapped(`Skill gaps: ${activeAnalysis.missing_skills.join(", ") || "None"}`);
    addWrapped("Improvement suggestions", 13, 5);
    (activeAnalysis.career_guidance || []).forEach((item) => addWrapped(`• ${item}`));
    addWrapped("Learning roadmap", 13, 5);
    (activeAnalysis.learning_roadmap || []).forEach((plan) => {
      addWrapped(plan.skill, 11, 3);
      plan.steps.forEach((step) => addWrapped(`Step ${step.step}: ${step.title} (${step.timeframe}) - ${step.description}`, 9, 3));
    });
    addWrapped("Flow: Selected role → Assess gaps → Build fundamentals → Ship projects → Show readiness", 10);
    doc.save(`${(activeAnalysis.job_title || "career-analysis").replace(/[^a-z0-9]+/gi, "-").toLowerCase()}-report.pdf`);
  });

  // 6. Real-Time Live Job Recommendations
  function renderLiveRecommendations(jobs) {
    if (!liveJobsGrid) return;
    liveJobsGrid.innerHTML = "";

    if (!jobs || jobs.length === 0) {
      liveJobsGrid.innerHTML = `
        <div class="live-jobs-empty">
          <p>No active live postings found matching current criteria. Try adjusting the search query or location.</p>
        </div>
      `;
      return;
    }

    jobs.forEach((job) => {
      const card = document.createElement("div");
      card.className = "live-job-card";

      const publisherName = job.job_publisher || "Live";
      const pubLower = publisherName.toLowerCase();
      let publisherClass = "publisher-linkedin";
      if (pubLower.includes("indeed")) publisherClass = "publisher-indeed";
      else if (pubLower.includes("glassdoor")) publisherClass = "publisher-glassdoor";

      const logoHtml = job.employer_logo
        ? `<img src="${job.employer_logo}" alt="${job.employer_name}" class="live-employer-logo" onerror="this.onerror=null; this.parentNode.innerHTML='<div class=\\'live-employer-fallback\\'>${getInitials(job.employer_name)}</div>';">`
        : `<div class="live-employer-fallback">${getInitials(job.employer_name)}</div>`;

      const matchedChips = (job.matched_skills || []).slice(0, 6).map((s) => 
        `<span class="live-skill-matched">&#10003; ${s}</span>`
      ).join("");

      const missingChips = (job.missing_skills || []).slice(0, 4).map((s) => 
        `<span class="live-skill-missing">&times; ${s}</span>`
      ).join("");

      const searchUrl = job.search_url || `https://www.google.com/search?q=${encodeURIComponent((job.job_title || "Software Engineer") + " " + (job.employer_name || "") + " apply").replace(/%20/g, "+")}`;

      card.innerHTML = `
        <div>
          <div class="live-job-top">
            <div class="live-employer-meta">
              ${logoHtml}
              <div>
                <span class="live-job-company">${job.employer_name || "Company"}</span>
                <h4 class="live-job-title">${job.job_title}</h4>
              </div>
            </div>
            <div class="live-match-badge">
              <span class="live-match-score" style="color: ${job.rating_color};">${job.match_score}%</span>
              <span class="live-match-rating">${job.rating}</span>
            </div>
          </div>

          <div class="live-job-meta-row">
            <span class="publisher-tag ${publisherClass}">${publisherName}</span>
            <span class="live-chip"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 10c0 5-8 11-8 11S4 15 4 10a8 8 0 1 1 16 0Z"></path><circle cx="12" cy="10" r="2.5"></circle></svg>${job.location}</span>
            ${job.is_remote ? `<span class="live-chip live-chip-remote">&#9679; Remote</span>` : ""}
            ${job.salary && job.salary !== "Salary Not Disclosed" ? `<span class="live-chip live-chip-salary">${job.salary}</span>` : ""}
          </div>

          <div class="live-job-skills">
            <div class="live-skills-title">Matched Skills (${job.matched_skills_count || 0}):</div>
            <div class="live-skills-cloud">
              ${matchedChips || `<span class="text-muted" style="font-size: 0.72rem;">None identified</span>`}
            </div>
            ${missingChips ? `
              <div class="live-skills-title" style="margin-top: 6px;">Missing Skill Gaps:</div>
              <div class="live-skills-cloud">${missingChips}</div>
            ` : ""}
          </div>

          <p class="live-job-desc">${job.description_snippet || ""}</p>
          <a class="btn btn-primary btn-sm live-job-actions" href="${escapeHtml(searchUrl)}" target="_blank" rel="noopener noreferrer">Search Active Posting</a>
        </div>
      `;

      liveJobsGrid.appendChild(card);
    });

    if (window.Alpine && typeof window.Alpine.initTree === "function") {
      window.Alpine.initTree(liveJobsGrid);
    }
  }


  // Fetch live recommendations via /api/live-recommendations
  async function fetchLiveRecommendations(skills, query, location = "Remote") {
    if (!liveJobsGrid) return;
    if (liveSpinner) liveSpinner.classList.remove("hidden");
    if (liveBtnText) liveBtnText.textContent = "Searching...";

    try {
      const res = await fetch("/api/live-recommendations", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          skills: skills || [],
          query: query || "",
          location: location || "Remote",
          resume_text: cachedResumeText || ""
        }),
      });

      const data = await res.json();
      if (data.success && data.jobs) {
        renderLiveRecommendations(data.jobs);
      } else {
        showAlert(data.error || "Failed to load live recommendations.", "warning");
      }
    } catch (err) {
      console.error("Live recommendations fetch error:", err);
    } finally {
      if (liveSpinner) liveSpinner.classList.add("hidden");
      if (liveBtnText) liveBtnText.textContent = "Search Live Openings";
    }
  }

  // Live Openings Search Button Handler
  if (refreshLiveJobsBtn) {
    refreshLiveJobsBtn.addEventListener("click", () => {
      const query = liveQueryInput ? liveQueryInput.value.trim() : "";
      const location = liveLocationInput ? liveLocationInput.value.trim() : "Remote";
      const skills = cachedCandidate ? cachedCandidate.skills : [];
      fetchLiveRecommendations(skills, query, location);
    });
  }

  if (liveQueryInput) {
    liveQueryInput.addEventListener("keypress", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        refreshLiveJobsBtn.click();
      }
    });
  }
});
