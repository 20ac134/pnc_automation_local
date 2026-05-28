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

import sys
import time


class SymplicityPlaybook(BasePortalPlaybook):

    def login(self):
        print(f"Navigating to: {self.portal_url}")
        self.driver.get(self.portal_url)
        self.human_delay(2, 3)

        username_field = None
        username_keywords = ['username', 'email', 'user', 'login', 'j_username', 'userid', 'employerid']
        
        all_inputs = self.driver.find_elements(By.TAG_NAME, "input")
        
        for field in all_inputs:
            try:
                if not field.is_displayed():
                    continue
                
                field_type = (field.get_attribute('type') or '').lower()
                field_id = (field.get_attribute('id') or '').lower()
                field_name = (field.get_attribute('name') or '').lower()
                field_placeholder = (field.get_attribute('placeholder') or '').lower()
                
                if field_type in ['hidden', 'submit', 'button', 'checkbox', 'radio']:
                    continue
                
                search_text = f"{field_id} {field_name} {field_placeholder}"
                
                for keyword in username_keywords:
                    if keyword in search_text:
                        username_field = field
                        print(f"Found username field: id='{field_id}' name='{field_name}' type='{field_type}'")
                        break
                
                if username_field:
                    break
            except:
                continue

        if not username_field:
            raise Exception("Could not find username/email field")

        print("Entering username")
        username_field.clear()
        self.slow_type(username_field, self.credentials['username'])
        self.human_delay(1, 2)

        print("Detecting password field")
        password_field = None
        
        for field in all_inputs:
            try:
                if not field.is_displayed():
                    continue
                
                field_type = (field.get_attribute('type') or '').lower()
                field_id = (field.get_attribute('id') or '').lower()
                field_name = (field.get_attribute('name') or '').lower()
                
                if field_type == 'password':
                    password_field = field
                    print(f"Found password field: id='{field_id}' name='{field_name}'")
                    break
                
                search_text = f"{field_id} {field_name}"
                if 'password' in search_text or 'passwd' in search_text or field_name == 'pass':
                    password_field = field
                    print(f"Found password field: id='{field_id}' name='{field_name}'")
                    break
            except:
                continue

        if not password_field:
            raise Exception("Could not find password field")
        
        print("Entering password")
        password_field.clear()
        self.slow_type(password_field, self.credentials['password'])
        self.human_delay(1, 2)

        print("Looking for login button")
        login_button = None
        
        button_keywords = ['login', 'sign in', 'submit', 'log in', 'connexion', 'se connecter']
        
        all_buttons = self.driver.find_elements(By.TAG_NAME, "button")
        all_links = self.driver.find_elements(By.TAG_NAME, "a")
        all_submit_inputs = self.driver.find_elements(By.XPATH, "//input[@type='submit']")
        
        for elem in all_buttons + all_links + all_submit_inputs:
            try:
                if not elem.is_displayed():
                    continue
                
                elem_text = (elem.text or '').lower()
                elem_value = (elem.get_attribute('value') or '').lower()
                elem_id = (elem.get_attribute('id') or '').lower()
                
                search_text = f"{elem_text} {elem_value} {elem_id}"
                
                for keyword in button_keywords:
                    if keyword in search_text:
                        login_button = elem
                        print(f"Found login button: '{elem_text or elem_value}' id='{elem_id}'")
                        break
                
                if login_button:
                    break
            except:
                continue
        
        if not login_button:
            try:
                login_button = self.driver.find_element(By.XPATH, "//button[@type='submit']")
                print("Found submit button (fallback)")
            except:
                try:
                    login_button = self.driver.find_element(By.XPATH, "//input[@type='submit']")
                    print("Found submit input (fallback)")
                except:
                    raise Exception("Could not find login button")
        
        print("Clicking login button")
        try:
            login_button.click()
        except:
            self.driver.execute_script("arguments[0].click();", login_button)

        print("Waiting for dashboard")
        self.human_delay(3, 5)

        if "login" in self.driver.current_url.lower() or "signin" in self.driver.current_url.lower():
            raise Exception("Login failed - still on login page")

        print("Login successful!")

    def navigate_to_job_posting(self):
        print("Step 1/3: Looking for 'Post a Job' button")
        self.human_delay(3, 5)

        try:
            self.driver.execute_script("return document.readyState") == "complete"

            selectors = [
                # Input button variants (VIU, Caltech)
                "//input[@type='button' and @value='Post a Job']",
                "//input[@type='button' and @value='Post A Job']",
                "//input[@type='button' and contains(@value, 'Post an Opportunity')]",
                "//input[@type='button' and contains(@value, 'Post An Opportunity')]",
                "//input[contains(@value, 'Post') and contains(@value, 'Job')]",
                "//input[contains(@value, 'Post') and contains(@value, 'Opportunity')]",
                "//input[contains(@class, 'btn_primary')]",
                # Standard button/link
                "//button[normalize-space(text())='Post a Job']",
                "//a[normalize-space(text())='Post a Job']",
                "//button[contains(@class, 'btn') and contains(., 'Post a Job')]",
                "//a[contains(@class, 'btn') and contains(., 'Post a Job')]",
                "//*[normalize-space(text())='Post a Job' and (self::button or self::a)]",
                # Post A Job variants
                "//button[normalize-space(text())='Post A Job']",
                "//a[normalize-space(text())='Post A Job']",
                "//button[contains(@class, 'btn') and contains(., 'Post A Job')]",
                "//a[contains(@class, 'btn') and contains(., 'Post A Job')]",
                "//*[normalize-space(text())='Post A Job' and (self::button or self::a)]",
                # Post a New Job variants (Queen's)
                "//a[contains(., 'Post a New Job')]",
                "//button[contains(., 'Post a New Job')]",
                "//a[contains(., 'Post A New Job')]",
                "//button[contains(., 'Post A New Job')]",
                # Post an Opportunity variants
                "//a[contains(., 'Post an Opportunity')]",
                "//a[contains(., 'Post An Opportunity')]",
                "//button[contains(., 'Post an Opportunity')]",
                "//button[contains(., 'Post An Opportunity')]",
                # Class-based fallbacks
                "//button[contains(@class, 'btn--post--job')]",
                "//button[contains(@class, 'post--job')]",
            ]

            post_job_btn = None
            for selector in selectors:
                try:
                    elements = self.driver.find_elements(By.XPATH, selector)
                    for elem in elements:
                        try:
                            if elem.is_displayed() and elem.is_enabled():
                                post_job_btn = elem
                                break
                        except:
                            pass
                    if post_job_btn:
                        break
                except:
                    continue

            # Brute force fallback — scan buttons, links, AND input buttons
            if not post_job_btn:
                all_buttons = self.driver.find_elements(By.TAG_NAME, "button")
                all_links   = self.driver.find_elements(By.TAG_NAME, "a")
                all_input_btns = self.driver.find_elements(By.XPATH, "//input[@type='button']")
                for elem in all_buttons + all_links + all_input_btns:
                    try:
                        if elem.is_displayed():
                            text = (elem.text or '').lower()
                            value = (elem.get_attribute('value') or '').lower()
                            if ('post a job' in text or 'post a job' in value or
                                'post an opportunity' in text or 'post an opportunity' in value or
                                'post a new job' in text or 'post a new job' in value):
                                post_job_btn = elem
                                print(f"Found post button (fallback): '{text or value}'")
                                break
                    except:
                        pass

            if not post_job_btn:
                raise Exception("Post a Job button not found")

            self.driver.execute_script("arguments[0].scrollIntoView(true);", post_job_btn)
            self.human_delay(1, 2)

            try:
                post_job_btn.click()
            except:
                self.driver.execute_script("arguments[0].click();", post_job_btn)

            print("Clicked 'Post a Job'")

        except Exception as e:
            print(f"Error: {e}")
            raise

        self.human_delay(3, 4)

        print("Step 2/3: Handling job category modal")
        self.handle_job_category_modal()

        self.human_delay(3, 4)

        # Step 3/3: Second "Post a Job" button (e.g. VIU input button)
        print("Step 3/3: Looking for second 'Post a Job' button")
        time.sleep(3)
        try:
            selectors = [
                # Input button variants (VIU, Caltech)
                "//input[@type='button' and @value='Post a Job']",
                "//input[@type='button' and @value='Post A Job']",
                "//input[@type='button' and contains(@value, 'Post an Opportunity')]",
                "//input[@type='button' and contains(@value, 'Post An Opportunity')]",
                "//input[contains(@value, 'Post') and contains(@value, 'Job')]",
                "//input[contains(@value, 'Post') and contains(@value, 'Opportunity')]",
                "//input[contains(@class, 'btn_primary')]",
                # Standard button/link
                "//button[normalize-space(text())='Post a Job']",
                "//a[normalize-space(text())='Post a Job']",
                "//button[normalize-space(text())='Post A Job']",
                "//a[normalize-space(text())='Post A Job']",
                # Post a New Job variants (Queen's)
                "//a[contains(., 'Post a New Job')]",
                "//button[contains(., 'Post a New Job')]",
                "//a[contains(., 'Post A New Job')]",
                "//button[contains(., 'Post A New Job')]",
                "//input[@type='button' and contains(@value, 'Post a New Job')]",
                # Post an Opportunity variants
                "//a[contains(., 'Post an Opportunity')]",
                "//a[contains(., 'Post An Opportunity')]",
                "//button[contains(., 'Post an Opportunity')]",
                "//button[contains(., 'Post An Opportunity')]",
                # Class-based
                "//button[contains(@class, 'btn') and contains(., 'Post a Job')]",
                "//a[contains(@class, 'btn') and contains(., 'Post a Job')]",
                "//button[contains(@class, 'btn') and contains(., 'Post A Job')]",
                "//a[contains(@class, 'btn') and contains(., 'Post A Job')]",
                "//button[contains(@class, 'btn--post--job')]",
                "//button[contains(@class, 'post--job')]",
            ]

            clicked = False
            for selector in selectors:
                try:
                    elements = self.driver.find_elements(By.XPATH, selector)
                    for el in elements:
                        if el.is_displayed() and el.is_enabled():
                            self.driver.execute_script("arguments[0].click();", el)
                            print(f"Clicked 'Post a Job' via: {selector}")
                            clicked = True
                            break
                except:
                    continue
                if clicked:
                    break

            # Brute force fallback
            if not clicked:
                for el in self.driver.find_elements(By.XPATH, "//input[@type='button'] | //button | //a"):
                    try:
                        text = (el.text or '').lower()
                        value = (el.get_attribute('value') or '').lower()
                        if el.is_displayed() and (
                            'post a job' in text or 'post a job' in value or
                            'post a new job' in text or 'post a new job' in value or
                            'post an opportunity' in text or 'post an opportunity' in value
                        ):
                            self.driver.execute_script("arguments[0].click();", el)
                            print("Clicked via brute force")
                            clicked = True
                            break
                    except:
                        continue

            if not clicked:
                print("No second 'Post a Job' button found — may not be needed")

        except Exception as e:
            print(f"Step 3 failed: {e}")

        # Step 3b: Handle school selection modal (if it appears)
        print("Step 3b: Checking for school selection modal")
        time.sleep(3)
        try:
            school_selectors = [
                "//a[contains(text(), 'This School Only')]",
                "//button[contains(text(), 'This School Only')]",
                "//*[contains(text(), 'This School Only')]",
                "//input[@type='button' and contains(@value, 'This School Only')]",
                # Mines — "This Organization and its Sister Institutions Only"
                "//a[contains(., 'This Organization')]",
                "//button[contains(., 'This Organization')]",
                "//a[contains(., 'Sister Institutions Only')]",
                "//button[contains(., 'Sister Institutions Only')]",
            ]

            clicked = False
            clicked = False
            for selector in school_selectors:
                try:
                    elements = self.driver.find_elements(By.XPATH, selector)
                    for el in elements:
                        el_text = el.text or ''
                        el_value = el.get_attribute("value") or ''
                        if el.is_displayed() and (
                            "This School" in el_text or "This School" in el_value or
                            "This Organization" in el_text or "This Organization" in el_value or
                            "Sister Institutions" in el_text or "Sister Institutions" in el_value
                        ):
                            self.driver.execute_script("arguments[0].click();", el)
                            print("Clicked school/organization selection")
                            clicked = True
                            break
                except:
                    continue
                if clicked:
                    break


            if not clicked:
                print("No school selection modal found — continuing")

        except Exception as e:
            print(f"Step 3b: {e}")

        # Step 3c: Handle language selection page (e.g. Laurentian)
        print("Step 3c: Checking for language selection page")
        time.sleep(3)
        try:
            # Try to select "English Only" if radio exists
            english_radio = self.driver.find_elements(By.XPATH,
                "//input[@type='radio' and contains(@value, 'English')]"
                " | //label[contains(., 'English Only')]/../input[@type='radio']"
                " | //label[contains(., 'English Only')]/preceding-sibling::input[@type='radio']"
            )

            if english_radio:
                radio = english_radio[0]
                if not radio.is_selected():
                    self.driver.execute_script("arguments[0].click();", radio)
                print("  Selected 'English Only'")
                self.human_delay(1, 2)

            # Click "Next" button — check independently of radio
            next_btn = None
            next_selectors = [
                "//input[@id='nextBtn']",
                "//input[@type='submit' and @value='Next']",
                "//button[normalize-space(text())='Next']",
                "//input[@type='button' and @value='Next']",
                "//a[normalize-space(text())='Next']",
            ]
            for selector in next_selectors:
                try:
                    btn = self.driver.find_element(By.XPATH, selector)
                    if btn.is_displayed():
                        next_btn = btn
                        break
                except:
                    continue

            if next_btn:
                self.driver.execute_script("arguments[0].click();", next_btn)
                print("  Clicked 'Next'")
            else:
                print("  No language/Next page found — continuing")

        except Exception as e:
            print(f"  Step 3c: {e}")

        print("Waiting for job posting form")
        self.human_delay(3, 4)
        print("Job posting form loaded")

    def handle_job_category_modal(self):
        print("Looking for job category modal")
        self.human_delay(3, 5)

        try:
            modal = self.wait.until(
                EC.presence_of_element_located((By.XPATH, "//div[contains(@class, 'modal') and contains(@class, 'visible')]"))
            )
            print("Modal found and visible")
            self.human_delay(2, 3)

            post_buttons = modal.find_elements(By.XPATH, ".//button[contains(text(), 'Post')] | .//a[contains(text(), 'Post')]")

            visible_buttons = []
            for btn in post_buttons:
                try:
                    if btn.is_displayed() and btn.is_enabled():
                        visible_buttons.append(btn)
                except:
                    pass

            if visible_buttons:
                print(f"Found {len(visible_buttons)} 'Post' buttons in modal")
                first_button = visible_buttons[0]
                print("Clicking first 'Post' button")

                self.driver.execute_script("arguments[0].scrollIntoView(true);", first_button)
                self.human_delay(1, 1.5)

                try:
                    first_button.click()
                except:
                    self.driver.execute_script("arguments[0].click();", first_button)

                print("Category selected")
                self.human_delay(2, 3)
                PortalHelpers.handle_agreement(self.driver)
            else:
                print("No visible Post buttons found")

        except Exception as e:
            print(f"Error handling modal: {e}")
            try:
                all_post_buttons = self.driver.find_elements(By.XPATH, "//button[contains(text(), 'Post')] | //a[contains(text(), 'Post')]")
                if all_post_buttons:
                    for btn in all_post_buttons:
                        if btn.is_displayed():
                            self.driver.execute_script("arguments[0].click();", btn)
                            print("Clicked via JavaScript")
                            self.human_delay(2, 3)
                            PortalHelpers.handle_agreement(self.driver)
                            break
            except Exception as e2:
                print(f"Alternative method failed: {e2}")


    def fill_job_form(self):
        print()
        print("=" * 60)
        print("SCANNING FORM AND AUTO-FILLING")
        print("=" * 60)
        print()

        title        = self.job_data.get('Title', '')
        description  = self.job_data.get('Description', '')
        location     = self.job_data.get('Location', '')
        salary       = self.job_data.get('Salary', '')
        duration     = self.job_data.get('Duration', '4 months')
        requirements = self.job_data.get('Requirements', '')

        keywords_mapping = {
            'Title':        ['job title', 'position title', 'position name', 'job name', 'titre du poste', 'titre', 'title of position', 'Opportunity Title'],
            'Location':     ['job location', 'work location', 'lieu de travail', 'location of work'],
            'Duration':     ['duration', 'term length', 'work term', 'contract length', 'duree', 'durée'],
            'Salary':       ['salaryamount', 'salary amount', 'hourly rate', 'taux horaire', 'wage', 'salary'],
            'Description':  ['job description', 'position description', 'description du poste', 'description of opportunity' , 'roles and responsibilities'],
            'Requirements': ['job requirements', 'qualifications', 'required skills', 'exigences', 'job qualifications', 'opportunity requirements'],
            'Positions':    ['number of positions', 'number of openings', 'nombre de postes', 'numberofpositions'],
            'Address':      ['address line one', 'address :', 'street address', 'adresse','Location'],
            'City':         ['city :', 'ville', 'city'],
            'Postal':       ['postal code / zip code', 'postal code', 'zip code', 'code postal'],
        }

        always_skip = [
            'email',
            'phone',
            'fax',
            'website',
            'semi-colon',
            'hoursperweek',
            'hours per week',
            'datedeadline',
            'date deadline',
            'deliverywebsite',
            'delivery website',
            'online_delivery',
            'contact first',
            'contact last',
            'contact title',
            'first name',
            'last name',
        ]

        data_to_fill = {
            'Title':        title,
            'Location':     location,
            'Duration':     duration,
            'Salary':       str(salary) if salary else '',
            'Description':  description,
            'Requirements': requirements,
            'Positions':    '1',
            'Address':      '100 King Street West',
            'City':         'Toronto',
            'Postal':       'M5X 1A9',
        }

        self.driver.execute_script("window.scrollTo(0, 0);")
        self.human_delay(2, 3)

        all_inputs    = self.driver.find_elements(By.TAG_NAME, "input")
        all_textareas = self.driver.find_elements(By.TAG_NAME, "textarea")
        all_selects   = self.driver.find_elements(By.TAG_NAME, "select")

        print(f"Found {len(all_inputs)} inputs and {len(all_textareas)} textareas")
        print()

        filled_fields   = []
        skipped_fields  = []
        required_missed = []

        for field in all_inputs + all_textareas + all_selects:
            try:
                if not field.is_displayed():
                    continue

                field_tag  = (field.tag_name or '').lower()
                field_type = (field.get_attribute('type') or '').lower()

                if field_tag == 'input' and field_type in ['hidden', 'submit', 'button', 'checkbox', 'radio', 'file']:
                    continue

                field_id          = (field.get_attribute('id') or '').lower()
                field_name        = (field.get_attribute('name') or '').lower()
                field_placeholder = (field.get_attribute('placeholder') or '').lower()

                label_text  = PortalHelpers.get_label_for_field(self.driver, field, field_id)
                is_required = PortalHelpers.is_required_field(label_text, field)

                search_string = PortalHelpers._norm(f"{label_text} {field_id} {field_name} {field_placeholder}")

                should_skip = False
                for skip_word in always_skip:
                    if PortalHelpers._norm(skip_word) in search_string:
                        skipped_fields.append(f"{label_text[:40] or field_name} (skip: '{skip_word}')")
                        should_skip = True
                        break

                if should_skip:
                    continue

                matched = False
                for excel_col, keywords in keywords_mapping.items():
                    if not data_to_fill.get(excel_col):
                        continue

                    for keyword in keywords:
                        if PortalHelpers._norm(keyword) in search_string:
                            value = data_to_fill[excel_col]

                            try:
                                PortalHelpers.robust_fill(self.driver, field, str(value))

                                display_name = label_text[:40] or field_name or field_id
                                print(f"Filled '{excel_col}': {display_name}")
                                print(f"  Value: {str(value)[:50]}")
                                print()

                                filled_fields.append(excel_col)
                                data_to_fill[excel_col] = ''
                                matched = True
                                break

                            except Exception as e:
                                print(f"Error filling {label_text[:40]}: {e}")

                    if matched:
                        break

                if not matched and is_required:
                    required_missed.append({
                        'label': label_text[:60] or field_name,
                        'id':    field_id,
                        'name':  field_name
                    })

            except:
                continue

        print()
        print("Handling Froala rich text editors")
        froala_editors = self.driver.find_elements(
            By.CSS_SELECTOR, "div.fr-element.fr-view[contenteditable='true']"
        )
        print(f"Found {len(froala_editors)} rich text editors")
        print()

        if len(froala_editors) >= 1 and data_to_fill.get('Description'):
            try:
                print("Filling Description (editor 1)")
                desc_editor = froala_editors[0]
                self.driver.execute_script("arguments[0].scrollIntoView(true);", desc_editor)
                self.human_delay(1, 2)
                desc_editor.click()
                self.human_delay(0.5, 1)
                desc_editor.send_keys(data_to_fill['Description'])
                print(f"  Value: {data_to_fill['Description'][:50]}")
                print()
                filled_fields.append('Description')
                data_to_fill['Description'] = ''
            except Exception as e:
                print(f"Description error: {e}")

        if len(froala_editors) >= 2 and data_to_fill.get('Requirements'):
            try:
                print("Filling Requirements (editor 2)")
                req_editor = froala_editors[1]
                self.driver.execute_script("arguments[0].scrollIntoView(true);", req_editor)
                self.human_delay(1, 2)
                req_editor.click()
                self.human_delay(0.5, 1)
                req_editor.send_keys(data_to_fill['Requirements'])
                print(f"  Value: {data_to_fill['Requirements'][:50]}")
                print()
                filled_fields.append('Requirements')
                data_to_fill['Requirements'] = ''
            except Exception as e:
                print(f"Requirements error: {e}")

        print()
        print("=" * 60)
        print("SUMMARY")
        print("=" * 60)
        print(f"Fields filled:  {len(filled_fields)}")
        for f in filled_fields:
            print(f"  + {f}")
        print()
        print(f"Fields skipped: {len(skipped_fields)}")
        for f in skipped_fields:
            print(f"  - {f}")
        print()

        unfilled = [k for k, v in data_to_fill.items() if v]
        if unfilled:
            print(f"Warning - Excel data not placed: {', '.join(unfilled)}")

        if required_missed:
            print()
            print(f"WARNING: {len(required_missed)} required (*) fields not filled:")
            for f in required_missed:
                print(f"  ! '{f['label']}'  id='{f['id']}'  name='{f['name']}'")
            print()
            print("These fields need attention before submitting!")

        print("=" * 60)
        print()

        # --- Additional required fields (Symplicity-specific) ---

        # 1. Salary — fill the "From" field
        print("Filling salary field")
        try:
            salary_input = self.driver.find_element(By.ID, "compensation_from_position_")
            salary_input.clear()
            salary_value = str(salary) if salary else "0"
            salary_input.send_keys(salary_value)
            print(f"  Filled salary: {salary_value}")
        except Exception as e:
            print(f"  Salary field not found (may not be required): {e}")

        # 2. Position Type — check "Full Time"
        print("Selecting Position Type")
        try:
            position_checkbox = self.driver.find_element(
                By.ID, "dnf_class_values_job__job_type___3_check"
            )
            if not position_checkbox.is_selected():
                self.driver.execute_script("arguments[0].click();", position_checkbox)
            print("  Selected 'Full Time'")
        except:
            # Fallback for Ottawa-style radio buttons
            try:
                ft_radio = self.driver.find_element(By.ID, "answer_18_1")
                if not ft_radio.is_selected():
                    self.driver.execute_script("arguments[0].click();", ft_radio)
                print("  Selected 'Full-time' (Ottawa style)")
            except:
                # Generic fallback — find by label text
                try:
                    ft_label = self.driver.find_element(By.XPATH,
                        "//label[normalize-space()='Full-time' or normalize-space()='Full Time']"
                    )
                    label_for = ft_label.get_attribute("for")
                    if label_for:
                        radio = self.driver.find_element(By.ID, label_for)
                        self.driver.execute_script("arguments[0].click();", radio)
                        print("  Selected 'Full-time' via label")
                    else:
                        self.driver.execute_script("arguments[0].click();", ft_label)
                        print("  Clicked 'Full-time' label directly")
                except Exception as e:
                    print(f"  Position Type not found: {e}")

        # 3. Automatic Application Packet Generation — select "Yes"
        print("Selecting Automatic Application Packet Generation")
        try:
            auto_packet_radio = self.driver.find_element(By.XPATH,
                "//input[@name='dnf_class_values[job][auto_gen_resume_book]' and @value='1']"
            )
            if not auto_packet_radio.is_selected():
                self.driver.execute_script("arguments[0].click();", auto_packet_radio)
            print("  Selected 'Yes'")
        except Exception as e:
            print(f"  Auto packet generation not found (optional): {e}")

        # 4. Policy Affirmation — check the checkbox
        print("Selecting Policy Affirmation")
        try:
            policy_checkbox = self.driver.find_element(
                By.ID, "dnf_class_values_job__policy_affirmed_1_check"
            )
            if not policy_checkbox.is_selected():
                self.driver.execute_script("arguments[0].click();", policy_checkbox)
            print("  Checked Policy Affirmation")
        except Exception as e:
            print(f"  Policy Affirmation not found (optional): {e}")

        print()
        print("=" * 60)

        self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        self.human_delay(2, 3)

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

      
        # Batch mode: no human confirm — return immediately, completion
        # is driven by execute()'s return value in api.py
        if getattr(self, "batch_mode", False):
            print("FORM FILLED (batch mode - no confirm)")
            return {'confirmation_id': 'NOT_SUBMITTED'}

        # Single mode (API): wait for UI confirm
        if self.run_id:
            from src.API.api import JOB_STORE, JOB_STORE_LOCK
            while True:
                time.sleep(2)
                with JOB_STORE_LOCK:
                    status = JOB_STORE.get(self.run_id, {}).get("status", "running")
                if status in ("completed", "failed"):
                    print("Confirmed via UI — closing browser")
                    break
        # Terminal mode: wait for Enter
        elif sys.stdin and sys.stdin.isatty():
            print("Press Enter when done reviewing")
            input()
        else:
            time.sleep(300)

        return {'confirmation_id': 'NOT_SUBMITTED'}



