import os
import time
import json
import requests
from datetime import datetime
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
GITHUB_ACTOR = os.getenv('GITHUB_ACTOR', 'bot')
GITHUB_TOKEN = os.getenv('GH_TOKEN')  # Token có quyền push repo

LOGIN_URL = "https://reviewmap.vn/login"
PROFILE_URL = "https://reviewmap.vn/account/profile"
HOME_URL = "https://reviewmap.vn/"
MAX_RETRIES = 3
REPORT_FILE_TXT = "report.txt"
REPORT_FILE_JSON = "report.json"
# ===============================================


def send_telegram(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}, timeout=10)
    except Exception as e:
        print(f"Telegram error: {e}")


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

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => false});")
    return driver


def login(driver):
    try:
        driver.get(LOGIN_URL)
        wait = WebDriverWait(driver, 20)
        wait.until(EC.presence_of_element_located((By.NAME, "username"))).send_keys(USERNAME)
        driver.find_element(By.NAME, "password").send_keys(PASSWORD)
        driver.find_element(By.XPATH, "//button[contains(., 'Đăng Nhập')]").click()
        time.sleep(6)
        return driver.current_url.startswith(HOME_URL)
    except Exception as e:
        print(f"Login error: {e}")
        return False


def get_last_login_info(driver):
    try:
        driver.get(PROFILE_URL)
        wait = WebDriverWait(driver, 15)

        # Đợi bảng lịch sử load
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "table#datatable tbody tr")))

        rows = driver.find_elements(By.CSS_SELECTOR, "table#datatable tbody tr")
        for row in rows:
            cells = row.find_elements(By.TAG_NAME, "td")
            if len(cells) >= 5:
                content = cells[2].text.strip()
                if "Đăng nhập thành công qua WEB" in content:
                    last_login = {
                        "id": cells[0].text.strip(),
                        "username": cells[1].text.strip(),
                        "action": content,
                        "ip": cells[3].text.strip(),
                        "time": cells[4].text.strip(),
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                    return last_login
        return None
    except Exception as e:
        print(f"Error parsing history: {e}")
        return None


def save_report(data):
    if not data:
        return

    # TXT - dễ đọc
    with open(REPORT_FILE_TXT, "w", encoding="utf-8") as f:
        f.write("REVIEWMAP - BÁO CÁO ĐĂNG NHẬP\n")
        f.write("="*50 + "\n")
        f.write(f"Thời gian chạy: {data['timestamp']}\n")
        f.write(f"Tài khoản: {data['username']}\n")
        f.write(f"Lần đăng nhập cuối: {data['time']}\n")
        f.write(f"IP: {data['ip']}\n")
        f.write(f"Hành động: {data['action']}\n")
        f.write(f"ID log: {data['id']}\n")

    # JSON - để dùng sau
    with open(REPORT_FILE_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print("Đã lưu report.txt và report.json")


def commit_and_push():
    if not GITHUB_TOKEN:
        print("Không có GH_TOKEN → bỏ qua push")
        return

    os.system("git config --global user.name 'ReviewMap Bot'")
    os.system("git config --global user.email 'bot@reviewmap.vn'")
    os.system("git remote set-url origin https://x-access-token:${GH_TOKEN}@github.com/${GITHUB_REPOSITORY}.git")

    os.system("git add report.txt report.json")
    os.system('git commit -m "Cập nhật báo cáo đăng nhập $(date)" || echo "No changes"')
    os.system("git push origin HEAD:main || echo 'Push failed or no changes'")


def main():
    if not USERNAME or not PASSWORD:
        send_telegram("Thiếu USERNAME hoặc PASSWORD!")
        return

    display = Display(visible=0, size=(1920, 1080))
    display.start()

    driver = None
    success = False

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            driver = create_driver()
            send_telegram(f"Bắt đầu đăng nhập lần {attempt}...")

            if login(driver):
                send_telegram("ĐĂNG NHẬP THÀNH CÔNG!")

                last_login = get_last_login_info(driver)
                if last_login:
                    msg = (f"<b>ĐĂNG NHẬP THÀNH CÔNG!</b>\n"
                           f"Tài khoản: <code>{last_login['username']}</code>\n"
                           f"Lần cuối: <b>{last_login['time']}</b>\n"
                           f"IP: <code>{last_login['ip']}</code>\n"
                           f"Thời gian chạy: {last_login['timestamp']}")
                    send_telegram(msg)

                    save_report(last_login)
                    commit_and_push()
                else:
                    send_telegram("Đăng nhập OK nhưng không tìm thấy lịch sử đăng nhập")

                success = True
                break
            else:
                send_telegram(f"Đăng nhập thất bại lần {attempt}")

        except Exception as e:
            send_telegram(f"Lỗi lần {attempt}: {str(e)[:200]}")
        finally:
            if driver:
                driver.quit()

        if attempt < MAX_RETRIES:
            time.sleep(15)

    display.stop()

    if not success:
        send_telegram("ĐĂNG NHẬP THẤT BẠI SAU 3 LẦN THỬ!")


if __name__ == "__main__":
    main()
