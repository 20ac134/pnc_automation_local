import sys
from pathlib import Path
from src.portal_helpers import PortalHelpers
import pandas as pd
import re

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.excel_manager import ExcelManager
from src.playbooks.base_playbook import BasePortalPlaybook
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support import expected_conditions as EC
from datetime import datetime, timedelta
import time


class MSFormsPlaybook(BasePortalPlaybook):

    # ------------------------------------------------------------------ #
    #  LOGIN — No login needed, just navigate to the form URL              #
    # ------------------------------------------------------------------ #

    def login(self):
        print(f"Navigating to: {self.portal_url}")
        self.driver.get(self.portal_url)
        self.human_delay(3, 5)
        print("Microsoft Forms page loaded — no login required")

    # ------------------------------------------------------------------ #
    #  NAVIGATE — Click through info pages to reach the form               #
    # ------------------------------------------------------------------ #

    def navigate_to_job_posting(self):
        # The form has: Cover -> Page 1/3 (info) -> Page 2/3 (contact) -> Page 3/3 (job form)

        # --- Cover page: click "Start now" ---
        print("Step 1/4: Clicking 'Start now' on cover page")
        self.human_delay(2, 3)

        clicked = False
        for selector in [
            "//button[contains(., 'Start now')]",
            "//button[contains(., 'Start Now')]",
        ]:
            try:
                for el in self.driver.find_elements(By.XPATH, selector):
                    if el.is_displayed():
                        self.driver.execute_script("arguments[0].click();", el)
                        print("  Clicked 'Start now'")
                        clicked = True
                        break
            except:
                continue
            if clicked:
                break

        if not clicked:
            print("  WARNING: 'Start now' not found")

        self.human_delay(3, 5)

        # --- Page 1/3: info-only page, no inputs — click "Next" to continue ---
        print("Step 2/4: Skipping info page (Page 1/3) -> clicking Next")
        try:
            next_btn = self.driver.find_element(By.XPATH, "//button[contains(., 'Next')]")
            self.driver.execute_script("arguments[0].click();", next_btn)
            print("  Clicked 'Next' -> Contact Information page (Page 2/3)")
        except Exception as e:
            print(f"  Could not click Next on info page: {e}")

        self.human_delay(3, 5)

        # --- Page 2/3: Contact Information — fill name, phone, email ---
        print("Step 3/4: Filling Contact Information (Page 2/3)")

        contact_name  = self.job_data.get('ContactName', 'Vosyn HR')
        contact_phone = self.job_data.get('ContactPhone', '437 744 1247')
        contact_email = self.job_data.get('ContactEmail', 'careers@vosyn.ai')

        contact_mapping = {
            'first and last name': contact_name,
            'name': contact_name,
            'phone number': contact_phone,
            'phone': contact_phone,
            'email address': contact_email,
            'email': contact_email,
        }

        # Find question containers and match by label text
        questions = self.driver.find_elements(By.XPATH,
            "//div[contains(@class,'question-content') or contains(@class,'__question')"
            " or @data-automation-id='questionItem'"
            " or contains(@class,'office-form-question')]"
        )

        filled_count = 0
        for q in questions:
            try:
                label = q.text.split('\n')[0].strip().lower()
                label = re.sub(r'\s*\*\s*$', '', label)
                for key, value in contact_mapping.items():
                    if key in label:
                        field = q.find_element(By.XPATH, ".//input[@type='text']")
                        if field.is_displayed():
                            field.click()
                            self.human_delay(0.3, 0.5)
                            field.send_keys(Keys.CONTROL, "a")
                            field.send_keys(Keys.BACKSPACE)
                            field.send_keys(str(value))
                            print(f"  Filled '{key}': {value}")
                            filled_count += 1
                            self.human_delay(0.5, 1)
                        break
            except:
                continue

        # Fallback: fill by order (Name, Phone, Email) if container matching failed
        if filled_count == 0:
            print("  Container matching failed — filling by order")
            visible_inputs = [el for el in self.driver.find_elements(By.TAG_NAME, "input")
                              if el.is_displayed()]
            for i, value in enumerate([contact_name, contact_phone, contact_email]):
                if i < len(visible_inputs):
                    try:
                        visible_inputs[i].click()
                        self.human_delay(0.3, 0.5)
                        visible_inputs[i].send_keys(Keys.CONTROL, "a")
                        visible_inputs[i].send_keys(Keys.BACKSPACE)
                        visible_inputs[i].send_keys(str(value))
                        print(f"  Filled field {i+1}: {value}")
                        self.human_delay(0.5, 1)
                    except Exception as e:
                        print(f"  Error on field {i+1}: {e}")

        # --- Click "Next" to advance to Page 3/3 (Job form) ---
        print("Step 4/4: Clicking 'Next' -> Job posting form (Page 3/3)")
        self.human_delay(1, 2)
        try:
            next_btn = self.driver.find_element(By.XPATH, "//button[contains(., 'Next')]")
            self.driver.execute_script("arguments[0].click();", next_btn)
            print("  Clicked 'Next' -> now on Job Form (Page 3/3)")
        except Exception as e:
            print(f"  Could not click Next: {e}")

        self.human_delay(3, 5)
        print("Job posting form ready")

    # ------------------------------------------------------------------ #
    #  FILL JOB FORM — Microsoft Forms fields                             #
    # ------------------------------------------------------------------ #

    def fill_job_form(self):
        print()
        print("=" * 60)
        print("FILLING MICROSOFT FORMS JOB POSTING")
        print("=" * 60)
        print()

        title        = self.job_data.get('Title', '')
        description  = self.job_data.get('Description', '')
        location     = self.job_data.get('Location', 'Toronto, ON')
        salary       = self.job_data.get('Salary', '')
        requirements = self.job_data.get('Requirements', '')
        org_name     = self.job_data.get('OrgName', 'Vosyn inc.')
        work_type    = self.job_data.get('WorkType', 'Remote Work')
        position_type = self.job_data.get('PositionType', 'Full Time')
        qualifications = self.job_data.get('Qualifications', requirements)
        desired_skills = self.job_data.get('DesiredSkills', requirements)
        how_to_apply = self.job_data.get('HowToApply', 'Apply via email at careers@vosyn.ai')
        deadline     = self.job_data.get('ApplicationDeadline',
                        (datetime.today() + timedelta(days=30)).strftime('%Y-%m-%d'))
        website      = self.job_data.get('Website', 'https://vosyn.ai')
        benefits     = self.job_data.get('Benefits', '')
        job_link     = self.job_data.get('JobLink', '')

        self.driver.execute_script("window.scrollTo(0, 0);")
        self.human_delay(2, 3)

        # MS Forms labels fields with aria-label or nearby text
        # Strategy: find all question containers and match by label text

        filled_fields = []

        # --- Text fields ---
        # MS Forms uses data-automation-id or question containers
        # We'll find all input/textarea elements and match by nearby label text

        questions = self.driver.find_elements(By.XPATH,
            "//div[contains(@class, 'question-content') or contains(@class, '__question')]"
            " | //div[@data-automation-id='questionItem']"
            " | //div[contains(@class, 'office-form-question')]"
        )

        if not questions:
            # Fallback: find question blocks by structure
            questions = self.driver.find_elements(By.XPATH,
                "//div[.//span[contains(@class, 'text-format')] and .//input or .//textarea]"
            )

        if not questions:
            # Last resort: just find all visible inputs/textareas
            print("Could not find question containers — using direct field scan")
            self._fill_fields_by_order(
                title, org_name, location, description, qualifications,
                desired_skills, how_to_apply, deadline, website, salary,
                benefits, job_link
            )
        else:
            print(f"Found {len(questions)} question blocks")
            print()

            # Map label text to values
            field_mapping = {
                'job title': title,
                'name of organization': org_name,
                'location': location,
                'job description': description,
                'required qualification': qualifications,
                'desired skills': desired_skills,
                'how to apply': how_to_apply,
                'application deadline': deadline,
                'company website': website,
                'salary': salary,
                'hourly wage': salary,
                'benefits offered': benefits,
                'link to job posting': job_link,
            }

            for question in questions:
                try:
                    # Get the question label text
                    label_text = question.text.split('\n')[0].strip().lower()
                    label_text = re.sub(r'\s*\*\s*$', '', label_text)  # remove trailing *

                    # Try to match
                    matched_value = None
                    matched_key = None
                    for key, value in field_mapping.items():
                        if key in label_text:
                            matched_value = value
                            matched_key = key
                            break

                    if matched_value and matched_key:
                        # Find the input or textarea inside this question
                        try:
                            field = question.find_element(By.XPATH,
                                ".//input[@type='text' or @type='email' or @type='date' or not(@type)]"
                                " | .//textarea"
                            )
                            if field.is_displayed():
                                field.click()
                                self.human_delay(0.3, 0.5)
                                field.send_keys(Keys.CONTROL, "a")
                                field.send_keys(Keys.BACKSPACE)
                                field.send_keys(str(matched_value))
                                print(f"Filled '{matched_key}': {str(matched_value)[:50]}")
                                filled_fields.append(matched_key)
                                self.human_delay(0.5, 1)
                        except:
                            pass

                except:
                    continue

        # --- Radio buttons ---
        # Work Type
        print()
        print("Selecting Work Type")
        self._click_ms_radio(work_type)

        # Position Type
        print("Selecting Position Type")
        self._click_ms_radio(position_type)

        # --- Summary ---
        print()
        print("=" * 60)
        print("SUMMARY")
        print("=" * 60)
        print(f"Fields filled: {len(filled_fields)}")
        for f in filled_fields:
            print(f"  + {f}")
        print("=" * 60)
        print()

        self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        self.human_delay(2, 3)

    # ------------------------------------------------------------------ #
    #  HELPERS                                                             #
    # ------------------------------------------------------------------ #

    def _click_ms_radio(self, label_text: str):
        """Click a radio button in Microsoft Forms by its label text."""
        try:
            # MS Forms radio buttons are often divs with role="radio" or input[type="radio"]
            radio_selectors = [
                f"//input[@type='radio'][following-sibling::*[contains(., '{label_text}')]]",
                f"//div[@role='radio' and contains(., '{label_text}')]",
                f"//label[contains(., '{label_text}')]",
                f"//span[contains(., '{label_text}')]/ancestor::div[@role='option' or @role='radio']",
                f"//*[contains(text(), '{label_text}')]/ancestor::div[contains(@class, 'choice')]",
                f"//input[@type='radio']/..//span[contains(text(), '{label_text}')]/..",
            ]

            for selector in radio_selectors:
                try:
                    elements = self.driver.find_elements(By.XPATH, selector)
                    for el in elements:
                        if el.is_displayed():
                            self.driver.execute_script("arguments[0].click();", el)
                            print(f"  Selected '{label_text}'")
                            self.human_delay(0.5, 1)
                            return
                except:
                    continue

            # Brute force: find by exact text match
            all_spans = self.driver.find_elements(By.TAG_NAME, "span")
            for span in all_spans:
                try:
                    if span.is_displayed() and span.text.strip() == label_text:
                        parent = span.find_element(By.XPATH, "./..")
                        self.driver.execute_script("arguments[0].click();", parent)
                        print(f"  Selected '{label_text}' via span click")
                        self.human_delay(0.5, 1)
                        return
                except:
                    continue

            print(f"  WARNING: Could not find radio option '{label_text}'")

        except Exception as e:
            print(f"  Radio selection error: {e}")

    def _fill_fields_by_order(self, title, org_name, location, description,
                               qualifications, desired_skills, how_to_apply,
                               deadline, website, salary, benefits, job_link):
        """Fallback: fill fields by their order on the page."""
        print("Filling fields by page order (fallback)")

        all_inputs = self.driver.find_elements(By.XPATH,
            "//input[@type='text' or @type='email' or @type='date' or not(@type)]"
        )
        all_textareas = self.driver.find_elements(By.TAG_NAME, "textarea")

        visible_inputs = [f for f in all_inputs if f.is_displayed()]
        visible_textareas = [f for f in all_textareas if f.is_displayed()]

        # Expected order on Page 3:
        # Inputs: Job Title, Name of Org, Location, Application Deadline, Company Website, Salary, Link to Job
        # Textareas: Job Description, Required Qualification, Desired Skills, How to Apply, Benefits

        input_values = [title, org_name, location]
        textarea_values = [description, qualifications, desired_skills, how_to_apply]

        for i, value in enumerate(input_values):
            if i < len(visible_inputs) and value:
                try:
                    field = visible_inputs[i]
                    field.click()
                    self.human_delay(0.3, 0.5)
                    field.send_keys(Keys.CONTROL, "a")
                    field.send_keys(Keys.BACKSPACE)
                    field.send_keys(str(value))
                    print(f"  Filled input {i+1}: {str(value)[:50]}")
                    self.human_delay(0.5, 1)
                except Exception as e:
                    print(f"  Error filling input {i+1}: {e}")

        for i, value in enumerate(textarea_values):
            if i < len(visible_textareas) and value:
                try:
                    field = visible_textareas[i]
                    field.click()
                    self.human_delay(0.3, 0.5)
                    field.send_keys(Keys.CONTROL, "a")
                    field.send_keys(Keys.BACKSPACE)
                    field.send_keys(str(value))
                    print(f"  Filled textarea {i+1}: {str(value)[:50]}")
                    self.human_delay(0.5, 1)
                except Exception as e:
                    print(f"  Error filling textarea {i+1}: {e}")

        # Fill remaining inputs (deadline, website, salary, link)
        remaining_input_values = [deadline, website, str(salary), job_link]
        remaining_start = len(input_values)
        for i, value in enumerate(remaining_input_values):
            idx = remaining_start + i
            if idx < len(visible_inputs) and value:
                try:
                    field = visible_inputs[idx]
                    field.click()
                    self.human_delay(0.3, 0.5)
                    field.send_keys(Keys.CONTROL, "a")
                    field.send_keys(Keys.BACKSPACE)
                    field.send_keys(str(value))
                    print(f"  Filled input {idx+1}: {str(value)[:50]}")
                    self.human_delay(0.5, 1)
                except Exception as e:
                    print(f"  Error filling input {idx+1}: {e}")

        # Fill remaining textarea (benefits)
        if len(visible_textareas) > len(textarea_values) and benefits:
            try:
                field = visible_textareas[len(textarea_values)]
                field.click()
                self.human_delay(0.3, 0.5)
                field.send_keys(Keys.CONTROL, "a")
                field.send_keys(Keys.BACKSPACE)
                field.send_keys(str(benefits))
                print(f"  Filled benefits textarea")
                self.human_delay(0.5, 1)
            except Exception as e:
                print(f"  Error filling benefits: {e}")

    # ------------------------------------------------------------------ #
    #  SUBMIT                                                              #
    # ------------------------------------------------------------------ #

    def submit_and_capture_proof(self) -> dict:
        print("Looking for submit button (NOT clicking it)")

        self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        self.human_delay(2, 3)

        try:
            submit_btn = None
            selectors = [
                "//button[contains(text(), 'Submit')]",
                "//input[@type='submit' and contains(@value, 'Submit')]",
                "//button[@type='submit']",
                "//a[contains(text(), 'Submit')]"
            ]

            for selector in selectors:
                try:
                    buttons = self.driver.find_elements(By.XPATH, selector)
                    for btn in buttons:
                        if btn.is_displayed() and btn.is_enabled():
                            submit_btn = btn
                            break
                    if submit_btn:
                        break
                except:
                    continue

            if submit_btn:
                print("Submit button found (NOT clicking it)")
            else:
                print("Submit button not found")

        except Exception as e:
            print(f"Error finding submit button: {e}")

        print("FORM FILLED - waiting for review...")

        # If running from API with a run_id, wait for UI confirm
        # If running from terminal, wait for Enter
        import sys
        import time

        if self.run_id:
            # API mode — poll JOB_STORE for confirm
            from src.API.api import JOB_STORE, JOB_STORE_LOCK
            while True:
                time.sleep(2)
                with JOB_STORE_LOCK:
                    status = JOB_STORE.get(self.run_id, {}).get("status", "running")
                if status in ("completed", "failed"):
                    print("Confirmed via UI — closing browser")
                    break
        elif sys.stdin and sys.stdin.isatty():
            print("Press Enter when done reviewing")
            input()
        else:
            time.sleep(300)

        return {'confirmation_id': 'NOT_SUBMITTED'}


