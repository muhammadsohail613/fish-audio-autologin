#!/usr/bin/env python3
"""
Fish.audio Auto-Login Streamlit Cloud App
Web-based control panel for the Fish.audio auto-login system
Enhanced Chrome compatibility for Streamlit Cloud deployment
"""

import streamlit as st
import time
import os
import sys
import requests
import zipfile
import stat
import threading
import queue
import logging
from datetime import datetime
import subprocess
import platform

# Import selenium components with better error handling
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

# Setup logging to capture in Streamlit
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
        # Keep only last 50 logs
        if len(self.logs) > 50:
            self.logs.pop(0)

# Initialize logging
log_handler = StreamlitLogHandler()
logging.basicConfig(level=logging.INFO, handlers=[log_handler])
logger = logging.getLogger(__name__)

class FishAudioLoginBot:
    """Main bot class for Fish.audio login automation - Cloud Compatible"""
    
    def __init__(self, email, password, reload_interval):
        self.email = email
        self.password = password
        self.reload_interval = reload_interval
        self.driver = None
        self.wait = None
        self.running = False
        self.status_queue = queue.Queue()
    
    def setup_driver(self):
        """Initialize Chrome WebDriver for cloud deployment"""
        try:
            if not SELENIUM_AVAILABLE:
                logger.error("Selenium not available. Please install selenium and webdriver-manager.")
                return False
            
            # Chrome options for cloud deployment
            chrome_options = Options()
            
            # Essential options for cloud/headless environments
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--disable-extensions")
            chrome_options.add_argument("--disable-plugins")
            chrome_options.add_argument("--disable-background-timer-throttling")
            chrome_options.add_argument("--disable-backgrounding-occluded-windows")
            chrome_options.add_argument("--disable-renderer-backgrounding")
            chrome_options.add_argument("--disable-features=TranslateUI")
            chrome_options.add_argument("--disable-ipc-flooding-protection")
            chrome_options.add_argument("--window-size=1920,1080")
            chrome_options.add_argument("--remote-debugging-port=9222")
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            # For Streamlit Cloud - specify chromium binary path
            chromium_paths = [
                "/usr/bin/chromium",
                "/usr/bin/chromium-browser", 
                "/usr/bin/google-chrome",
                "/usr/bin/google-chrome-stable"
            ]
            
            for path in chromium_paths:
                if os.path.exists(path):
                    chrome_options.binary_location = path
                    logger.info(f"Found browser at: {path}")
                    break
            
            # User agent to avoid detection
            chrome_options.add_argument("--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
            
            # Try different approaches to setup ChromeDriver
            driver_setup_methods = [
                # Method 1: Use webdriver-manager (most reliable)
                lambda: webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options),
                
                # Method 2: Use undetected-chromedriver
                lambda: self._setup_undetected_chrome(),
                
                # Method 3: Use system chromedriver paths
                lambda: self._setup_system_chrome(chrome_options),
                
                # Method 4: Default Chrome setup
                lambda: webdriver.Chrome(options=chrome_options)
            ]
            
            driver_created = False
            for i, method in enumerate(driver_setup_methods):
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
            self.driver.execute_cdp_cmd('Network.setUserAgentOverride', {
                "userAgent": 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            })
            
            self.wait = WebDriverWait(self.driver, 15)  # Increased timeout for cloud
            logger.info("ChromeDriver initialized successfully for cloud deployment")
            return True
            
        except Exception as e:
            logger.error(f"Error setting up driver: {e}")
            return False
    
    def _setup_system_chrome(self, chrome_options):
        """Try different system chromedriver paths"""
        driver_paths = [
            "/usr/bin/chromedriver",
            "/usr/bin/chromium-driver", 
            "/usr/local/bin/chromedriver"
        ]
        
        for path in driver_paths:
            if os.path.exists(path):
                logger.info(f"Found chromedriver at: {path}")
                return webdriver.Chrome(executable_path=path, options=chrome_options)
        
        raise Exception("No system chromedriver found")
    
    def _setup_undetected_chrome(self):
        """Setup undetected Chrome driver for better cloud compatibility"""
        try:
            options = uc.ChromeOptions()
            options.add_argument("--headless")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")
            options.add_argument("--window-size=1920,1080")
            
            # Try to use system chromium if available
            chromium_paths = [
                "/usr/bin/chromium",
                "/usr/bin/chromium-browser", 
                "/usr/bin/google-chrome"
            ]
            
            for path in chromium_paths:
                if os.path.exists(path):
                    options.binary_location = path
                    break
            
            driver = uc.Chrome(options=options, version_main=None)
            return driver
            
        except Exception as e:
            logger.error(f"Undetected Chrome setup failed: {e}")
            raise e
    
    def is_logged_in(self):
        """Check if user is currently logged in"""
        try:
            # Check current URL first
            current_url = self.driver.current_url
            if "auth" in current_url or "login" in current_url:
                logger.info("User appears to be on login page")
                return False
            
            # Check for login form elements
            login_indicators = [
                "//input[@type='email']",
                "//input[@type='password']",
                "//button[contains(text(), 'Sign in')]",
                "//button[contains(text(), 'Login')]"
            ]
            
            for indicator in login_indicators:
                try:
                    self.driver.find_element(By.XPATH, indicator)
                    logger.info("Login form detected - user appears to be logged out")
                    return False
                except NoSuchElementException:
                    continue
            
            logger.info("No login form found - user appears to be logged in")
            return True
            
        except Exception as e:
            logger.error(f"Error checking login status: {e}")
            return False
    
    def login(self):
        """Perform login process"""
        try:
            logger.info("Attempting to login...")
            
            # Navigate to login page
            self.driver.get(LOGIN_URL)
            time.sleep(5)  # Longer wait for cloud environments
            
            # Wait for page to load completely
            self.wait.until(lambda driver: driver.execute_script("return document.readyState") == "complete")
            
            try:
                email_field = self.wait.until(EC.presence_of_element_located((By.XPATH, '/html/body/div/div[3]/div/div[3]/form/div/div[1]/input')))
                email_field.clear()
                time.sleep(1)
                email_field.send_keys(self.email)
                logger.info("Email entered successfully")
            except TimeoutException:
                logger.error("Could not find email field with provided XPath")
                return False
            
            try:
                password_field = self.wait.until(EC.presence_of_element_located((By.XPATH, '/html/body/div/div[3]/div/div[3]/form/div/div[2]/input')))
                password_field.clear()
                time.sleep(1)
                password_field.send_keys(self.password)
                logger.info("Password entered successfully")
            except TimeoutException:
                logger.error("Could not find password field with provided XPath")
                return False
            
            try:
                login_button = self.wait.until(EC.element_to_be_clickable((By.XPATH, '/html/body/div/div[3]/div/div[3]/form/div/button')))
                login_button.click()
                logger.info("Login button clicked successfully")
            except TimeoutException:
                logger.error("Could not find login button with provided XPath")
                return False
            
            # Wait for login to complete
            time.sleep(8)  # Longer wait for cloud
            
            # Check if login was successful
            current_url = self.driver.current_url
            if LOGIN_URL not in current_url:
                logger.info("Login successful - redirected from login page!")
                return True
            elif not self.is_logged_in():
                logger.info("Login successful - no login form visible!")
                return True
            else:
                logger.error("Login appears to have failed - still on login page")
                return False
                
        except Exception as e:
            logger.error(f"Error during login: {e}")
            return False
    
    def run(self):
        """Main execution loop"""
        if not self.setup_driver():
            logger.error("Failed to setup driver")
            self.status_queue.put({"status": "error", "message": "Failed to setup driver"})
            return
        
        self.running = True
        try:
            while self.running:
                try:
                    # Navigate to the page
                    self.driver.get(LOGIN_URL)
                    time.sleep(5)
                    
                    # Check if logged in
                    if not self.is_logged_in():
                        logger.info("User is logged out, attempting login...")
                        if self.login():
                            self.status_queue.put({"status": "success", "message": "Login successful"})
                        else:
                            self.status_queue.put({"status": "error", "message": "Login failed"})
                    else:
                        logger.info("User is logged in")
                        self.status_queue.put({"status": "success", "message": "User is logged in"})
                    
                    # Wait for the specified interval
                    for i in range(self.reload_interval):
                        if not self.running:
                            break
                        time.sleep(1)
                        # Update progress in queue
                        remaining = self.reload_interval - i
                        self.status_queue.put({"status": "progress", "message": f"Next check in {remaining}s"})
                    
                except Exception as e:
                    logger.error(f"Error in main loop: {e}")
                    self.status_queue.put({"status": "error", "message": f"Error: {e}"})
                    time.sleep(self.reload_interval)
                    
        finally:
            if self.driver:
                self.driver.quit()
                logger.info("Driver closed")
                self.status_queue.put({"status": "info", "message": "Bot stopped"})
    
    def stop(self):
        """Stop the bot"""
        self.running = False