#  MAIN 

if __name__ == "__main__":
    from src.config import Config
    from src.excel_manager import ExcelManager
    import pandas as pd

    print("=" * 60)
    print("Symplicity Playbook")
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

    portal_map = {
        "1": "regina", "2": "laurentian", "3": "guelph", "4": "queens",
        "5": "ottawa", "6": "unb", "7": "mta", "8": "royalroads",
        "9": "trent", "10": "viu", "11": "caltech", "12": "calpoly",
        "13": "csulb", "14": "mines", "15": "cumberland", "16": "fsu",
        "17": "gonzaga", "18": "gcu", "19": "harvard", "20": "niu",
        "21": "pennstate", "22": "tamu", "23": "purdue",
    }

    print("Available Portals:")
    for num, name in portal_map.items():
        print(f"  {num:>3}. {name.upper()}")
    print()

    while True:
        choice = input("Select portal number: ").strip()
        if choice in portal_map:
            selected_portal = portal_map[choice]
            break
        print("Invalid choice.")

    print(f"\nPortal: {selected_portal.upper()}\n")

    portal_url = Config.get_portal_url(selected_portal)
    credentials = Config.get_credentials(selected_portal)
    print(f"URL:      {portal_url}")
    print(f"Username: {credentials['username']}\n")

    playbook = SymplicityPlaybook(
        portal_url=portal_url,
        credentials=credentials,
        job_data={
            "JobId": selected_job.get("JobId", ""),
            "Title": selected_job.get("Title", ""),
            "Description": selected_job.get("Description", ""),
            "Location": selected_job.get("Location", ""),
            "City": selected_job.get("City", "Toronto"),
            "Province": selected_job.get("Province", "ON"),
            "Salary": selected_job.get("Salary", ""),
            "HourlyRate": selected_job.get("HourlyRate", ""),
            "Duration": "520 Hours (approximately 3 months)",
            "Requirements": selected_job.get("Requirements", ""),
            "JobType": selected_job.get("JobType", "Internship"),
            "Industry": selected_job.get("Industry", "Technology"),
            "JobFunction": selected_job.get("JobFunction", ""),
            "StudentGroup": selected_job.get("StudentGroup", "All Students"),
            "Department": selected_job.get("Department", ""),
            "portal_name": selected_portal,
        }
    )

    result = playbook.execute()
    print(f"\nResult: {result['status']}")
    print("=" * 60)
    print("COMPLETE")
    print("=" * 60)