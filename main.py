#!/usr/bin/env python3
"""
Fish.audio Force Login Bot
Forces login every 7 seconds to kick out all other users
Simple and extremely effective approach
"""

import streamlit as st
import time
import os
import sys
import requests
import threading
import queue
import logging
from datetime import datetime
import platform

# Import selenium components
SELENIUM_AVAILABLE = False
IMPORT_ERRORS = []

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from selenium.common.exceptions import TimeoutException, NoSuchElementException
    SELENIUM_AVAILABLE = True
except ImportError as e:
    IMPORT_ERRORS.append(f"selenium: {e}")

try:
    from webdriver_manager.chrome import ChromeDriverManager
    WEBDRIVER_MANAGER_AVAILABLE = True
except ImportError as e:
    WEBDRIVER_MANAGER_AVAILABLE = False
    IMPORT_ERRORS.append(f"webdriver_manager: {e}")

try:
    import undetected_chromedriver as uc
    UNDETECTED_CHROME_AVAILABLE = True
except ImportError as e:
    UNDETECTED_CHROME_AVAILABLE = False
    IMPORT_ERRORS.append(f"undetected_chromedriver: {e}")

# Configuration
LOGIN_URL = "https://fish.audio/auth/"

# Setup logging
class StreamlitLogHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.logs = []
        
    def emit(self, record):
        log_entry = {
            'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'level': record.levelname,
            'message': record.getMessage()
        }
        self.logs.append(log_entry)
        if len(self.logs) > 100:
            self.logs.pop(0)

log_handler = StreamlitLogHandler()
logging.basicConfig(level=logging.INFO, handlers=[log_handler])
logger = logging.getLogger(__name__)

