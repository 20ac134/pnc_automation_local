from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import undetected_chromedriver as uc

import time
import random
from datetime import datetime
from pathlib import Path
from abc import ABC, abstractmethod
import threading
import tempfile


_DRIVER_INIT_LOCK = threading.Lock()

class BasePortalPlaybook(ABC):
  
    
    def __init__(self, portal_url: str, credentials: dict, job_data: dict, screenshot_dir: str = "screenshots"):
        self.portal_url = portal_url
        self.credentials = credentials
        self.job_data = job_data
        self.screenshot_dir = Path(screenshot_dir)
        self.screenshot_dir.mkdir(exist_ok=True)
        self.driver = None
        self.wait = None
        self.run_id = None  # Set by API when running via frontend

    def setup_driver(self):
        user_data_dir = tempfile.mkdtemp(prefix="uc_profile_")
        options = uc.ChromeOptions()
        options.add_argument(f"--user-data-dir={user_data_dir}")
            
        width = random.randint(1200, 1920)
        height = random.randint(800, 1080)
        options.add_argument(f'--window-size={width},{height}')
        
        prefs = {"profile.default_content_setting_values.notifications": 2}
        options.add_experimental_option("prefs", prefs)
        with _DRIVER_INIT_LOCK:

            self.driver = uc.Chrome(options=options, version_main=147)
        
        self.wait = WebDriverWait(self.driver, 15)
        
       
        
        print(f"Browser initialized (window size: {width}x{height})")

    def human_delay(self, min_sec: float = 2, max_sec: float = 5):
        delay = random.uniform(min_sec, max_sec)
        time.sleep(delay)

    def slow_type(self, element, text: str, min_delay: float = 0.05, max_delay: float = 0.15):
        for char in text:
            element.send_keys(char)
            time.sleep(random.uniform(min_delay, max_delay))

   

    @abstractmethod
    def login(self):
        pass

    @abstractmethod
    def navigate_to_job_posting(self):
        pass

    @abstractmethod
    def fill_job_form(self):
        pass

    @abstractmethod
    def submit_and_capture_proof(self) -> dict:
        pass

    def execute(self) -> dict:
        try:
            print("=" * 60)
            print(f"Starting automation for {self.job_data.get('Title', 'Unknown Job')}")
            print(f"Portal: {self.portal_url}")
            print("=" * 60)
            
            print("\n[1/5] Setting up browser")
            self.setup_driver()
            self.human_delay(1, 2)
            
            print("\n[2/5] Logging in")
            self.login()
            self.human_delay(2, 4)
            
            print("\n[3/5] Navigating to job posting form")
            self.navigate_to_job_posting()
            self.human_delay(2, 3)
            
            print("\n[4/5] Filling job form")
            self.fill_job_form()
            self.human_delay(2, 3)
            
            print("\n[5/5] Submitting and capturing proof")
            result = self.submit_and_capture_proof()
            
            print("\n" + "=" * 60)
            print("SUCCESS!")
            print(f"Confirmation ID: {result.get('confirmation_id')}")
            print(f"Screenshot: {result.get('screenshot_path')}")
            print("=" * 60)
            
            return {
                'status': 'POSTED',
                'confirmation_id': result.get('confirmation_id'),
                'screenshot_path': result.get('screenshot_path')
            }
            
        except Exception as e:
            print("\n" + "=" * 60)
            print("FAILED!")
            print(f"Error: {str(e)}")
            print("=" * 60)
    
    
        
        finally:
            if self.driver:
                print("\nClosing browser")
                self.driver.quit()

    def safe_find_element(self, by, value, timeout: int = 10):
        wait = WebDriverWait(self.driver, timeout)
        return wait.until(EC.presence_of_element_located((by, value)))

    def safe_click(self, by, value, timeout: int = 10):
        wait = WebDriverWait(self.driver, timeout)
        element = wait.until(EC.element_to_be_clickable((by, value)))
        element.click()


#TESTING CODE 

if __name__ == "__main__":
   
    class TestPlaybook(BasePortalPlaybook):
        """Simple test implementation"""
        
        def login(self):
            print("  → Opening Google (test URL)")
            self.driver.get("https://www.google.com")
            self.human_delay(2, 3)
        
        def navigate_to_job_posting(self):
            print("  → Simulating navigation")
            self.human_delay(1, 2)
        
        def fill_job_form(self):
            print("  → Simulating form fill")
            # Find search box and type slowly
            search_box = self.driver.find_element(By.NAME, "q")
            self.slow_type(search_box, "Selenium automation test")
            self.human_delay(1, 2)
        
        def submit_and_capture_proof(self):
            print (" -> Done")
            return {
                'confirmation_id': "TEST_12345",
            }
    
    print("=" * 60)
    print("Testing Base Playbook")
    print("=" * 60)
    print()
    
    # Test data
    test_job = {
        'JobId': 'TEST_001',
        'Title': 'Test Job - Software Engineer',
        'Description': 'This is a test',
        'Location': 'Toronto, ON'
    }
    
    test_creds = {
        'username': 'test@example.com',
        'password': 'test123'
    }
    
    # Run test
    playbook = TestPlaybook(
        portal_url='https://www.google.com',
        credentials=test_creds,
        job_data=test_job
    )
    
    result = playbook.execute()
    
    print("\nResult:")
    print(f"Status: {result['status']}")
    print(f"Confirmation ID: {result.get('confirmation_id')}")
    print()
    print("Base playbook test complete!")