import os
import time
import json
import logging
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from eth_account import Account
import secrets

class GitHubActionsMeritBot:
    def __init__(self):
        self.setup_logging()
        self.driver = None
        self.wait = None
        self.is_github_actions = os.getenv('GITHUB_ACTIONS') == 'true'
        
        # Setup wallet dari private key
        self.setup_wallet()
        
    def setup_logging(self):
        """Setup logging untuk GitHub Actions environment"""
        log_level = logging.DEBUG if self.is_github_actions else logging.INFO
        
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('merit_bot.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
        if self.is_github_actions:
            self.logger.info("🚀 Running in GitHub Actions environment")

    def setup_wallet(self):
        """Setup wallet dari private key environment variable"""
        try:
            private_key = os.getenv('PRIVATE_KEY')
            
            if not private_key:
                self.logger.error("❌ PRIVATE_KEY not found in environment variables")
                raise ValueError("PRIVATE_KEY is required")
            
            # Remove '0x' prefix jika ada
            if private_key.startswith('0x'):
                private_key = private_key[2:]
            
            # Validate private key format
            if len(private_key) != 64:
                raise ValueError("Invalid private key length")
            
            # Create account dari private key
            self.account = Account.from_key(private_key)
            self.wallet_address = self.account.address
            
            # Log wallet address (untuk debugging, tapi jangan log private key)
            self.logger.info(f"✅ Wallet initialized: {self.wallet_address}")
            self.logger.info(f"🔑 Wallet address: {self.wallet_address[:6]}...{self.wallet_address[-4:]}")
            
        except Exception as e:
            self.logger.error(f"❌ Failed to setup wallet: {str(e)}")
            raise

    def setup_driver(self):
        """Setup Chrome WebDriver untuk GitHub Actions"""
        chrome_options = Options()
        
        # Konfigurasi khusus untuk GitHub Actions
        if self.is_github_actions:
            chrome_options.add_argument("--headless=new")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--disable-web-security")
            chrome_options.add_argument("--allow-running-insecure-content")
            chrome_options.add_argument("--disable-extensions")
            chrome_options.add_argument("--disable-plugins")
        
        # Pengaturan umum
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        # Enable MetaMask-like features
        chrome_options.add_argument("--enable-cookies")
        chrome_options.add_argument("--enable-local-storage")
        
        try:
            # Di GitHub Actions, Chrome sudah terinstall
            if self.is_github_actions:
                service = Service('/usr/bin/chromedriver')
            else:
                from webdriver_manager.chrome import ChromeDriverManager
                service = Service(ChromeDriverManager().install())
                
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.wait = WebDriverWait(self.driver, 30)
            self.logger.info("✅ WebDriver initialized successfully")
            
        except Exception as e:
            self.logger.error(f"❌ Failed to initialize WebDriver: {str(e)}")
            raise

    def load_claim_history(self):
        """Load claim history dari file"""
        try:
            if os.path.exists('claim_history.json'):
                with open('claim_history.json', 'r') as f:
                    history = json.load(f)
                    self.logger.info(f"📊 Loaded claim history: {len(history)} entries")
                    return history
        except Exception as e:
            self.logger.warning(f"⚠️ Could not load claim history: {str(e)}")
        
        return {}

    def save_claim_history(self, success=False, error_msg=None, claim_type="wallet_connected"):
        """Save claim history untuk tracking"""
        today = datetime.now().strftime('%Y-%m-%d')
        history = self.load_claim_history()
        
        history[today] = {
            'timestamp': datetime.now().isoformat(),
            'success': success,
            'claim_type': claim_type,
            'wallet_address': f"{self.wallet_address[:6]}...{self.wallet_address[-4:]}",
            'github_run_id': os.getenv('GITHUB_RUN_ID', 'local'),
            'error': error_msg if error_msg else None
        }
        
        try:
            with open('claim_history.json', 'w') as f:
                json.dump(history, f, indent=2)
            self.logger.info(f"💾 Saved claim history for {today}")
        except Exception as e:
            self.logger.error(f"❌ Failed to save history: {str(e)}")

    def check_already_claimed_today(self):
        """Check apakah sudah claim hari ini"""
        today = datetime.now().strftime('%Y-%m-%d')
        history = self.load_claim_history()
        
        if today in history and history[today].get('success'):
            self.logger.info("✅ Already claimed merits today - skipping")
            return True
        return False

    def navigate_to_blockscout_merits(self):
        """Navigate ke halaman merits Blockscout"""
        try:
            # Direct ke halaman merits dengan wallet address
            merits_url = f"https://eth.blockscout.com/address/{self.wallet_address}/merits"
            self.logger.info(f"🌐 Navigating to: {merits_url}")
            
            self.driver.get(merits_url)
            time.sleep(5)  # Wait for page load
            
            # Verify page loaded
            self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            
            # Check if page loaded successfully
            if "404" in self.driver.page_source or "Not Found" in self.driver.page_source:
                self.logger.warning("⚠️ Merits page not found, trying alternative URLs")
                return self.try_alternative_merit_urls()
            
            self.logger.info("✅ Successfully loaded Blockscout merits page")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Failed to navigate to merits page: {str(e)}")
            return self.try_alternative_merit_urls()

    def try_alternative_merit_urls(self):
        """Try alternative merit URLs"""
        alternative_urls = [
            f"https://eth.blockscout.com/address/{self.wallet_address}",
            "https://eth.blockscout.com/account/merits",
            "https://eth.blockscout.com/merits",
            "https://eth.blockscout.com/rewards"
        ]
        
        for url in alternative_urls:
            try:
                self.logger.info(f"🔄 Trying alternative URL: {url}")
                self.driver.get(url)
                time.sleep(5)
                
                if "404" not in self.driver.page_source and "Not Found" not in self.driver.page_source:
                    self.logger.info(f"✅ Successfully loaded: {url}")
                    return True
                    
            except Exception as e:
                self.logger.warning(f"⚠️ Failed to load {url}: {str(e)}")
                continue
        
        return False

    def simulate_wallet_connection(self):
        """Simulate wallet connection dengan inject wallet address"""
        try:
            # Inject wallet address ke localStorage
            wallet_data = {
                'address': self.wallet_address,
                'connected': True,
                'provider': 'injected'
            }
            
            # Set localStorage
            self.driver.execute_script(f"""
                localStorage.setItem('wallet_address', '{self.wallet_address}');
                localStorage.setItem('wallet_connected', 'true');
                localStorage.setItem('wallet_data', '{json.dumps(wallet_data)}');
            """)
            
            # Set sessionStorage juga
            self.driver.execute_script(f"""
                sessionStorage.setItem('wallet_address', '{self.wallet_address}');
                sessionStorage.setItem('wallet_connected', 'true');
            """)
            
            self.logger.info("🔗 Simulated wallet connection in browser storage")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Failed to simulate wallet connection: {str(e)}")
            return False

    def look_for_connect_wallet_button(self):
        """Look for dan click connect wallet button"""
        connect_selectors = [
            "//button[contains(text(), 'Connect')]",
            "//button[contains(text(), 'Sign in')]",
            "//button[contains(text(), 'Connect Wallet')]",
            "//div[contains(@class, 'connect')]//button",
            ".connect-wallet-btn",
            ".connect-button",
            "[data-testid='connect-wallet']",
            "#connect-wallet"
        ]
        
        for selector in connect_selectors:
            try:
                if selector.startswith("//"):
                    elements = self.driver.find_elements(By.XPATH, selector)
                else:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                
                for element in elements:
                    if element.is_displayed() and element.is_enabled():
                        # Scroll to element
                        self.driver.execute_script("arguments[0].scrollIntoView(true);", element)
                        time.sleep(2)
                        
                        # Click connect button
                        element.click()
                        self.logger.info(f"🔗 Clicked connect button: {element.text}")
                        time.sleep(3)
                        
                        # After clicking, simulate wallet connection
                        self.simulate_wallet_connection()
                        return True
                        
            except Exception as e:
                continue
        
        self.logger.info("ℹ️ No connect wallet button found")
        return False

    def look_for_claim_buttons(self):
        """Look for dan click claim buttons"""
        claim_selectors = [
            "//button[contains(text(), 'Claim')]",
            "//button[contains(text(), 'Collect')]",
            "//button[contains(text(), 'Get Reward')]",
            "//div[contains(@class, 'claim')]//button",
            ".claim-button",
            ".claim-btn",
            "[data-testid='claim-button']",
            "#claim-btn"
        ]
        
        claimed_something = False
        
        for selector in claim_selectors:
            try:
                if selector.startswith("//"):
                    elements = self.driver.find_elements(By.XPATH, selector)
                else:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                
                for element in elements:
                    if element.is_displayed() and element.is_enabled():
                        # Scroll to element
                        self.driver.execute_script("arguments[0].scrollIntoView(true);", element)
                        time.sleep(2)
                        
                        # Click claim button
                        element.click()
                        self.logger.info(f"🎯 Clicked claim button: {element.text}")
                        claimed_something = True
                        time.sleep(5)  # Wait for claim process
                        
                        # Check for success
                        if self.check_success_indicators():
                            return True
                        
            except Exception as e:
                continue
        
        return claimed_something

    def check_success_indicators(self):
        """Check for success indicators di page"""
        try:
            success_indicators = [
                "success", "claimed", "completed", "earned", 
                "congratulations", "well done", "reward", "merit"
            ]
            
            page_text = self.driver.page_source.lower()
            
            for indicator in success_indicators:
                if indicator in page_text:
                    self.logger.info(f"✅ Found success indicator: {indicator}")
                    return True
            
            # Check for visual success elements
            success_selectors = [
                ".success", ".completed", ".claimed", ".earned",
                "[class*='success']", "[class*='complete']", "[class*='claim']"
            ]
            
            for selector in success_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements and any(elem.is_displayed() for elem in elements):
                        self.logger.info(f"✅ Found success element: {selector}")
                        return True
                except:
                    continue
                    
            return False
            
        except Exception as e:
            self.logger.error(f"❌ Failed to check success indicators: {str(e)}")
            return False

    def take_screenshot(self, filename="screenshot.png"):
        """Take screenshot untuk debugging"""
        try:
            self.driver.save_screenshot(filename)
            self.logger.info(f"📸 Screenshot saved: {filename}")
        except Exception as e:
            self.logger.error(f"❌ Failed to take screenshot: {str(e)}")

    def run_bot(self):
        """Main bot execution function"""
        start_time = datetime.now()
        self.logger.info(f"🤖 Starting Blockscout Merit Bot at {start_time}")
        self.logger.info(f"💳 Using wallet: {self.wallet_address[:6]}...{self.wallet_address[-4:]}")
        
        # Check if already claimed today
        if self.check_already_claimed_today():
            return
        
        success = False
        error_msg = None
        claim_type = "wallet_connected"
        
        try:
            # Setup WebDriver
            self.setup_driver()
            
            # Navigate to Blockscout merits page
            if not self.navigate_to_blockscout_merits():
                raise Exception("Failed to navigate to Blockscout merits page")
            
            # Take initial screenshot
            self.take_screenshot("initial_page.png")
            
            # Look for connect wallet button first
            self.look_for_connect_wallet_button()
            
            # Wait a bit after connection attempt
            time.sleep(5)
            
            # Take screenshot after connection attempt
            self.take_screenshot("after_connection.png")
            
            # Look for claim buttons
            if self.look_for_claim_buttons():
                success = True
                self.logger.info("🎉 Merit claim process completed!")
            else:
                self.logger.info("ℹ️ No claimable merits found - this might be normal")
                success = True  # Consider it success even if no claimable merits
                claim_type = "no_claimable_merits"
                
        except Exception as e:
            error_msg = str(e)
            self.logger.error(f"❌ Bot execution failed: {error_msg}")
            
        finally:
            # Take final screenshot
            if self.driver:
                self.take_screenshot("final_screenshot.png")
            
            # Cleanup
            if self.driver:
                self.driver.quit()
                self.logger.info("🔧 WebDriver closed")
            
            # Save history
            self.save_claim_history(success, error_msg, claim_type)
            
            # Log execution time
            end_time = datetime.now()
            duration = end_time - start_time
            self.logger.info(f"⏱️ Bot execution completed in {duration.total_seconds():.2f} seconds")

def main():
    """Entry point untuk GitHub Actions"""
    try:
        bot = GitHubActionsMeritBot()
        bot.run_bot()
    except Exception as e:
        logging.error(f"❌ Critical error: {str(e)}")
        exit(1)

if __name__ == "__main__":
    main()