# ================================================================== #
#  MAIN                                                                #
# ================================================================== #

if __name__ == "__main__":
    from src.excel_manager import ExcelManager
    import pandas as pd

    print("=" * 60)
    print("Microsoft Forms Playbook - Nipissing")
    print("=" * 60)
    print()

    em = ExcelManager()
    df_jobs = pd.read_excel(em.excel_path, sheet_name='JobPosts')

    print("Available Jobs:")
    print("-" * 60)
    for i, row in df_jobs.iterrows():
        print(f"  {i+1:>3}. [{row['JobId']}] {row['Title']}")
    print()

    while True:
        choice = input(f"Select job (1-{len(df_jobs)}): ").strip()
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(df_jobs):
                selected_job = df_jobs.iloc[idx].to_dict()
                break
        except ValueError:
            pass
        print("Invalid choice.")

    print(f"\nSelected: {selected_job['Title']}\n")

    portal_url = "https://forms.office.com/pages/responsepage.aspx?id=2IYwsWuZZUCLY3hqklhgtYPxDhaf1mdLuekJLiVVCE9UQVpPSllTMUM2U1NSNDRVOERVMFJQUDc3WCQlQCN0PWcu&route=shorturl"

    playbook = MSFormsPlaybook(
        portal_url=portal_url,
        credentials={'username': '', 'password': ''},
        job_data={
            "JobId": selected_job.get("JobId", ""),
            "Title": selected_job.get("Title", ""),
            "Description": selected_job.get("Description", ""),
            "Location": selected_job.get("Location", "Toronto, ON"),
            "Salary": selected_job.get("Salary", ""),
            "Requirements": selected_job.get("Requirements", ""),
            "OrgName": "Vosyn inc.",
            "ContactName": "Vosyn HR",
            "ContactPhone": "437 744 1247",
            "ContactEmail": "careers@vosyn.ai",
            "WorkType": "Remote Work",
            "PositionType": "Full Time",
            "Qualifications": selected_job.get("Requirements", ""),
            "DesiredSkills": selected_job.get("Requirements", ""),
            "HowToApply": "Apply via email at careers@vosyn.ai",
            "ApplicationDeadline": selected_job.get("ApplicationDeadline", ""),
            "Website": "https://vosyn.ai",
            "portal_name": "nipissing",
        }
    )

    result = playbook.execute()
    print(f"\nResult: {result['status']}")
    print("=" * 60)