# Streamlit App
def main():
    # MUST be the first Streamlit command
    st.set_page_config(
        page_title="Fish.audio Auto-Login",
        page_icon="🐠",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Check Python version and environment (after page config)
    st.sidebar.write(f"🐍 Python: {sys.version.split()[0]}")
    
    # Check if selenium is available
    if not SELENIUM_AVAILABLE:
        st.error("🚨 **Selenium Module Not Found**")
        st.markdown("""
        **Possible causes:**
        1. **Installation in progress** - Streamlit Cloud may still be installing packages
        2. **Missing requirements.txt** - Make sure it's in your repository root
        3. **Package installation failed** - Check deployment logs
        """)
        
        # Show detailed import errors
        with st.expander("🔍 Detailed Import Errors"):
            for error in IMPORT_ERRORS:
                st.code(error)
        
        # Show environment info
        st.info(f"**Environment**: Python {sys.version.split()[0]} on {platform.system()}")
        
        # Show required files
        with st.expander("📋 Required Repository Files"):
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**requirements.txt**")
                st.code("""streamlit>=1.28.0
selenium>=4.15.0
requests>=2.31.0
webdriver-manager>=4.0.1
undetected-chromedriver>=3.5.4""")
            
            with col2:
                st.markdown("**packages.txt**")
                st.code("""chromium
chromium-driver
xvfb""")
        
        # Troubleshooting steps
        st.markdown("### 🛠️ Troubleshooting Steps:")
        st.markdown("""
        1. **Wait 5 minutes** - Initial deployment can take time
        2. **Check files** - Ensure `requirements.txt` and `packages.txt` are in repo root
        3. **Reboot app** - Go to "Manage App" → "Reboot"
        4. **Check logs** - Look for installation errors in the terminal
        5. **Repository structure**:
           ```
           your-repo/
           ├── app.py
           ├── requirements.txt
           └── packages.txt
           ```
        """)
        
        # Add refresh button
        if st.button("🔄 Refresh Page"):
            st.rerun()
        
        st.stop()
    
    st.title("🐠 Fish.audio Auto-Login System")
    st.markdown("*Cloud-Compatible Version*")
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
    
    # Sidebar for configuration
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        # Environment info
        st.info(f"🖥️ Platform: {platform.system()}")
        
    # Sidebar for configuration
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        # Environment info
        st.info(f"🖥️ Platform: {platform.system()}")
        
        # Credentials section
        if not st.session_state.credentials_saved or st.session_state.show_credentials_form:
            st.subheader("🔐 Login Credentials")
            st.info("💡 Enter your credentials once - they'll be remembered for this session!")
            
            with st.form("credentials_form"):
                email = st.text_input("📧 Email", value=st.session_state.saved_email, 
                                    placeholder="your.email@example.com")
                password = st.text_input("🔐 Password", value="", type="password",
                                       placeholder="Enter your Fish.audio password")
                
                submitted = st.form_submit_button("💾 Save Credentials", type="primary")
                
                if submitted:
                    if email and password:
                        st.session_state.saved_email = email
                        st.session_state.saved_password = password
                        st.session_state.credentials_saved = True
                        st.session_state.show_credentials_form = False
                        st.success("✅ Credentials saved!")
                        st.rerun()
                    else:
                        st.error("❌ Please enter both email and password")
        
        else:
            # Show saved credentials info
            st.success("✅ **Credentials Saved**")
            st.info(f"📧 **Email**: {st.session_state.saved_email}")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("✏️ Edit", help="Change login credentials"):
                    st.session_state.show_credentials_form = True
                    st.rerun()
            with col2:
                if st.button("🗑️ Clear", help="Clear saved credentials"):
                    st.session_state.saved_email = ""
                    st.session_state.saved_password = ""
                    st.session_state.credentials_saved = False
                    st.session_state.show_credentials_form = True
                    st.success("Credentials cleared!")
                    st.rerun()
        
        st.markdown("---")
        
        # Timer settings (only show if credentials are saved)
        if st.session_state.credentials_saved:
            st.subheader("⏱️ Timer Settings")
            
            timer_option = st.selectbox(
                "Select reload interval:",
                ["30 seconds", "1 minute", "2 minutes", "5 minutes", "10 minutes", "Custom"]
            )
            
            if timer_option == "Custom":
                reload_interval = st.number_input(
                    "Custom interval (seconds):",
                    min_value=10,
                    max_value=3600,
                    value=30,
                    step=10
                )
            else:
                time_mapping = {
                    "30 seconds": 30,
                    "1 minute": 60,
                    "2 minutes": 120,
                    "5 minutes": 300,
                    "10 minutes": 600
                }
                reload_interval = time_mapping[timer_option]
            
            st.success(f"⏰ Reload every **{reload_interval}** seconds")
            
            st.markdown("---")
            
            # Control buttons
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("🚀 Start Bot", type="primary", disabled=st.session_state.bot_running):
                    with st.spinner("Starting bot..."):
                        # Use saved credentials
                        st.session_state.bot_instance = FishAudioLoginBot(
                            st.session_state.saved_email, 
                            st.session_state.saved_password, 
                            reload_interval
                        )
                        st.session_state.bot_thread = threading.Thread(
                            target=st.session_state.bot_instance.run,
                            daemon=True
                        )
                        st.session_state.bot_thread.start()
                        st.session_state.bot_running = True
                        st.success("✅ Bot started!")
                        time.sleep(1)
                        st.rerun()
            
            with col2:
                if st.button("⏹️ Stop Bot", type="secondary", disabled=not st.session_state.bot_running):
                    if st.session_state.bot_instance:
                        st.session_state.bot_instance.stop()
                    st.session_state.bot_running = False
                    st.session_state.bot_instance = None
                    st.session_state.bot_thread = None
                    st.success("✅ Bot stopped!")
                    time.sleep(1)
                    st.rerun()
            
            # Warning for cloud deployment
            if st.session_state.bot_running:
                st.warning("⚠️ **Cloud Note**: Bot runs in headless mode on Streamlit Cloud. Browser won't be visible but automation still works!")
        
        else:
            st.info("👆 Please enter your login credentials first to continue")
            # Set default values to prevent errors
            reload_interval = 30
    
    # Main content area
    if st.session_state.credentials_saved:
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.header("📊 Status Dashboard")
            
            # Status indicators
            status_col1, status_col2, status_col3 = st.columns(3)
            
            with status_col1:
                if st.session_state.bot_running:
                    st.success("🟢 **Status**: Running")
                else:
                    st.error("🔴 **Status**: Stopped")
            
            with status_col2:
                st.info(f"⏱️ **Interval**: {reload_interval}s")
            
            with status_col3:
                st.info(f"🌐 **Target**: fish.audio")
            
            # Real-time status updates
            status_placeholder = st.empty()
            progress_placeholder = st.empty()
            
            if st.session_state.bot_running and st.session_state.bot_instance:
                # Check for status updates
                try:
                    while not st.session_state.bot_instance.status_queue.empty():
                        status_update = st.session_state.bot_instance.status_queue.get_nowait()
                        st.session_state.last_status = status_update
                        
                        if status_update["status"] == "success":
                            status_placeholder.success(f"✅ {status_update['message']}")
                        elif status_update["status"] == "error":
                            status_placeholder.error(f"❌ {status_update['message']}")
                        elif status_update["status"] == "progress":
                            progress_placeholder.info(f"⏳ {status_update['message']}")
                        else:
                            status_placeholder.info(f"ℹ️ {status_update['message']}")
                except:
                    pass
            
            # Display last status if available
            if st.session_state.last_status and not st.session_state.bot_running:
                if st.session_state.last_status["status"] == "success":
                    status_placeholder.success(f"✅ Last: {st.session_state.last_status['message']}")
                elif st.session_state.last_status["status"] == "error":
                    status_placeholder.error(f"❌ Last: {st.session_state.last_status['message']}")
        
        with col2:
            st.header("📝 Activity Log")
            
            # Display logs
            log_container = st.container()
            
            with log_container:
                if log_handler.logs:
                    # Show last 8 logs
                    for log in reversed(log_handler.logs[-8:]):
                        timestamp = log['time'].split(' ')[1]  # Show only time
                        level = log['level']
                        message = log['message']
                        
                        # Truncate long messages
                        if len(message) > 60:
                            message = message[:57] + "..."
                        
                        if level == "ERROR":
                            st.error(f"**{timestamp}** {message}")
                        elif level == "WARNING":
                            st.warning(f"**{timestamp}** {message}")
                        elif level == "INFO":
                            st.info(f"**{timestamp}** {message}")
                        else:
                            st.text(f"**{timestamp}** {message}")
                else:
                    st.info("🔄 Waiting for activity...")
    
    else:
        # Welcome screen when no credentials are saved
        st.header("🔐 Welcome to Fish.audio Auto-Login")
        
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.info("""
            **👋 Getting Started:**
            
            1. **Enter your Fish.audio credentials** in the sidebar
            2. **Choose your preferred timer interval**
            3. **Click "Start Bot"** to begin auto-login
            
            Your credentials will be remembered for this session only and are never stored permanently.
            """)
            
            st.success("🛡️ **Privacy**: Your login information stays secure in your browser session")
        
        # Feature highlights
        st.markdown("---")
        st.subheader("✨ Features")
        
        feat_col1, feat_col2, feat_col3 = st.columns(3)
        
        with feat_col1:
            st.info("""
            **🤖 Auto-Login**
            
            Automatically detects when you're logged out and logs you back in
            """)
        
        with feat_col2:
            st.info("""
            **⏱️ Customizable Timer**
            
            Set your preferred check interval from 30 seconds to 10 minutes
            """)
        
        with feat_col3:
            st.info("""
            **📊 Real-time Monitoring**
            
            Live status updates and activity logging
            """)
    
    # Auto-refresh for real-time updates
    if st.session_state.bot_running:
        time.sleep(3)
        st.rerun()
    
    # Footer
    st.markdown("---")
    st.markdown(
        """
        <div style='text-align: center; color: gray; font-size: 0.8em;'>
            <p>🐠 Fish.audio Auto-Login System | ☁️ Streamlit Cloud Compatible</p>
            <p>⚡ Powered by Selenium WebDriver</p>
        </div>
        """,
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()
