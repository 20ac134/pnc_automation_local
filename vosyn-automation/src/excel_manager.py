import pandas as pd
from datetime import date, datetime, time
from pathlib import Path
from typing import List, Dict, Optional, Any
import uuid
import threading

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
EXCEL_PATH = DATA_DIR / "job_queue.xlsx"
TRACKING_PATH = DATA_DIR / "application_tracking.xlsx"
TRACKING_SHEET = "ApplicationTracking"
TRACKING_COLUMNS = [
    "TrackingId",
    "UniversityJobId",
    "JobId",
    "JobTitle",
    "PortalName",
    "University",
    "Country",
    "PostingStatus",
    "ApplicantsCount",
    "LastApplicantsCount",
    "NewApplicantsCount",
    "SubmittedDate",
    "SubmittedTime",
]
LEGACY_TRACKING_COLUMNS = [
    "PortalDisplayName",
    "SubmittedAt",
    "PostedAt",
    "LastCheckedAt",
    "CreatedAt",
    "UpdatedAt",
    "PortalPostingId",
    "ProofLink",
    "Notes",
    "LastRunId",
    "BatchId",
]

_EXCEL_LOCK = threading.RLock()

class ExcelManager:
#Manages job queue stored in Excel file
    
    def __init__(self, excel_path: Path | str = EXCEL_PATH, tracking_path: Path | str = TRACKING_PATH):
        self.excel_path = Path(excel_path)
        self.tracking_path = Path(tracking_path)
        
        if not self.excel_path.exists():
            raise FileNotFoundError(
                f"Excel file not found: {excel_path}\n"
                f"Please create it with JobPosts, PostingRuns, and JobTemplates sheets"
            )

    def get_queued_jobs(self) -> List[Dict]:
        df = pd.read_excel(self.excel_path, sheet_name='JobPosts')
        queued = df[df['Status'] == 'QUEUED']
        return queued.to_dict('records')

    def get_job(self, job_id: str) -> Optional[Dict]:
        df = pd.read_excel(self.excel_path, sheet_name='JobPosts')
        job_rows = df[df['JobId'] == job_id]
        
        if len(job_rows) == 0:
            return None
        
        return job_rows.iloc[0].to_dict()

    def get_posting_runs(self, job_id: str) -> List[Dict]:
        df = pd.read_excel(self.excel_path, sheet_name='PostingRuns')
        runs = df[df['JobId'] == job_id]
        return runs.to_dict('records')

    def get_queued_runs(self, job_id: str) -> List[Dict]:
        all_runs = self.get_posting_runs(job_id)
        return [r for r in all_runs if r['RunStatus'] == 'QUEUED']

    def transition_job_status(
        self, 
        job_id: str, 
        from_status: str, 
        to_status: str, 
        locked_by: str = None
    ) -> bool:
        df = pd.read_excel(self.excel_path, sheet_name='JobPosts')
        for col in ["CreatedAt", "StartedAt", "FinishedAt"]:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce").dt.floor("s")
        
        if "LockedBy" in df.columns:
            df["LockedBy"] = df["LockedBy"].astype("string")
        
        job_mask = df['JobId'] == job_id
        
        if not job_mask.any():
            print(f"Warning: Job {job_id} not found")
            return False
        
        job_idx = df[job_mask].index[0]
        current_status = df.loc[job_idx, 'Status']
        
        if current_status != from_status:
            print(f"Warning: Job {job_id} status is {current_status}, expected {from_status}")
            return False
        
        df.loc[job_idx, 'Status'] = to_status
        
        if to_status == 'RUNNING':
            df.loc[job_idx, 'StartedAt'] = pd.Timestamp.now().floor("s")
            if locked_by:
                df.loc[job_idx, 'LockedBy'] = locked_by
        
        elif to_status in ['POSTED', 'FAILED', 'PARTIAL_FAILED']:
            df.loc[job_idx, 'FinishedAt'] = pd.Timestamp.now().floor("s")
        
        self._write_sheet(df, 'JobPosts')
        
        return True

    def update_posting_run(
        self,
        run_id: str,
        status: str,
        portal_posting_id: str = None,
        proof_link: str = None,
        error_reason: str = None
    ):
        df = pd.read_excel(self.excel_path, sheet_name='PostingRuns')

        for col in ["CreatedAt", "StartedAt", "FinishedAt"]:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce").dt.floor("s")

        for col in ["PortalPostingId", "ProofLink", "ErrorReason", "PortalName", "PortalUrl", "RunStatus"]:
            if col in df.columns:
                df[col] = df[col].astype("string")
        
        run_mask = df['RunId'] == run_id
        
        if not run_mask.any():
            print(f"Warning: Run {run_id} not found")
            return
        
        run_idx = df[run_mask].index[0]
        
        df.loc[run_idx, 'RunStatus'] = status
        df.loc[run_idx, 'FinishedAt'] = pd.Timestamp.now().floor("s")
        
        if portal_posting_id:
            df.loc[run_idx, 'PortalPostingId'] = str(portal_posting_id)
        
        if proof_link:
            df.loc[run_idx, 'ProofLink'] = proof_link
        
        if error_reason:
            df.loc[run_idx, 'ErrorReason'] = error_reason
        
        current_attempts = df.loc[run_idx, 'Attempts']
        df.loc[run_idx, 'Attempts'] = current_attempts + 1
        
        self._write_sheet(df, 'PostingRuns')

    def record_application_posting(
        self,
        job_id: str,
        job_title: str,
        portal_name: str,
        portal_display_name: str = "",
        country: str = "",
        university_job_id: str = "",
        posting_status: str = "POSTED",
        applicants_count: int = 0,
        submitted_at: str | datetime = None,
    ) -> Dict[str, Any]:
        """Create an application tracking row for a submitted job."""
        with _EXCEL_LOCK:
            df = self._read_tracking_sheet()
            applicant_total = self._safe_int(applicants_count)
            submitted_timestamp = self._parse_timestamp(submitted_at) or pd.Timestamp.now().floor("s")
            tracking_id = f"TRACK_{uuid.uuid4().hex[:10].upper()}"

            row = {
                "TrackingId": tracking_id,
                "UniversityJobId": str(university_job_id or ""),
                "JobId": str(job_id),
                "JobTitle": str(job_title or job_id),
                "PortalName": str(portal_name).strip().lower(),
                "University": str(portal_display_name or portal_name),
                "Country": str(country or ""),
                "PostingStatus": str(posting_status or "POSTED").upper(),
                "ApplicantsCount": applicant_total,
                "LastApplicantsCount": 0,
                "NewApplicantsCount": applicant_total,
                "SubmittedDate": self._format_date_value(submitted_timestamp),
                "SubmittedTime": self._format_time_value(submitted_timestamp),
            }

            df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
            df = self._normalize_tracking_df(df)
            self._write_tracking_sheet(df)
            return self._clean_record(row)

    def get_application_tracking(
        self,
        job_id: str = None,
        portal_name: str = None,
        status: str = None,
    ) -> List[Dict[str, Any]]:
        """Return application tracking records, optionally filtered."""
        df = self._read_tracking_sheet()
        if df.empty:
            return []

        if job_id:
            df = df[df["JobId"].astype(str) == str(job_id)]
        if portal_name:
            df = df[df["PortalName"].astype(str).str.lower() == str(portal_name).lower()]
        if status:
            df = df[df["PostingStatus"].astype(str).str.upper() == str(status).upper()]

        if "SubmittedDate" in df.columns:
            sort_values = df.apply(self._submitted_sort_value, axis=1)
            df = (
                df.assign(_SubmittedSort=sort_values)
                .sort_values("_SubmittedSort", ascending=False, na_position="last")
                .drop(columns=["_SubmittedSort"])
            )

        return [self._clean_record(row) for row in df.to_dict("records")]

    def get_tracking_record(self, tracking_id: str) -> Optional[Dict[str, Any]]:
        records = self.get_application_tracking()
        for record in records:
            if record.get("TrackingId") == tracking_id:
                return record
        return None

    def update_applicant_count(
        self,
        applicants_count: int,
        tracking_id: str = None,
        job_id: str = None,
        portal_name: str = None,
        status: str = None,
    ) -> Dict[str, Any]:
        """Update applicant count for one tracking row."""
        applicant_total = self._safe_int(applicants_count)
        if applicant_total < 0:
            raise ValueError("Applicants count cannot be negative")

        with _EXCEL_LOCK:
            df = self._read_tracking_sheet()
            if df.empty:
                raise ValueError("No application tracking records exist yet")

            row_idx = self._find_tracking_index(df, tracking_id, job_id, portal_name)
            if row_idx is None:
                raise ValueError("Tracking record not found")

            previous_total = self._safe_int(df.loc[row_idx, "ApplicantsCount"])

            df.loc[row_idx, "LastApplicantsCount"] = previous_total
            df.loc[row_idx, "ApplicantsCount"] = applicant_total
            df.loc[row_idx, "NewApplicantsCount"] = max(applicant_total - previous_total, 0)

            if status:
                df.loc[row_idx, "PostingStatus"] = status.upper()

            self._write_tracking_sheet(df)
            return self._clean_record(df.loc[row_idx].to_dict())

    def get_tracking_summary(self) -> Dict[str, Any]:
        """Return totals for postings and applicants by job and portal."""
        df = self._read_tracking_sheet()
        if df.empty:
            return {
                "total_postings": 0,
                "total_applicants": 0,
                "jobs_tracked": 0,
                "portals_tracked": 0,
                "by_status": [],
                "by_job": [],
                "by_portal": [],
            }

        df["ApplicantsCount"] = pd.to_numeric(df["ApplicantsCount"], errors="coerce").fillna(0).astype(int)

        by_status = (
            df.groupby("PostingStatus", dropna=False)
            .size()
            .reset_index(name="postings")
            .sort_values("postings", ascending=False)
        )

        by_job = (
            df.groupby(["JobId", "JobTitle"], dropna=False)
            .agg(postings=("TrackingId", "count"), applicants=("ApplicantsCount", "sum"))
            .reset_index()
            .sort_values(["applicants", "postings"], ascending=False)
        )

        by_portal = (
            df.groupby(["PortalName", "University"], dropna=False)
            .agg(postings=("TrackingId", "count"), applicants=("ApplicantsCount", "sum"))
            .reset_index()
            .sort_values(["applicants", "postings"], ascending=False)
        )

        return {
            "total_postings": int(len(df)),
            "total_applicants": int(df["ApplicantsCount"].sum()),
            "jobs_tracked": int(df["JobId"].nunique()),
            "portals_tracked": int(df["PortalName"].nunique()),
            "by_status": [self._clean_record(row) for row in by_status.to_dict("records")],
            "by_job": [self._clean_record(row) for row in by_job.to_dict("records")],
            "by_portal": [self._clean_record(row) for row in by_portal.to_dict("records")],
        }

    def transition_run_status(
        self,
        run_id: str,
        from_status: str,
        to_status: str
    ) -> bool:
        df = pd.read_excel(self.excel_path, sheet_name='PostingRuns')
        
        run_mask = df['RunId'] == run_id
        
        if not run_mask.any():
            return False
        
        run_idx = df[run_mask].index[0]
        current_status = df.loc[run_idx, 'RunStatus']
        
        if current_status != from_status:
            return False
        
        df.loc[run_idx, 'RunStatus'] = to_status
        
        if to_status == 'RUNNING':
            df.loc[run_idx, 'StartedAt'] = pd.Timestamp.now().floor("s")
        
        self._write_sheet(df, 'PostingRuns')
        return True

    def create_job(
        self,
        title: str,
        description: str,
        location: str,
        portals: List[str],
        salary: str = None,
        template_id: str = None
    ) -> str:
        job_id = f"JOB_{uuid.uuid4().hex[:8].upper()}"
        
        job_data = {
            'JobId': job_id,
            'Title': title,
            'Description': description,
            'Location': location,
            'Salary': salary,
            'TemplateId': template_id,
            'Status': 'QUEUED',
            'CreatedAt': datetime.now(),
            'StartedAt': None,
            'FinishedAt': None,
            'LockedBy': None
        }
        
        df_jobs = pd.read_excel(self.excel_path, sheet_name='JobPosts')
        df_jobs = pd.concat([df_jobs, pd.DataFrame([job_data])], ignore_index=True)
        self._write_sheet(df_jobs, 'JobPosts')
        
        df_runs = pd.read_excel(self.excel_path, sheet_name='PostingRuns')
        
        for portal in portals:
            run_id = f"RUN_{uuid.uuid4().hex[:8].upper()}"
            
            run_data = {
                'RunId': run_id,
                'JobId': job_id,
                'PortalName': portal,
                #'PortalUrl': self._get_portal_url(portal),
                'RunStatus': 'QUEUED',
                'PortalPostingId': None,
                'ProofLink': None,
                'ErrorReason': None,
                'Attempts': 0,
                'CreatedAt': datetime.now(),
                'FinishedAt': None
            }
            
            df_runs = pd.concat([df_runs, pd.DataFrame([run_data])], ignore_index=True)
        
        self._write_sheet(df_runs, 'PostingRuns')
        
        print(f"Created job {job_id} with {len(portals)} posting runs")
        return job_id

    def _write_sheet(self, df: pd.DataFrame, sheet_name: str):
        self.excel_path.parent.mkdir(parents=True, exist_ok=True)

        with _EXCEL_LOCK:
            mode = "a" if self.excel_path.exists() else "w"

            if mode == "a":
                with pd.ExcelWriter(
                    self.excel_path,
                    engine="openpyxl",
                    mode="a",
                    if_sheet_exists="replace",
                ) as writer:
                    df.to_excel(writer, sheet_name=sheet_name, index=False)
            else:
                with pd.ExcelWriter(self.excel_path, engine="openpyxl", mode="w") as writer:
                    df.to_excel(writer, sheet_name=sheet_name, index=False)

    def _read_tracking_sheet(self) -> pd.DataFrame:
        if not self.tracking_path.exists():
            return self._normalize_tracking_df(pd.DataFrame(columns=TRACKING_COLUMNS))

        try:
            df = pd.read_excel(self.tracking_path, sheet_name=TRACKING_SHEET)
        except ValueError:
            df = pd.DataFrame(columns=TRACKING_COLUMNS)
        return self._normalize_tracking_df(df)

    def _write_tracking_sheet(self, df: pd.DataFrame):
        self.tracking_path.parent.mkdir(parents=True, exist_ok=True)

        with _EXCEL_LOCK:
            with pd.ExcelWriter(self.tracking_path, engine="openpyxl", mode="w") as writer:
                df.to_excel(writer, sheet_name=TRACKING_SHEET, index=False)

    def _normalize_tracking_df(self, df: pd.DataFrame) -> pd.DataFrame:
        if "University" not in df.columns and "PortalDisplayName" in df.columns:
            df["University"] = df["PortalDisplayName"]
        elif "University" in df.columns and "PortalDisplayName" in df.columns:
            df["University"] = df["University"].fillna(df["PortalDisplayName"])

        source_timestamps = pd.Series([None] * len(df), index=df.index)
        for col in ["SubmittedAt", "PostedAt"]:
            if col in df.columns:
                parsed_values = df[col].apply(self._parse_timestamp)
                source_timestamps = source_timestamps.where(source_timestamps.notna(), parsed_values)

        for col in ["SubmittedDate", "SubmittedTime"]:
            if col not in df.columns:
                df[col] = None

        df["SubmittedDate"] = [
            self._format_date_value(existing) or self._format_date_value(source_timestamps.loc[idx])
            for idx, existing in df["SubmittedDate"].items()
        ]
        df["SubmittedTime"] = [
            self._format_time_value(existing) or self._format_time_value(source_timestamps.loc[idx])
            for idx, existing in df["SubmittedTime"].items()
        ]

        df = df.drop(columns=[col for col in LEGACY_TRACKING_COLUMNS if col in df.columns])

        for col in TRACKING_COLUMNS:
            if col not in df.columns:
                df[col] = None

        df["University"] = [
            existing if not self._is_missing(existing) else portal_name
            for existing, portal_name in zip(df["University"], df["PortalName"])
        ]

        ordered_columns = TRACKING_COLUMNS + [col for col in df.columns if col not in TRACKING_COLUMNS]
        df = df[ordered_columns]

        for col in ["ApplicantsCount", "LastApplicantsCount", "NewApplicantsCount"]:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

        df["SubmittedDate"] = df["SubmittedDate"].apply(self._format_date_value)
        df["SubmittedTime"] = df["SubmittedTime"].apply(self._format_time_value)

        return df

    def _find_tracking_index(
        self,
        df: pd.DataFrame,
        tracking_id: str = None,
        job_id: str = None,
        portal_name: str = None,
    ) -> Optional[int]:
        if tracking_id:
            matches = df[df["TrackingId"].astype(str) == str(tracking_id)]
        elif job_id and portal_name:
            matches = df[
                (df["JobId"].astype(str) == str(job_id))
                & (df["PortalName"].astype(str).str.lower() == str(portal_name).lower())
            ]
        else:
            raise ValueError("Provide tracking_id or both job_id and portal_name")

        if matches.empty:
            return None
        return int(matches.index[-1])

    @staticmethod
    def _safe_int(value: Any) -> int:
        if ExcelManager._is_missing(value):
            return 0
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _parse_timestamp(value: str | datetime = None):
        if ExcelManager._is_missing(value):
            return None
        parsed = pd.to_datetime(value, errors="coerce")
        if pd.isna(parsed):
            return None
        parsed = pd.Timestamp(parsed)
        if parsed.tzinfo is not None:
            parsed = parsed.tz_convert(None)
        return parsed.floor("s")

    @staticmethod
    def _format_date_value(value: Any) -> Optional[str]:
        if ExcelManager._is_missing(value):
            return None
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d")
        if isinstance(value, date):
            return value.strftime("%Y-%m-%d")

        text = str(value).strip()
        parsed = pd.to_datetime(text, errors="coerce")
        if pd.isna(parsed):
            return text
        return pd.Timestamp(parsed).strftime("%Y-%m-%d")

    @staticmethod
    def _format_time_value(value: Any) -> Optional[str]:
        if ExcelManager._is_missing(value):
            return None
        if isinstance(value, datetime):
            return value.strftime("%H:%M:%S")
        if isinstance(value, time):
            return value.strftime("%H:%M:%S")

        text = str(value).strip()
        parsed = pd.to_datetime(text, errors="coerce")
        if pd.isna(parsed):
            return text
        return pd.Timestamp(parsed).strftime("%H:%M:%S")

    @staticmethod
    def _submitted_sort_value(record: pd.Series):
        submitted_date = record.get("SubmittedDate")
        submitted_time = record.get("SubmittedTime")
        if ExcelManager._is_missing(submitted_date):
            return pd.NaT
        time_part = "00:00:00" if ExcelManager._is_missing(submitted_time) else str(submitted_time).strip()
        return ExcelManager._parse_timestamp(f"{submitted_date} {time_part}") or pd.NaT

    @staticmethod
    def _is_missing(value: Any) -> bool:
        if value is None:
            return True
        try:
            if pd.isna(value):
                return True
        except (TypeError, ValueError):
            pass
        return isinstance(value, str) and value.strip() == ""

    @staticmethod
    def _clean_record(record: Dict[str, Any]) -> Dict[str, Any]:
        cleaned = {}
        for key, value in record.items():
            if isinstance(value, pd.Timestamp):
                cleaned[key] = None if pd.isna(value) else value.isoformat()
            elif isinstance(value, datetime):
                cleaned[key] = value.isoformat()
            elif isinstance(value, (date, time)):
                cleaned[key] = value.isoformat()
            elif ExcelManager._is_missing(value):
                cleaned[key] = None
            elif hasattr(value, "item"):
                cleaned[key] = value.item()
            else:
                cleaned[key] = value
        return cleaned

    def _get_portal_url(self, portal_name: str) -> str:
        portal_urls = {
            'laurentian': 'https://careerhub.laurentian.ca/employers/login.htm',
            'sfu': 'https://myexperience.sfu.ca',
            'concordia': 'https://excel.concordia.ca/employers/login-page.htm',
            'saskatchewan': 'https://careerlink.usask.ca/login-main/employer-login.htm',
            'unb': 'https://experience.unb.ca/home/employers/login.htm',
            'mta': 'https://experience.mta.ca/employer/login.htm',
            'wlu': 'https://navigator.wlu.ca/home/employers/login.htm',
            'regina': 'https://uregina-csm.symplicity.com/employers/',
            'royalroads': 'https://royalroads-csm.symplicity.com/employers/',
        }
        
        return portal_urls.get(portal_name, 'URL_NOT_FOUND')

    def finalize_job_status(self, job_id: str):
        runs = self.get_posting_runs(job_id)
        statuses = [r['RunStatus'] for r in runs]
        
        if all(s == 'POSTED' for s in statuses):
            final_status = 'POSTED'
        elif all(s == 'FAILED' for s in statuses):
            final_status = 'FAILED'
        else:
            final_status = 'PARTIAL_FAILED'
        #CHANGE IT LATER 
        #self.transition_job_status(job_id, 'RUNNING', final_status)
        
        return final_status