class ForceLoginBot:
    """Simple bot that forces login every X seconds to maintain exclusive access"""
    
    def __init__(self, email, password, login_interval=7):
        self.email = email
        self.password = password
        self.login_interval = login_interval
        self.driver = None
        self.wait = None
        self.running = False
        self.status_queue = queue.Queue()
        
        # Simple statistics
        self.stats = {
            'total_logins': 0,
            'successful_logins': 0,
            'failed_logins': 0,
            'start_time': None,
            'last_login_time': None,
            'current_status': 'Stopped',
            'consecutive_successes': 0,
            'max_consecutive_successes': 0
        }
    
    def setup_driver(self):
        """Initialize Chrome WebDriver"""
        try:
            if not SELENIUM_AVAILABLE:
                logger.error("Selenium not available.")
                return False
            
            chrome_options = Options()
            
            # Essential options for cloud deployment
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--disable-extensions")
            chrome_options.add_argument("--window-size=1920,1080")
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            # Anti-detection user agent
            chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
            
            # Find browser binary - prioritize Chromium on Streamlit Cloud
            chromium_paths = [
                "/usr/bin/chromium",           # Streamlit Cloud Chromium
                "/usr/bin/chromium-browser",   # Alternative Chromium path
                "/usr/bin/google-chrome",      # Google Chrome
                "/usr/bin/google-chrome-stable"
            ]
            
            browser_found = False
            for path in chromium_paths:
                if os.path.exists(path):
                    chrome_options.binary_location = path
                    logger.info(f"Found browser at: {path}")
                    browser_found = True
                    break
            
            if not browser_found:
                logger.warning("No browser binary found, using default")
            
            # Try multiple driver setup methods
            driver_setup_methods = [
                # Method 1: Use system chromedriver first (Streamlit Cloud)
                lambda: self._setup_system_chrome(chrome_options),
                
                # Method 2: Use webdriver-manager
                lambda: webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options),
                
                # Method 3: Use undetected chrome if available
                lambda: self._setup_undetected_chrome() if UNDETECTED_CHROME_AVAILABLE else None,
                
                # Method 4: Default Chrome setup
                lambda: webdriver.Chrome(options=chrome_options)
            ]
            
            driver_created = False
            for i, method in enumerate(driver_setup_methods):
                if method is None:
                    continue
                try:
                    logger.info(f"Attempting driver setup method {i+1}")
                    self.driver = method()
                    driver_created = True
                    logger.info(f"Successfully created driver using method {i+1}")
                    break
                except Exception as e:
                    logger.warning(f"Driver setup method {i+1} failed: {e}")
                    continue
            
            if not driver_created:
                logger.error("All driver setup methods failed")
                return False
            
            # Anti-detection measures
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            self.wait = WebDriverWait(self.driver, 10)
            logger.info("Force login bot driver initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error setting up driver: {e}")
            return False
    
    def _setup_undetected_chrome(self):
        """Setup undetected Chrome driver"""
        try:
            options = uc.ChromeOptions()
            options.add_argument("--headless")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")
            options.add_argument("--window-size=1920,1080")
            
            # Find Chromium binary for Streamlit Cloud
            chromium_paths = [
                "/usr/bin/chromium",
                "/usr/bin/chromium-browser", 
                "/usr/bin/google-chrome"
            ]
            
            for path in chromium_paths:
                if os.path.exists(path):
                    options.binary_location = path
                    logger.info(f"Undetected Chrome using binary: {path}")
                    break
            
            driver = uc.Chrome(options=options, version_main=None)
            return driver
            
        except Exception as e:
            logger.error(f"Undetected Chrome setup failed: {e}")
            raise e
    
    def _setup_system_chrome(self, chrome_options):
        """Try different system chromedriver paths - prioritize Streamlit Cloud"""
        driver_paths = [
            "/usr/bin/chromedriver",           # Streamlit Cloud chromedriver
            "/usr/bin/chromium-driver",        # Alternative name
            "/usr/local/bin/chromedriver"      # Alternative location
        ]
        
        for path in driver_paths:
            if os.path.exists(path):
                logger.info(f"Found chromedriver at: {path}")
                try:
                    service = Service(executable_path=path)
                    return webdriver.Chrome(service=service, options=chrome_options)
                except Exception as e:
                    logger.warning(f"Failed to use chromedriver at {path}: {e}")
                    continue
        
        raise Exception("No system chromedriver found")
    
    def force_login(self):
        """Force login to Fish.audio - kicks out anyone else"""
        try:
            self.stats['total_logins'] += 1
            self.stats['last_login_time'] = datetime.now()
            
            logger.info(f"🔥 FORCE LOGIN #{self.stats['total_logins']} - Going to login page...")
            
            # Always go directly to login page
            self.driver.get(LOGIN_URL)
            time.sleep(2)
            
            # Wait for page to load
            self.wait.until(lambda driver: driver.execute_script("return document.readyState") == "complete")
            
            # Fill email field
            try:
                email_field = self.wait.until(EC.presence_of_element_located((By.XPATH, '/html/body/div/div[3]/div/div[3]/form/div/div[1]/input')))
                email_field.clear()
                email_field.send_keys(self.email)
                logger.info("✅ Email entered")
            except TimeoutException:
                logger.error("❌ Could not find email field")
                self.stats['failed_logins'] += 1
                return False
            
            # Fill password field
            try:
                password_field = self.wait.until(EC.presence_of_element_located((By.XPATH, '/html/body/div/div[3]/div/div[3]/form/div/div[2]/input')))
                password_field.clear()
                password_field.send_keys(self.password)
                logger.info("✅ Password entered")
            except TimeoutException:
                logger.error("❌ Could not find password field")
                self.stats['failed_logins'] += 1
                return False
            
            # Click login button
            try:
                login_button = self.wait.until(EC.element_to_be_clickable((By.XPATH, '/html/body/div/div[3]/div/div[3]/form/div/button')))
                login_button.click()
                logger.info("✅ Login button clicked")
            except TimeoutException:
                logger.error("❌ Could not find login button")
                self.stats['failed_logins'] += 1
                return False
            
            # Wait for login to complete
            time.sleep(3)
            
            # Check if login was successful (simple check)
            current_url = self.driver.current_url
            if LOGIN_URL not in current_url:
                self.stats['successful_logins'] += 1
                self.stats['consecutive_successes'] += 1
                self.stats['max_consecutive_successes'] = max(
                    self.stats['max_consecutive_successes'], 
                    self.stats['consecutive_successes']
                )
                
                success_msg = f"🎯 FORCE LOGIN SUCCESS! Anyone else has been kicked out (#{self.stats['successful_logins']})"
                logger.info(success_msg)
                self.stats['current_status'] = 'Force login successful'
                return True
            else:
                self.stats['failed_logins'] += 1
                self.stats['consecutive_successes'] = 0
                
                fail_msg = f"❌ Force login failed (#{self.stats['failed_logins']})"
                logger.error(fail_msg)
                self.stats['current_status'] = 'Force login failed'
                return False
                
        except Exception as e:
            self.stats['failed_logins'] += 1
            self.stats['consecutive_successes'] = 0
            error_msg = f"❌ Error during force login: {e}"
            logger.error(error_msg)
            self.stats['current_status'] = 'Error occurred'
            return False
    
    def run(self):
        """Main force login loop - logs in every X seconds"""
        if not self.setup_driver():
            logger.error("Failed to setup driver")
            self.status_queue.put({
                "status": "error", 
                "message": "Failed to setup driver",
                "stats": self.stats
            })
            return
        
        self.running = True
        self.stats['start_time'] = datetime.now()
        self.stats['current_status'] = 'Starting force login mode'
        
        logger.info(f"🚀 STARTING FORCE LOGIN MODE - Will login every {self.login_interval} seconds")
        
        try:
            while self.running:
                # Force login every cycle
                if self.force_login():
                    success_msg = f"🎯 FORCE LOGIN SUCCESS! Kicked out all other users (Success #{self.stats['successful_logins']})"
                    self.status_queue.put({
                        "status": "success", 
                        "message": success_msg,
                        "stats": self.stats.copy(),
                        "action": "force_login_success"
                    })
                else:
                    fail_msg = f"❌ Force login failed (Failure #{self.stats['failed_logins']})"
                    self.status_queue.put({
                        "status": "error", 
                        "message": fail_msg,
                        "stats": self.stats.copy(),
                        "action": "force_login_failed"
                    })
                
                # Wait for next login cycle with countdown
                for i in range(self.login_interval):
                    if not self.running:
                        break
                    remaining = self.login_interval - i
                    
                    self.status_queue.put({
                        "status": "progress", 
                        "message": f"Next force login in {remaining}s",
                        "stats": self.stats.copy(),
                        "countdown": remaining
                    })
                    time.sleep(1)
                    
        except Exception as e:
            logger.error(f"Fatal error in force login loop: {e}")
            self.stats['current_status'] = 'Fatal error'
        finally:
            if self.driver:
                self.driver.quit()
                logger.info("Driver closed")
                self.stats['current_status'] = 'Stopped'
                self.status_queue.put({
                    "status": "info", 
                    "message": "Force login mode stopped",
                    "stats": self.stats.copy()
                })
    
    def stop(self):
        """Stop the force login mode"""
        self.running = False
        self.stats['current_status'] = 'Stopping...'
    
    def get_stats_summary(self):
        """Get formatted statistics summary"""
        if self.stats['start_time']:
            runtime = datetime.now() - self.stats['start_time']
            runtime_str = str(runtime).split('.')[0]
        else:
            runtime_str = "0:00:00"
        
        success_rate = round(self.stats['successful_logins'] / max(self.stats['total_logins'], 1) * 100, 1)
        
        return {
            'runtime': runtime_str,
            'total_logins': self.stats['total_logins'],
            'successful_logins': self.stats['successful_logins'],
            'failed_logins': self.stats['failed_logins'],
            'success_rate': success_rate,
            'current_status': self.stats['current_status'],
            'consecutive_successes': self.stats['consecutive_successes'],
            'max_consecutive_successes': self.stats['max_consecutive_successes'],
            'last_login': self.stats['last_login_time'].strftime('%H:%M:%S') if self.stats['last_login_time'] else 'Never'
        }

