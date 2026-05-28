from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pandas as pd
from pathlib import Path
import sys
import uuid
import threading
from datetime import datetime
from platform_router import get_playbook_class
import os


# -- Add project root so src.* imports work
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.config import Config
from src.excel_manager import ExcelManager

app = FastAPI(title="Vosyn Portal API", version="1.0.0")


MAX_WORKERS = int(os.environ.get("PNC_MAX_WORKERS", "3")) # This vaalue has been set keeping in mind thet resources are limited on the pnc team, if we get the perimision to hoast it change the number to a reasonable one that can run on the server.
# -- CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -- File paths
EXCEL_PATH = Path(r"C:\Users\aritr\vosyn\vosyn-automation\data\job_queue.xlsx")
PORTAL_URLS_PATH = Path(r"C:\Users\aritr\vosyn\vosyn-automation\data\portal_urls.xlsx")

# -- In-memory job status store
JOB_STORE: dict[str, dict] = {}
JOB_STORE_LOCK = threading.Lock()

# -- Country code mapping
COUNTRY_CODE_MAP: dict[str, str] = {
    "Canada": "ca",
    "USA": "us",
    "United Kingdom": "uk",
    "UK": "uk",
}

COUNTRY_NAMES: dict[str, str] = {
    "ca": "Canada",
    "us": "United States",
    "uk": "United Kingdom",
}


def read_excel(sheet: str) -> pd.DataFrame:
    return pd.read_excel(EXCEL_PATH, sheet_name=sheet)


def read_portal_urls() -> pd.DataFrame:
    """Read portal_urls.xlsx and return DataFrame with portal info."""
    return pd.read_excel(PORTAL_URLS_PATH, sheet_name="portal_urls")


def get_portal_display_names() -> dict[str, str]:
    """Build {portal_key: UniversityName} from portal_urls.xlsx."""
    df = read_portal_urls()
    return {
        str(row["PortalKey"]).strip().lower(): str(row["UniversityName"]).strip()
        for _, row in df.iterrows()
    }


def get_portal_countries() -> dict[str, str]:
    """Build {portal_key: country_code} from portal_urls.xlsx."""
    df = read_portal_urls()
    result = {}
    for _, row in df.iterrows():
        portal_key = str(row["PortalKey"]).strip().lower()
        country = str(row["Country"]).strip()
        country_code = COUNTRY_CODE_MAP.get(country, country.lower()[:2])
        result[portal_key] = country_code
    return result


# -- Models
class SubmitRequest(BaseModel):
    portal_key: str
    job_id: str


# -- Endpoints

@app.get("/")
def root():
    return {"status": "ok", "service": "Vosyn Portal API"}

