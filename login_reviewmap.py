# login_reviewmap.py
import os
import time
import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from pyvirtualdisplay import Display


# ==================== CONFIG ====================
USERNAME = os.getenv('REVIEWMAP_USERNAME')
PASSWORD = os.getenv('REVIEWMAP_PASSWORD')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

LOGIN_URL = "https://reviewmap.vn/login"
HOME_URL = "https://reviewmap.vn/"
MAX_RETRIES = 3
# ===============================================


def send_telegram(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Thiếu config Telegram")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}, timeout=10)
    except Exception as e:
        print(f"Lỗi gửi Telegram: {e}")


def create_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => false});")
    return driver


def login_attempt(driver, attempt):
    print(f"Đang đăng nhập lần {attempt}...")
    send_telegram(f"Đang thử đăng nhập ReviewMap - lần {attempt}/{MAX_RETRIES}")

    try:
        driver.get(LOGIN_URL)
        wait = WebDriverWait(driver, 20)

        # Nhập username + password
        wait.until(EC.presence_of_element_located((By.NAME, "username"))).send_keys(USERNAME)
        driver.find_element(By.NAME, "password").send_keys(PASSWORD)

        # Click nút đăng nhập
        login_btn = driver.find_element(By.XPATH, "//button[@type='submit' and contains(., 'Đăng Nhập')]")
        driver.execute_script("arguments[0].click();", login_btn)

        time.sleep(6)

        # Kiểm tra thành công
        if driver.current_url.startswith(HOME_URL):
            try:
                wait.until(EC.presence_of_element_located((By.XPATH, "//a[contains(., 'Nhận Nhiệm Vụ')]")))
                send_telegram("ĐĂNG NHẬP REVIEWMAP THÀNH CÔNG!\n"
                              f"URL: {driver.current_url}\n"
                              f"Time: {time.strftime('%H:%M %d/%m/%Y')}")
                print("Đăng nhập thành công!")
                return True
            except:
                pass

        if "login" in driver.current_url.lower():
            send_telegram("Đăng nhập thất bại - vẫn ở trang login")
        else:
            send_telegram(f"Chuyển hướng lạ: {driver.current_url}")

    except Exception as e:
        send_telegram(f"Lỗi lần {attempt}: {str(e)[:200]}")
        print(f"Lỗi: {e}")

    return False


def main():
    if not USERNAME or not PASSWORD:
        send_telegram("Thiếu REVIEWMAP_USERNAME hoặc PASSWORD trong Secrets!")
        return

    # Bật màn hình ảo
    display = Display(visible=0, size=(1920, 1080))
    display.start()

    success = False
    driver = None

    for i in range(1, MAX_RETRIES + 1):
        try:
            driver = create_driver()
            if login_attempt(driver, i):
                success = True
                break
        except Exception as e:
            print(f"Lỗi khởi tạo driver lần {i}: {e}")
        finally:
            if driver:
                driver.quit()
        if i < MAX_RETRIES:
            time.sleep(15)

    display.stop()

    if not success:
        send_telegram("ĐĂNG NHẬP THẤT BẠI SAU 3 LẦN THỬ!\n"
                      "Kiểm tra tài khoản/pass hoặc web đang chặn bot.")


if __name__ == "__main__":
    main()