# Streamlit App
def main():
    st.set_page_config(
        page_title="Fish.audio Force Login",
        page_icon="⚡",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Check Python version and environment
    st.sidebar.write(f"🐍 Python: {sys.version.split()[0]}")
    
    if not SELENIUM_AVAILABLE:
        st.error("🚨 **Selenium Module Not Found**")
        st.markdown("Please ensure all dependencies are installed properly.")
        with st.expander("🔍 Import Errors"):
            for error in IMPORT_ERRORS:
                st.code(error)
        st.stop()
    
    st.title("⚡ Fish.audio Force Login Bot")
    st.markdown("*Forces login every 7 seconds to kick out ALL other users*")
    st.markdown("---")
    
    # Initialize session state
    if 'bot_running' not in st.session_state:
        st.session_state.bot_running = False
    if 'bot_thread' not in st.session_state:
        st.session_state.bot_thread = None
    if 'bot_instance' not in st.session_state:
        st.session_state.bot_instance = None
    if 'last_status' not in st.session_state:
        st.session_state.last_status = None
    if 'credentials_saved' not in st.session_state:
        st.session_state.credentials_saved = False
    if 'saved_email' not in st.session_state:
        st.session_state.saved_email = ""
    if 'saved_password' not in st.session_state:
        st.session_state.saved_password = ""
    if 'show_credentials_form' not in st.session_state:
        st.session_state.show_credentials_form = True
    
    # Sidebar configuration
    with st.sidebar:
        st.header("⚡ Force Login Settings")
        
        st.info(f"⚡ Mode: Force Login | 🖥️ Platform: {platform.system()}")
        
        # Credentials section
        if not st.session_state.credentials_saved or st.session_state.show_credentials_form:
            st.subheader("🔐 Account Credentials")
            st.error("🚨 **EXTREME MODE**: This will login every 7 seconds!")
            st.warning("⚠️ **WARNING**: Will kick out ANYONE using your account!")
            
            with st.form("credentials_form"):
                email = st.text_input("📧 Email", value=st.session_state.saved_email)
                password = st.text_input("🔐 Password", value="", type="password")
                
                submitted = st.form_submit_button("⚡ ACTIVATE FORCE LOGIN", type="primary")
                
                if submitted:
                    if email and password:
                        st.session_state.saved_email = email
                        st.session_state.saved_password = password
                        st.session_state.credentials_saved = True
                        st.session_state.show_credentials_form = False
                        st.success("✅ Force login mode ready!")
                        st.rerun()
                    else:
                        st.error("❌ Please enter both email and password")
        
        else:
            st.success("✅ **Force Login Ready**")
            st.info(f"📧 **Email**: {st.session_state.saved_email}")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("✏️ Edit"):
                    st.session_state.show_credentials_form = True
                    st.rerun()
            with col2:
                if st.button("🗑️ Clear"):
                    st.session_state.saved_email = ""
                    st.session_state.saved_password = ""
                    st.session_state.credentials_saved = False
                    st.session_state.show_credentials_form = True
                    st.success("Force login disabled!")
                    st.rerun()
        
        st.markdown("---")
        
        if st.session_state.credentials_saved:
            st.subheader("⚡ Login Frequency")
            
            login_interval = st.selectbox(
                "Force login every:",
                [5, 7, 10, 15, 20],
                index=1,  # Default to 7 seconds
                format_func=lambda x: f"{x} seconds"
            )
            
            st.success(f"⚡ **FORCE LOGIN EVERY {login_interval} SECONDS**")
            st.error(f"🚨 This will kick out other users every {login_interval}s!")
            
            st.markdown("---")
            
            # Control buttons
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("🚨 START FORCE LOGIN", type="primary", disabled=st.session_state.bot_running):
                    with st.spinner("Activating force login mode..."):
                        st.session_state.bot_instance = ForceLoginBot(
                            st.session_state.saved_email, 
                            st.session_state.saved_password, 
                            login_interval
                        )
                        st.session_state.bot_thread = threading.Thread(
                            target=st.session_state.bot_instance.run,
                            daemon=True
                        )
                        st.session_state.bot_thread.start()
                        st.session_state.bot_running = True
                        st.success("⚡ FORCE LOGIN ACTIVATED!")
                        time.sleep(1)
                        st.rerun()
            
            with col2:
                if st.button("⏹️ STOP FORCE LOGIN", type="secondary", disabled=not st.session_state.bot_running):
                    if st.session_state.bot_instance:
                        st.session_state.bot_instance.stop()
                    st.session_state.bot_running = False
                    st.session_state.bot_instance = None
                    st.session_state.bot_thread = None
                    st.success("⚡ Force login stopped!")
                    time.sleep(1)
                    st.rerun()
            
            if st.session_state.bot_running:
                st.error("🚨 **FORCE LOGIN ACTIVE**")
                st.warning(f"Logging in every {login_interval} seconds!")
        
        else:
            st.info("👆 Enter credentials to enable force login")
            login_interval = 7
    
    # Main dashboard
    if st.session_state.credentials_saved:
        st.header("⚡ Force Login Dashboard")
        
        if st.session_state.bot_instance:
            stats = st.session_state.bot_instance.get_stats_summary()
            
            # Key metrics
            col1, col2, col3, col4, col5 = st.columns(5)
            
            with col1:
                st.metric("🕒 Runtime", stats['runtime'])
            with col2:
                st.metric("⚡ Total Force Logins", stats['total_logins'])
            with col3:
                st.metric("✅ Successful Logins", stats['successful_logins'])
            with col4:
                st.metric("❌ Failed Logins", stats['failed_logins'])
            with col5:
                st.metric("📈 Success Rate", f"{stats['success_rate']}%")
            
            # Additional stats
            extra_col1, extra_col2, extra_col3 = st.columns(3)
            with extra_col1:
                st.metric("🔥 Current Streak", stats['consecutive_successes'])
            with extra_col2:
                st.metric("🏆 Max Streak", stats['max_consecutive_successes'])
            with extra_col3:
                st.metric("🕐 Last Login", stats['last_login'])
        
        st.markdown("---")
        
        # Real-time activity
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.subheader("🔄 Live Force Login Activity")
            
            status_placeholder = st.empty()
            progress_placeholder = st.empty()
            countdown_placeholder = st.empty()
            
            if st.session_state.bot_running and st.session_state.bot_instance:
                try:
                    while not st.session_state.bot_instance.status_queue.empty():
                        status_update = st.session_state.bot_instance.status_queue.get_nowait()
                        st.session_state.last_status = status_update
                        
                        if status_update["status"] == "success":
                            status_placeholder.success(f"🎯 {status_update['message']}")
                        elif status_update["status"] == "error":
                            status_placeholder.error(f"❌ {status_update['message']}")
                        elif status_update["status"] == "progress":
                            progress_placeholder.info(f"⏳ {status_update['message']}")
                            
                            if 'countdown' in status_update:
                                countdown = status_update['countdown']
                                progress_percent = (login_interval - countdown) / login_interval
                                countdown_placeholder.progress(progress_percent, text=f"Next force login in {countdown}s")
                        else:
                            status_placeholder.info(f"ℹ️ {status_update['message']}")
                except:
                    pass
        
        with col2:
            st.subheader("📝 Force Login Log")
            
            if log_handler.logs:
                for log in reversed(log_handler.logs[-8:]):
                    timestamp = log['time'].split(' ')[1]
                    level = log['level']
                    message = log['message']
                    
                    if len(message) > 45:
                        message = message[:42] + "..."
                    
                    if "FORCE LOGIN SUCCESS" in message or "KICKED OUT" in message:
                        st.success(f"**{timestamp}** {message}")
                    elif "FORCE LOGIN" in message:
                        st.info(f"**{timestamp}** {message}")
                    elif level == "ERROR":
                        st.error(f"**{timestamp}** {message}")
                    elif level == "INFO":
                        st.info(f"**{timestamp}** {message}")
                    else:
                        st.text(f"**{timestamp}** {message}")
            else:
                st.info("🔄 Waiting for force login activity...")
    
    else:
        # Welcome screen
        st.header("⚡ Force Login Mode")
        
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.error("""
            **⚡ EXTREME FORCE LOGIN MODE**
            
            **What this does:**
            - **Logs in every 7 seconds** (customizable)
            - **Doesn't check if anyone is online**
            - **Just forces login constantly**
            - **Kicks out EVERYONE else every 7 seconds**
            
            **How it works:**
            1. Goes to Fish.audio login page
            2. Enters your credentials and logs in
            3. Waits 7 seconds
            4. Repeats forever in a loop
            
            **Result:**
            - **No one else can use your account for more than 7 seconds**
            - **Extremely effective** at maintaining control
            - **Simple and foolproof** approach
            """)
            
            st.warning("🚨 **Warning**: This is very aggressive and will constantly kick out other users!")
    
    # Auto-refresh
    if st.session_state.bot_running:
        time.sleep(2)
        st.rerun()
    
    st.markdown("---")
    st.markdown(
        """
        <div style='text-align: center; color: gray; font-size: 0.8em;'>
            <p>⚡ Force Login Mode | 🚨 Maximum Aggression</p>
        </div>
        """,
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()
