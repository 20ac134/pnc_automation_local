import React, { useState, useEffect, useRef } from "react";
import SelectField from "./components/SelectField";
import ProgressBar from "./components/ProgressBar";
import SuccessScreen from "./components/SuccessScreen";
import { Country, University, JobPosting, API_BASE } from "./data";
import "./App.css";

// ── Types ────────────────────────────────────────────────────────────
type LoadState = "idle" | "loading" | "error";
type AppState = "form" | "running" | "completed" | "failed";
type AppMode = "single" | "batch";

interface Submission {
  country: string;
  university: string;
  job: string;
  department: string;
  jobType: string;
}

interface BatchQueueItem {
  portal_key: string;
  job_id: string;
  countryName: string;
  universityName: string;
  jobTitle: string;
}

interface BatchJobStatus {
  run_id: string;
  portal: string;
  job_id: string;
  job_title: string;
  status: "pending" | "running" | "completed" | "failed";
  message: string;
}

interface BatchStatusResponse {
  batch_id: string;
  status: string;
  total: number;
  completed: number;
  failed: number;
  current_index: number;
  jobs: BatchJobStatus[];
}

// ── Loading steps ────────────────────────────────────────────────────
const LOADING_STEPS = [
  "Launching browser…",
  "Navigating to portal…",
  "Logging in…",
  "Filling job form…",
  "Submitting application…",
];