@app.get("/api/countries")
def get_countries():
    """Return all countries that have portals configured."""
    try:
        portal_countries = get_portal_countries()
        seen = set()
        result = []
        for country_code in portal_countries.values():
            if country_code not in seen:
                seen.add(country_code)
                result.append({
                    "code": country_code,
                    "name": COUNTRY_NAMES.get(country_code, country_code.upper()),
                })
        result.sort(key=lambda x: x["name"])
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/universities")
def get_universities(country: str):
    """Return all universities for a given country."""
    try:
        portal_countries = get_portal_countries()
        display_names = get_portal_display_names()

        result = []
        for portal_key, portal_country in portal_countries.items():
            if portal_country != country.lower():
                continue
            result.append({
                "id": portal_key,
                "name": display_names.get(portal_key, portal_key.upper()),
                "countryCode": portal_country,
            })
        result.sort(key=lambda x: x["name"])
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/jobs")
def get_jobs():
    """Return all jobs from the JobPosts sheet."""
    try:
        df_jobs = read_excel("JobPosts")
        result = []
        for _, job in df_jobs.iterrows():
            result.append({
                "id":          str(job.get("JobId", "")),
                "title":       str(job.get("Title", "")),
                "department":  str(job.get("Department", "")),
                "type":        str(job.get("JobType", "Internship")),
                "location":    str(job.get("Location", "")),
                "salary":      str(job.get("Salary", "")),
                "hourlyRate":  str(job.get("HourlyRate", "")),
                "description": str(job.get("Description", ""))[:200],
            })
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/submit")
def submit_application(payload: SubmitRequest, background_tasks: BackgroundTasks):
    """Submit a job to a portal. Reads job data directly from JobPosts sheet."""
    try:
        em = ExcelManager()
        job = em.get_job(payload.job_id)
        if not job:
            raise HTTPException(status_code=404, detail=f"Job '{payload.job_id}' not found")

        portal_url = Config.get_portal_url(payload.portal_key)
        credentials = Config.get_credentials(payload.portal_key)
        PlaybookClass, platform = get_playbook_class(portal_url)

        if not PlaybookClass:
            raise HTTPException(status_code=422, detail=f"No playbook for platform '{platform}'")

        display_names = get_portal_display_names()

        job_data = {
            "JobId":        payload.job_id,
            "Title":        job["Title"],
            "Description":  job["Description"],
            "Location":     job.get("Location", ""),
            "City":         job.get("City", "Toronto"),
            "Salary":       job.get("Salary", ""),
            "HourlyRate":   job.get("HourlyRate", ""),
            "Duration":     "520 Hours (approximately 3 months)",
            "Requirements": job.get("Requirements", ""),
            "JobType":      job.get("JobType", "Internship"),
            "Industry":     job.get("Industry", "Technology"),
            "JobFunction":  job.get("JobFunction", ""),
            "StudentGroup": job.get("StudentGroup", "All Students"),
            "Department":   job.get("Department", ""),
            "portal_name":  payload.portal_key,
        }

        run_id = str(uuid.uuid4())
        with JOB_STORE_LOCK:
            JOB_STORE[run_id] = {
                "status":      "running",
                "portal":      display_names.get(payload.portal_key, payload.portal_key),
                "job_id":      payload.job_id,
                "job_title":   job["Title"],
                "platform":    platform,
                "message":     "Playbook is running...",
                "started_at":  datetime.now().isoformat(),
                "finished_at": None,
            }

        def run_playbook():
            try:
                playbook = PlaybookClass(
                    portal_url=portal_url,
                    credentials=credentials,
                    job_data=job_data,
                )
                result = playbook.execute()
                playbook.run_id = run_id
                p_status = result.get("status", "completed")
                with JOB_STORE_LOCK:
                    JOB_STORE[run_id]["status"]      = "completed" if p_status == "success" else p_status
                    JOB_STORE[run_id]["message"]     = f"Playbook finished: {p_status}"
                    JOB_STORE[run_id]["finished_at"] = datetime.now().isoformat()
                print(f"[API] run {payload.portal_key}/{payload.job_id} -> {p_status}")
            except Exception as e:
                with JOB_STORE_LOCK:
                    JOB_STORE[run_id]["status"]      = "failed"
                    JOB_STORE[run_id]["message"]     = str(e)
                    JOB_STORE[run_id]["finished_at"] = datetime.now().isoformat()
                print(f"[API] run {payload.portal_key}/{payload.job_id} -> ERROR: {e}")

        background_tasks.add_task(run_playbook)

        return {
            "run_id":   run_id,
            "status":   "running",
            "portal":   display_names.get(payload.portal_key, payload.portal_key),
            "job_id":   payload.job_id,
            "platform": platform,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/status/{run_id}" )
def get_status(run_id: str):
    """Poll this to check if a playbook run has finished."""
    with JOB_STORE_LOCK:
        job = JOB_STORE.get(run_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Run ID '{run_id}' not found")
    return job


@app.post("/api/confirm/{run_id}")
def confirm_run(run_id: str):
    """Manually mark a run as completed from the frontend."""
    with JOB_STORE_LOCK:
        job = JOB_STORE.get(run_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Run ID '{run_id}' not found")

    with JOB_STORE_LOCK:
        JOB_STORE[run_id]["status"]      = "completed"
        JOB_STORE[run_id]["message"]     = "Manually confirmed via UI"
        JOB_STORE[run_id]["finished_at"] = datetime.now().isoformat()

    print(f"[API] Run {run_id} manually confirmed")
    return {"status": "completed", "run_id": run_id}


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/debug")
def debug():
    import openpyxl
    wb = openpyxl.load_workbook(EXCEL_PATH)
    portal_df = read_portal_urls()
    return {
        "sheets": wb.sheetnames,
        "job_queue_path": str(EXCEL_PATH),
        "portal_urls_path": str(PORTAL_URLS_PATH),
        "total_portals": len(portal_df),
    }
# -- Batch Models
class BatchJobItem(BaseModel):
    portal_key: str
    job_id: str

class BatchSubmitRequest(BaseModel):
    jobs: list[BatchJobItem]

BATCH_STORE: dict[str, dict] = {}
BATCH_STORE_LOCK = threading.Lock()


@app.post("/api/submit/batch")
def submit_batch(payload: BatchSubmitRequest, background_tasks: BackgroundTasks):
    """Submit multiple jobs sequentially."""
    if not payload.jobs:
        raise HTTPException(status_code=400, detail="No jobs provided")

    em = ExcelManager()
    display_names = get_portal_display_names()

    # Validate all jobs upfront
    validated = []
    for item in payload.jobs:
        job = em.get_job(item.job_id)
        if not job:
            raise HTTPException(status_code=404, detail=f"Job '{item.job_id}' not found")
        validated.append({
            "portal_key": item.portal_key,
            "job_id":     item.job_id,
            "job_title":  str(job.get("Title", item.job_id)),
        })

    batch_id = str(uuid.uuid4())
    batch_jobs = []
    for v in validated:
        run_id = str(uuid.uuid4())
        with JOB_STORE_LOCK:
            JOB_STORE[run_id] = {
                "status":      "pending",
                "portal":      display_names.get(v["portal_key"], v["portal_key"]),
                "job_id":      v["job_id"],
                "job_title":   v["job_title"],
                "platform":    "",
                "message":     "Waiting to start...",
                "started_at":  None,
                "finished_at": None,
                "batch_id":    batch_id,
            }
        batch_jobs.append({**v, "run_id": run_id})

    with BATCH_STORE_LOCK:
        BATCH_STORE[batch_id] = {
            "status":        "running",
            "jobs":          batch_jobs,
            "current_index": 0,
            "total":         len(batch_jobs),
            "completed":     0,
            "failed":        0,
        }

    def run_single(item, idx):
        import time
        run_id     = item["run_id"]
        portal_key = item["portal_key"]
        job_id     = item["job_id"]

        with JOB_STORE_LOCK:
            JOB_STORE[run_id]["status"]     = "running"
            JOB_STORE[run_id]["message"]    = "Playbook is running..."
            JOB_STORE[run_id]["started_at"] = datetime.now().isoformat()

        try:
            portal_url  = Config.get_portal_url(portal_key)
            credentials = Config.get_credentials(portal_key)
            PlaybookClass, platform = get_playbook_class(portal_url)

            if not PlaybookClass:
                raise Exception(f"No playbook for platform '{platform}'")

            with JOB_STORE_LOCK:
                JOB_STORE[run_id]["platform"] = platform

            thread_em = ExcelManager()
            job = thread_em.get_job(job_id)
            if not job:
                raise Exception(f"Job '{job_id}' not found")

            job_data = {
                "JobId":        job_id,
                "Title":        job["Title"],
                "Description":  job["Description"],
                "Location":     job.get("Location", ""),
                "City":         job.get("City", "Toronto"),
                "Salary":       job.get("Salary", ""),
                "HourlyRate":   job.get("HourlyRate", ""),
                "Duration":     "520 Hours (approximately 3 months)",
                "Requirements": job.get("Requirements", ""),
                "JobType":      job.get("JobType", "Internship"),
                "Industry":     job.get("Industry", "Technology"),
                "JobFunction":  job.get("JobFunction", ""),
                "StudentGroup": job.get("StudentGroup", "All Students"),
                "Department":   job.get("Department", ""),
                "portal_name":  portal_key,
            }

            playbook = PlaybookClass(
                portal_url=portal_url,
                credentials=credentials,
                job_data=job_data,
            )
            playbook.run_id = run_id
            playbook.batch_mode = True
            result = playbook.execute()
            p_status = result.get("status", "FAILED")
        

            with JOB_STORE_LOCK:
                if p_status == "POSTED":
                    JOB_STORE[run_id]["status"] = "completed"
                    JOB_STORE[run_id]["message"] = "Form filled successfully"
                else:
                    JOB_STORE[run_id]["status"] = "failed"
                    JOB_STORE[run_id]["message"] = result.get("error","UNKNOWN_ERROR" )
                JOB_STORE[run_id]["finished_at"] = datetime.now().isoformat()

            with BATCH_STORE_LOCK:
                if p_status == "POSTED":
                    BATCH_STORE[batch_id]["completed"] += 1
                else:
                    BATCH_STORE[batch_id]["failed"] += 1

            print(f"[BATCH] Worker {idx+1}/{len(batch_jobs)} done: {portal_key}/{job_id} -> {p_status}")

        except Exception as e:
            with JOB_STORE_LOCK:
                JOB_STORE[run_id]["status"]      = "failed"
                JOB_STORE[run_id]["message"]     = str(e)
                JOB_STORE[run_id]["finished_at"] = datetime.now().isoformat()
            with BATCH_STORE_LOCK:
                BATCH_STORE[batch_id]["failed"] += 1
            print(f"[BATCH] Worker {idx+1} failed: {e}")

    def run_batch():
        from concurrent.futures import ThreadPoolExecutor, as_completed
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {
                executor.submit(run_single, item, idx): idx
                for idx, item in enumerate(batch_jobs)
            }
            for future in as_completed(futures):
                future.result()

        with BATCH_STORE_LOCK:
            BATCH_STORE[batch_id]["status"] = "completed"

    background_tasks.add_task(run_batch)

    return {
        "batch_id": batch_id,
        "status":   "running",
        "total":    len(batch_jobs),
        "jobs":     [{"run_id": j["run_id"], "portal": j["portal_key"], "job_id": j["job_id"]} for j in batch_jobs],
    }


@app.get("/api/batch/status/{batch_id}")
def get_batch_status(batch_id: str):
    """Overall batch progress + each job's individual status."""
    with BATCH_STORE_LOCK:
        batch = BATCH_STORE.get(batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail=f"Batch '{batch_id}' not found")

    display_names = get_portal_display_names()
    jobs_status = []
    for item in batch["jobs"]:
        with JOB_STORE_LOCK:
            info = JOB_STORE.get(item["run_id"], {})
        jobs_status.append({
            "run_id":    item["run_id"],
            "portal":    display_names.get(item["portal_key"], item["portal_key"]),
            "job_id":    item["job_id"],
            "job_title": item["job_title"],
            "status":    info.get("status", "pending"),
            "message":   info.get("message", ""),
        })

    return {
        "batch_id":      batch_id,
        "status":        batch["status"],
        "total":         batch["total"],
        "completed":     batch["completed"],
        "failed":        batch["failed"],
        "current_index": batch["current_index"],
        "jobs":          jobs_status,
    }