# TESTING CODE 

if __name__ == "__main__":
    """
    Test the Excel Manager
    Run this to verify everything works
    """
    print("=" * 60)
    print("Testing Excel Manager")
    print("=" * 60)
    print()
    
    
    em = ExcelManager(EXCEL_PATH)
    
    print("Test 1: Creating a test job")
    job_id = em.create_job(
        title="TEST - Software Engineer",
        description="This is a test job posting",
        location="Toronto, ON",
        portals=['laurentian', 'sfu'],
        salary="80k-100k"
    )
    print(f"Created: {job_id}")
    print()
    
    
    print("Test 2: Getting queued jobs")
    queued = em.get_queued_jobs()
    print(f"Found {len(queued)} queued jobs")
    for job in queued:
        print(f"   - {job['JobId']}: {job['Title']}")
    print()
    
    
    print("Test 3: Transitioning job status")
    success = em.transition_job_status(job_id, 'QUEUED', 'RUNNING', 'WORKER_TEST')
    if success:
        print(f" Successfully transitioned {job_id} to RUNNING")
    else:
        print(f" Failed to transition {job_id}")
    print()
    
    
    print("Test 4: Getting posting runs")
    runs = em.get_posting_runs(job_id)
    print(f"Found {len(runs)} posting runs for {job_id}")
    for run in runs:
        print(f"   - {run['RunId']}: {run['PortalName']} ({run['RunStatus']})")
    print()
    
    
    print("Test 5: Updating posting run")
    if runs:
        first_run = runs[0]
        em.update_posting_run(
            run_id=first_run['RunId'],
            status='POSTED',
            portal_posting_id='TEST_12345',
            proof_link='screenshots/test.png'
        )
        print(f"Updated {first_run['RunId']}")
    print()
    
    
    print("Test 6: Finalizing job status")
    
    if len(runs) > 1:
        em.update_posting_run(
            run_id=runs[1]['RunId'],
            status='FAILED',
            error_reason='Test failure'
        )
    
    final_status = em.finalize_job_status(job_id)
    print(f"Final status: {final_status}")
    print()
    
    print("=" * 60)
    print("All tests passed!")
    print("=" * 60)
    print()
    print("Check your Excel file - you should see:")
    print("1. New job in JobPosts (with PARTIAL_FAILED status)")
    print("2. Two runs in PostingRuns (one POSTED, one FAILED)")