const App: React.FC = () => {
  // ── Data ─────────────────────────────────────────────────────────────
  const [countries, setCountries] = useState<Country[]>([]);
  const [universities, setUniversities] = useState<University[]>([]);
  const [jobPostings, setJobPostings] = useState<JobPosting[]>([]);

  // ── Selections ────────────────────────────────────────────────────────
  const [selectedCountry, setSelectedCountry] = useState("");
  const [selectedUniversity, setSelectedUniversity] = useState("");
  const [selectedJob, setSelectedJob] = useState("");

  // ── Load states ───────────────────────────────────────────────────────
  const [countriesState, setCountriesState] = useState<LoadState>("loading");
  const [universitiesState, setUniversitiesState] = useState<LoadState>("idle");
  const [jobsState, setJobsState] = useState<LoadState>("idle");

  // ── App state machine ─────────────────────────────────────────────────
  const [appMode, setAppMode] = useState<AppMode>("single");
  const [appState, setAppState] = useState<AppState>("form");
  const [runId, setRunId] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState<Submission | null>(null);
  const [errorMessage, setErrorMessage] = useState("");
  const [loadingStep, setLoadingStep] = useState(0);

  // ── Batch state ───────────────────────────────────────────────────────
  const [batchQueue, setBatchQueue] = useState<BatchQueueItem[]>([]);
  const [batchId, setBatchId] = useState<string | null>(null);
  const [batchStatus, setBatchStatus] = useState<BatchStatusResponse | null>(
    null
  );
  const [activeRunId, setActiveRunId] = useState<string | null>(null);

  // ── Polling refs ──────────────────────────────────────────────────────
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const stepRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const clearIntervals = () => {
    if (pollRef.current) clearInterval(pollRef.current);
    if (stepRef.current) clearInterval(stepRef.current);
  };

  // ── Fetch countries on mount ──────────────────────────────────────────
  useEffect(() => {
    setCountriesState("loading");
    fetch(`${API_BASE}/countries`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((data: Country[]) => {
        setCountries(data);
        setCountriesState("idle");
      })
      .catch(() => setCountriesState("error"));
  }, []);

  // ── Fetch universities when country changes ───────────────────────────
  useEffect(() => {
    if (!selectedCountry) {
      setUniversities([]);
      return;
    }
    setUniversitiesState("loading");
    setUniversities([]);
    fetch(`${API_BASE}/universities?country=${selectedCountry}`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((data: University[]) => {
        setUniversities(data);
        setUniversitiesState("idle");
      })
      .catch(() => setUniversitiesState("error"));
  }, [selectedCountry]);

  // ── Fetch jobs when university changes ────────────────────────────────
  useEffect(() => {
    if (!selectedUniversity) {
      setJobPostings([]);
      return;
    }
    setJobsState("loading");
    setJobPostings([]);
    fetch(`${API_BASE}/jobs?portal=${selectedUniversity}`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((data: JobPosting[]) => {
        setJobPostings(data);
        setJobsState("idle");
      })
      .catch(() => setJobsState("error"));
  }, [selectedUniversity]);

  // ── Single mode polling ───────────────────────────────────────────────
  useEffect(() => {
    if (appState !== "running" || !runId || appMode !== "single") return;

    stepRef.current = setInterval(() => {
      setLoadingStep((prev) => (prev + 1) % LOADING_STEPS.length);
    }, 4000);

    pollRef.current = setInterval(async () => {
      try {
        const res = await fetch(`${API_BASE}/status/${runId}`);
        const data = await res.json();
        if (data.status === "completed") {
          clearIntervals();
          setAppState("completed");
        } else if (data.status === "failed") {
          clearIntervals();
          setErrorMessage(data.message || "Playbook failed");
          setAppState("failed");
        }
      } catch {
        /* network blip — keep polling */
      }
    }, 3000);

    return () => clearIntervals();
  }, [appState, runId, appMode]);

  // ── Batch mode polling ────────────────────────────────────────────────
  useEffect(() => {
    if (appState !== "running" || !batchId || appMode !== "batch") return;

    stepRef.current = setInterval(() => {
      setLoadingStep((prev) => (prev + 1) % LOADING_STEPS.length);
    }, 4000);

    pollRef.current = setInterval(async () => {
      try {
        const res = await fetch(`${API_BASE}/batch/status/${batchId}`);
        const data: BatchStatusResponse = await res.json();
        setBatchStatus(data);

        // Find the currently running job that needs a confirm
        const runningJob = data.jobs.find((j) => j.status === "running");
        if (runningJob) setActiveRunId(runningJob.run_id);

        if (data.status === "completed") {
          clearIntervals();
          setAppState("completed");
        }
      } catch {
        /* network blip — keep polling */
      }
    }, 3000);

    return () => clearIntervals();
  }, [appState, batchId, appMode]);

  // ── Derived ───────────────────────────────────────────────────────────
  const currentStep = selectedCountry
    ? selectedUniversity
      ? selectedJob
        ? 3
        : 2
      : 1
    : 0;
  const canSubmit = !!(selectedCountry && selectedUniversity && selectedJob);

  // ── Handlers ──────────────────────────────────────────────────────────
  const handleCountryChange = (val: string) => {
    setSelectedCountry(val);
    setSelectedUniversity("");
    setSelectedJob("");
    setUniversities([]);
    setJobPostings([]);
    setUniversitiesState("idle");
    setJobsState("idle");
  };

  const handleUniversityChange = (val: string) => {
    setSelectedUniversity(val);
    setSelectedJob("");
    setJobPostings([]);
    setJobsState("idle");
  };

  const handleModeSwitch = (mode: AppMode) => {
    setAppMode(mode);
    // don't reset selections — user may want to keep them
  };

  // ── Single submit ─────────────────────────────────────────────────────
  const handleSubmit = async () => {
    if (!canSubmit) return;

    const countryObj = countries.find((c) => c.code === selectedCountry);
    const universityObj = universities.find((u) => u.id === selectedUniversity);
    const jobObj = jobPostings.find((j) => j.id === selectedJob);
    const submittedAt = new Date().toISOString();
    const submission = {
      country: countryObj?.name ?? selectedCountry,
      university: universityObj?.name ?? selectedUniversity,
      job: jobObj?.title ?? selectedJob,
      department: jobObj?.department ?? "",
      jobType: jobObj?.type ?? "",
    };

    setSubmitted(submission);

    setLoadingStep(0);
    setAppState("running");
    setErrorMessage("");

    try {
      const res = await fetch(`${API_BASE}/submit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          portal_key: selectedUniversity,
          job_id: selectedJob,
          country: submission.country,
          university_name: submission.university,
          job_title: submission.job,
          submitted_at: submittedAt,
        }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail ?? `HTTP ${res.status}`);
      }
      const data = await res.json();
      setRunId(data.run_id);
    } catch (err: unknown) {
      clearIntervals();
      setErrorMessage(err instanceof Error ? err.message : "Submission failed");
      setAppState("failed");
    }
  };

  // ── Single confirm ────────────────────────────────────────────────────
  const handleConfirm = async () => {
    if (!runId) return;
    try {
      const res = await fetch(`${API_BASE}/confirm/${runId}`, {
        method: "POST",
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      clearIntervals();
      setAppState("completed");
    } catch (err: unknown) {
      setErrorMessage(
        err instanceof Error ? err.message : "Confirmation failed"
      );
      setAppState("failed");
    }
  };

  // ── Batch: add current selection to queue ─────────────────────────────
  const handleAddToBatch = () => {
    if (!canSubmit) return;
    const countryObj = countries.find((c) => c.code === selectedCountry);
    const universityObj = universities.find((u) => u.id === selectedUniversity);
    const jobObj = jobPostings.find((j) => j.id === selectedJob);

    // Prevent duplicates
    const isDupe = batchQueue.some(
      (q) => q.portal_key === selectedUniversity && q.job_id === selectedJob
    );
    if (isDupe) return;

    setBatchQueue((prev) => [
      ...prev,
      {
        portal_key: selectedUniversity,
        job_id: selectedJob,
        countryName: countryObj?.name ?? selectedCountry,
        universityName: universityObj?.name ?? selectedUniversity,
        jobTitle: jobObj?.title ?? selectedJob,
      },
    ]);

    // Reset job selection so user can pick the next one
    setSelectedJob("");
  };

  const handleRemoveFromBatch = (index: number) => {
    setBatchQueue((prev) => prev.filter((_, i) => i !== index));
  };

  // ── Batch: run all queued jobs ────────────────────────────────────────
  const handleRunBatch = async () => {
    if (batchQueue.length === 0) return;

    const submittedAt = new Date().toISOString();

    setLoadingStep(0);
    setAppState("running");
    setErrorMessage("");
    setBatchStatus(null);
    setActiveRunId(null);

    try {
      const res = await fetch(`${API_BASE}/submit/batch`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          jobs: batchQueue.map((q) => ({
            portal_key: q.portal_key,
            job_id: q.job_id,
            country: q.countryName,
            university_name: q.universityName,
            job_title: q.jobTitle,
            submitted_at: submittedAt,
          })),
        }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail ?? `HTTP ${res.status}`);
      }
      const data = await res.json();
      setBatchId(data.batch_id);

      // Seed batchStatus from the initial response so the UI shows jobs immediately
      setBatchStatus({
        batch_id: data.batch_id,
        status: "running",
        total: data.total,
        completed: 0,
        failed: 0,
        current_index: 0,
        jobs: data.jobs.map(
          (j: {
            run_id: string;
            portal_key: string;
            job_id: string;
            job_title: string;
          }) => ({
            run_id: j.run_id,
            portal: j.portal_key,
            job_id: j.job_id,
            job_title: j.job_title,
            status: "pending" as const,
            message: "Waiting to start…",
          })
        ),
      });
    } catch (err: unknown) {
      clearIntervals();
      setErrorMessage(
        err instanceof Error ? err.message : "Batch submission failed"
      );
      setAppState("failed");
    }
  };

  // ── Batch confirm: confirm the currently running job ──────────────────
  const handleBatchConfirm = async () => {
    if (!activeRunId) return;
    try {
      const res = await fetch(`${API_BASE}/confirm/${activeRunId}`, {
        method: "POST",
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setActiveRunId(null);
      // Polling will pick up the next running job automatically
    } catch (err: unknown) {
      setErrorMessage(
        err instanceof Error ? err.message : "Confirmation failed"
      );
    }
  };

  // ── Reset everything ──────────────────────────────────────────────────
  const handleReset = () => {
    clearIntervals();
    setSelectedCountry("");
    setSelectedUniversity("");
    setSelectedJob("");
    setUniversities([]);
    setJobPostings([]);
    setUniversitiesState("idle");
    setJobsState("idle");
    setAppState("form");
    setRunId(null);
    setSubmitted(null);
    setErrorMessage("");
    setLoadingStep(0);
    setBatchQueue([]);
    setBatchId(null);
    setBatchStatus(null);
    setActiveRunId(null);
  };

  // ── Helper texts ──────────────────────────────────────────────────────
  const uniHelperText = () => {
    if (universitiesState === "loading") return "Loading universities…";
    if (universitiesState === "error") return "Failed to load universities";
    if (selectedCountry)
      return `${universities.length} universities with open positions`;
    return "";
  };

  const jobHelperText = () => {
    if (jobsState === "loading") return "Loading positions…";
    if (jobsState === "error") return "Failed to load positions";
    if (selectedUniversity)
      return `${jobPostings.length} queued position${
        jobPostings.length !== 1 ? "s" : ""
      }`;
    return "";
  };

  // ── Status pill helper ────────────────────────────────────────────────
  const statusPill = (status: BatchJobStatus["status"]) => {
    const map: Record<string, string> = {
      pending: "pill--pending",
      running: "pill--running",
      completed: "pill--completed",
      failed: "pill--failed",
    };
    const labels: Record<string, string> = {
      pending: "Pending",
      running: "Running",
      completed: "Done",
      failed: "Failed",
    };
    return (
      <span className={`status-pill ${map[status]}`}>{labels[status]}</span>
    );
  };

  // ── Render ────────────────────────────────────────────────────────────
  return (
    <div className="page">
      <main className="card">
        {/* ── LOADING SCREEN — single ── */}
        {appState === "running" && appMode === "single" && submitted && (
          <div className="loading-screen">
            <div className="loading-spinner-ring" aria-hidden="true">
              <div />
              <div />
              <div />
              <div />
            </div>
            <h2 className="loading-title">Running playbook</h2>
            <p className="loading-subtitle">
              Submitting <strong>{submitted.job}</strong> to{" "}
              <strong>{submitted.university}</strong>
            </p>
            <div className="loading-step-pill">
              <span className="loading-step-dot" />
              {LOADING_STEPS[loadingStep]}
            </div>
            <p className="loading-note">
              This may take a few minutes. Please keep this window open.
            </p>
            {runId && (
              <div className="confirm-section">
                <div className="confirm-divider" />
                <p className="confirm-hint">
                  Once you've reviewed the form in the browser and it shows
                  <br />
                  <strong>"FORM FILLED BUT NOT SUBMITTED"</strong> — click
                  below.
                </p>
                <button className="btn-confirm" onClick={handleConfirm}>
                  ✓ Mark as complete
                </button>
              </div>
            )}
          </div>
        )}

        {/* ── LOADING SCREEN — batch ── */}
        {appState === "running" && appMode === "batch" && (
          <div className="loading-screen">
            <div className="loading-spinner-ring" aria-hidden="true">
              <div />
              <div />
              <div />
              <div />
            </div>
            <h2 className="loading-title">Running batch</h2>

            {/* Overall progress */}
            {batchStatus && (
              <div className="batch-progress-bar-wrap">
                <div
                  className="batch-progress-bar-fill"
                  style={{
                    width: `${Math.round(
                      ((batchStatus.completed + batchStatus.failed) /
                        batchStatus.total) *
                        100
                    )}%`,
                  }}
                />
              </div>
            )}
            {batchStatus && (
              <p className="loading-subtitle" style={{ marginBottom: "1rem" }}>
                {batchStatus.completed + batchStatus.failed} of{" "}
                {batchStatus.total} jobs finished
                {batchStatus.failed > 0 && (
                  <span className="batch-failed-count">
                    {" "}
                    · {batchStatus.failed} failed
                  </span>
                )}
              </p>
            )}

            <div className="loading-step-pill">
              <span className="loading-step-dot" />
              {LOADING_STEPS[loadingStep]}
            </div>

            {/* Per-job status list */}
            {batchStatus && (
              <div className="batch-job-list">
                {batchStatus.jobs.map((job) => (
                  <div
                    key={job.run_id}
                    className={`batch-job-row ${
                      job.status === "running" ? "batch-job-row--active" : ""
                    }`}
                  >
                    <div className="batch-job-info">
                      <span className="batch-job-title">{job.job_title}</span>
                      <span className="batch-job-portal">{job.portal}</span>
                    </div>
                    {statusPill(job.status)}
                  </div>
                ))}
              </div>
            )}

            {/* Confirm button for the currently running job */}
            {activeRunId && (
              <div className="confirm-section">
                <div className="confirm-divider" />
                <p className="confirm-hint">
                  Review the filled form in the browser, then confirm to proceed
                  to the next job.
                  <br />
                  <strong>"FORM FILLED BUT NOT SUBMITTED"</strong>
                </p>
                <button className="btn-confirm" onClick={handleBatchConfirm}>
                  ✓ Confirm & continue
                </button>
              </div>
            )}
          </div>
        )}

        {/* ── FAILED SCREEN ── */}
        {appState === "failed" && (
          <div className="failed-screen">
            <div className="failed-icon" aria-hidden="true">
              <svg width="32" height="32" viewBox="0 0 32 32" fill="none">
                <circle
                  cx="16"
                  cy="16"
                  r="15"
                  stroke="currentColor"
                  strokeWidth="1.5"
                />
                <path
                  d="M11 11l10 10M21 11l-10 10"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                />
              </svg>
            </div>
            <h2 className="failed-title">Playbook failed</h2>
            <p className="failed-message">{errorMessage}</p>
            <button className="btn-reset" onClick={handleReset}>
              Try again
            </button>
          </div>
        )}

        {/* ── SUCCESS SCREEN — single ── */}
        {appState === "completed" && appMode === "single" && submitted && (
          <SuccessScreen
            country={submitted.country}
            university={submitted.university}
            job={submitted.job}
            department={submitted.department}
            jobType={submitted.jobType}
            onReset={handleReset}
          />
        )}

        {/* ── SUCCESS SCREEN — batch ── */}
        {appState === "completed" && appMode === "batch" && batchStatus && (
          <div className="success-screen">
            <div className="success-icon" aria-hidden="true">
              <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
                <circle
                  cx="20"
                  cy="20"
                  r="19"
                  stroke="currentColor"
                  strokeWidth="1.5"
                />
                <path
                  d="M12 20l6 6 10-12"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </div>
            <h2 className="success-title">Batch complete</h2>
            <p className="success-subtitle">
              {batchStatus.completed} of {batchStatus.total} jobs submitted
              successfully
              {batchStatus.failed > 0 && ` · ${batchStatus.failed} failed`}
            </p>
            <div className="batch-job-list batch-job-list--summary">
              {batchStatus.jobs.map((job) => (
                <div key={job.run_id} className="batch-job-row">
                  <div className="batch-job-info">
                    <span className="batch-job-title">{job.job_title}</span>
                    <span className="batch-job-portal">{job.portal}</span>
                  </div>
                  {statusPill(job.status)}
                </div>
              ))}
            </div>
            <button className="btn-reset" onClick={handleReset}>
              Submit more
            </button>
          </div>
        )}

        {/* ── FORM ── */}
        {appState === "form" && (
          <>
            <header className="card__header">
              <span className="badge">Application Portal</span>
              <h1>Find your opportunity</h1>
              <p>
                Select a country, university, and a queued job posting to
                trigger the playbook.
              </p>
            </header>

            {/* Mode toggle */}
            <div className="mode-toggle">
              <button
                className={`mode-btn ${
                  appMode === "single" ? "mode-btn--active" : ""
                }`}
                onClick={() => handleModeSwitch("single")}
              >
                Single
              </button>
              <button
                className={`mode-btn ${
                  appMode === "batch" ? "mode-btn--active" : ""
                }`}
                onClick={() => handleModeSwitch("batch")}
              >
                Batch
                {batchQueue.length > 0 && (
                  <span className="mode-badge">{batchQueue.length}</span>
                )}
              </button>
            </div>

            <ProgressBar totalSteps={3} currentStep={currentStep} />

            <div className="form-body">
              <SelectField
                stepNumber={1}
                label="Country"
                value={selectedCountry}
                onChange={handleCountryChange}
                options={countries.map((c) => ({
                  value: c.code,
                  label: c.name,
                }))}
                placeholder={
                  countriesState === "loading"
                    ? "Loading countries…"
                    : countriesState === "error"
                    ? "Failed to load countries"
                    : "Select a country…"
                }
                disabled={countriesState === "loading"}
                isDone={!!selectedCountry}
              />

              <SelectField
                stepNumber={2}
                label="University"
                value={selectedUniversity}
                onChange={handleUniversityChange}
                options={universities.map((u) => ({
                  value: u.id,
                  label: u.name,
                }))}
                placeholder={
                  !selectedCountry
                    ? "Select a country first…"
                    : universitiesState === "loading"
                    ? "Loading universities…"
                    : "Select a university…"
                }
                disabled={!selectedCountry || universitiesState === "loading"}
                helperText={uniHelperText()}
                isDone={!!selectedUniversity}
              />

              <div className="divider" />

              <SelectField
                stepNumber={3}
                label="Job posting"
                value={selectedJob}
                onChange={setSelectedJob}
                options={jobPostings.map((j) => ({
                  value: j.id,
                  label: `${j.title} — ${j.id}`,
                }))}
                placeholder={
                  !selectedUniversity
                    ? "Select a university first…"
                    : jobsState === "loading"
                    ? "Loading positions…"
                    : jobPostings.length === 0
                    ? "No queued positions available"
                    : "Select a job posting…"
                }
                disabled={
                  !selectedUniversity ||
                  jobsState === "loading" ||
                  jobPostings.length === 0
                }
                helperText={jobHelperText()}
                isDone={!!selectedJob}
              />
            </div>

            {/* ── Batch queue list ── */}
            {appMode === "batch" && batchQueue.length > 0 && (
              <div className="batch-queue">
                <p className="batch-queue-label">Queued jobs</p>
                {batchQueue.map((item, i) => (
                  <div
                    key={`${item.portal_key}-${item.job_id}`}
                    className="batch-queue-row"
                  >
                    <div className="batch-queue-info">
                      <span className="batch-queue-num">{i + 1}</span>
                      <div className="batch-queue-text">
                        <span className="batch-job-title">{item.jobTitle}</span>
                        <span className="batch-job-portal">
                          {item.universityName}
                        </span>
                      </div>
                    </div>
                    <button
                      className="batch-queue-remove"
                      onClick={() => handleRemoveFromBatch(i)}
                      aria-label="Remove"
                    >
                      ✕
                    </button>
                  </div>
                ))}
              </div>
            )}

            <footer className="card__footer">
              {appMode === "single" ? (
                <>
                  <span
                    className={`submit-hint ${
                      canSubmit ? "submit-hint--ready" : ""
                    }`}
                  >
                    {canSubmit
                      ? "Ready to submit"
                      : "Complete all fields to continue"}
                  </span>
                  <button
                    className="btn-submit"
                    onClick={handleSubmit}
                    disabled={!canSubmit}
                    aria-disabled={!canSubmit}
                  >
                    Submit application
                    <svg
                      width="15"
                      height="15"
                      viewBox="0 0 16 16"
                      fill="none"
                      aria-hidden="true"
                    >
                      <path
                        d="M3 8h10M9 4l4 4-4 4"
                        stroke="currentColor"
                        strokeWidth="1.5"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                  </button>
                </>
              ) : (
                <>
                  <button
                    className="btn-add-batch"
                    onClick={handleAddToBatch}
                    disabled={!canSubmit}
                    aria-disabled={!canSubmit}
                  >
                    + Add to batch
                  </button>
                  <button
                    className="btn-submit"
                    onClick={handleRunBatch}
                    disabled={batchQueue.length === 0}
                    aria-disabled={batchQueue.length === 0}
                  >
                    Run {batchQueue.length > 0 ? `${batchQueue.length} ` : ""}
                    job{batchQueue.length !== 1 ? "s" : ""}
                    <svg
                      width="15"
                      height="15"
                      viewBox="0 0 16 16"
                      fill="none"
                      aria-hidden="true"
                    >
                      <path
                        d="M3 8h10M9 4l4 4-4 4"
                        stroke="currentColor"
                        strokeWidth="1.5"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                  </button>
                </>
              )}
            </footer>
          </>
        )}
      </main>
    </div>
  );
};

export default App;
