import os
import time
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# ==================== CONFIG ====================
# GitHub Secrets
USERNAME = os.getenv('REVIEWMAP_USERNAME')
PASSWORD = os.getenv('REVIEWMAP_PASSWORD')

# Telegram Bot (bạn đã có bot rồi)
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

LOGIN_URL = "https://reviewmap.vn/login"
HOME_URL = "https://reviewmap.vn/"

MAX_RETRIES = 3
# ===============================================

def send_telegram_message(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Thiếu config Telegram → bỏ qua gửi tin")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    try:
        requests.post(url, data=payload, timeout=10)
    except Exception as e:
        print(f"Lỗi gửi Telegram: {e}")

def init_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")

    driver = webdriver.Chrome(options=chrome_options)
    driver.set_page_load_timeout(30)
    return driver

def login_reviewmap(driver, attempt=1):
    print(f"Đang thử đăng nhập lần {attempt}...")
    send_telegram_message(f"🔄 Đang đăng nhập ReviewMap - lần {attempt}/{MAX_RETRIES}")

    try:
        driver.get(LOGIN_URL)
        wait = WebDriverWait(driver, 20)

        # Nhập username
        username_field = wait.until(EC.presence_of_element_located((By.NAME, "username")))
        username_field.clear()
        username_field.send_keys(USERNAME)

        # Nhập password
        password_field = driver.find_element(By.NAME, "password")
        password_field.clear()
        password_field.send_keys(PASSWORD)

        # Click nút Đăng Nhập
        login_button = driver.find_element(By.XPATH, "//button[@type='submit' and contains(., 'Đăng Nhập')]")
        driver.execute_script("arguments[0].scrollIntoView();", login_button)
        time.sleep(1)
        login_button.click()

        # Đợi chuyển hướng
        time.sleep(5)

        # Kiểm tra thành công
        if driver.current_url.startswith(HOME_URL):
            # Kiểm tra thêm menu nhiệm vụ có hiện không
            try:
                wait.until(EC.presence_of_element_located((By.XPATH, "//a[contains(@href, '/account/profile') and contains(., 'Tài Khoản')]")))
                print("Đăng nhập thành công!")
                send_telegram_message("✅ <b>Đăng nhập ReviewMap thành công!</b>\n"
                                   f"URL: {driver.current_url}\n"
                                   f"Thời gian: {time.strftime('%H:%M:%S %d/%m/%Y')}")
                return True
            except TimeoutException:
                pass

        # Nếu vẫn ở trang login hoặc lỗi
        if "login" in driver.current_url.lower():
            print("Vẫn ở trang login → sai tài khoản/mật khẩu hoặc bị chặn")
            send_telegram_message("❌ Đăng nhập thất bại (vẫn ở trang login)")

    except Exception as e:
        print(f"Lỗi trong quá trình đăng nhập: {e}")
        send_telegram_message(f"⚠️ Lỗi Selenium lần {attempt}: {str(e)[:200]}")

    return False

def main():
    if not USERNAME or not PASSWORD:
        print("Thiếu REVIEWMAP_USERNAME hoặc REVIEWMAP_PASSWORD trong Secrets!")
        send_telegram_message("❌ Thiếu username/password trong GitHub Secrets!")
        return

    driver = None
    success = False

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            driver = init_driver()
            if login_reviewmap(driver, attempt):
                success = True
                break
            else:
                if attempt < MAX_RETRIES:
                    print(f"Thử lại sau 10 giây...")
                    time.sleep(10)
        except Exception as e:
            print(f"Lỗi khởi tạo driver lần {attempt}: {e}")
        finally:
            if driver:
                driver.quit()

        if attempt < MAX_RETRIES:
            time.sleep(15)  # Đợi lâu hơn trước khi thử lại

    if not success:
        send_telegram_message("🚨 <b>Đăng nhập ReviewMap thất bại sau 3 lần thử!</b>\n"
                            "Kiểm tra lại tài khoản hoặc trang web có thể đang chặn bot.")

if __name__ == "__main__":
    main()
