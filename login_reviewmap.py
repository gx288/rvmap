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
from selenium.common.exceptions import TimeoutException
from webdriver_manager.chrome import ChromeDriverManager
from pyvirtualdisplay import Display


# ==================== CONFIG ====================
USERNAME = os.getenv('REVIEWMAP_USERNAME')
PASSWORD = os.getenv('REVIEWMAP_PASSWORD')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
GH_TOKEN = os.getenv('GH_TOKEN')
GITHUB_REPOSITORY = os.getenv('GITHUB_REPOSITORY', '')

LOGIN_URL = "https://reviewmap.vn/login"
HOME_URL = "https://reviewmap.vn/"
PROFILE_URL = "https://reviewmap.vn/account/profile"
MAX_RETRIES = 3
# ===============================================


def send_telegram(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, data={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML"
        }, timeout=10)
        return True
    except:
        return False


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
        wait.until(EC.element_to_be_clickable((By.NAME, "username"))).send_keys(USERNAME)
        driver.find_element(By.NAME, "password").send_keys(PASSWORD)
        driver.find_element(By.XPATH, "//button[contains(., 'Đăng Nhập')]").click()
        time.sleep(7)
        return driver.current_url.startswith(HOME_URL)
    except Exception as e:
        print(f"Login error: {e}")
        return False


def check_new_task_popup(driver):
    """Kiểm tra có popup chứa từ 'time:' không (dấu hiệu có nhiệm vụ mới)"""
    try:
        # Đợi 5s để popup hiện (nếu có)
        time.sleep(5)
        page_source = driver.page_source.lower()
        if "time:" in page_source and ("modal" in page_source or "popup" in page_source or "toast" in page_source):
            # Thêm kiểm tra chính xác hơn: tìm thẻ có chứa "time:" trong nội dung
            elements = driver.find_elements(By.XPATH, "//*[contains(translate(text(), 'TIME:', 'time:'), 'time:')]")
            if elements:
                send_telegram("Có nhiệm vụ Review Maps mới.\nNhanh tay nhận kẻo hết!")
                print("PHÁT HIỆN NHIỆM VỤ MỚI!")
                return True
        return False
    except:
        return False


def get_last_login_info(driver):
    try:
        driver.get(PROFILE_URL)
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "table#datatable tbody tr"))
        )
        rows = driver.find_elements(By.CSS_SELECTOR, "table#datatable tbody tr")
        for row in rows:
            cells = row.find_elements(By.TAG_NAME, "td")
            if len(cells) >= 5 and "Đăng nhập thành công qua WEB" in cells[2].text:
                return {
                    "id": cells[0].text.strip(),
                    "username": cells[1].text.strip(),
                    "action": cells[2].text.strip(),
                    "ip": cells[3].text.strip(),
                    "time": cells[4].text.strip(),
                    "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
        return None
    except Exception as e:
        print(f"Error getting login info: {e}")
        return None


def save_report(data):
    if not data:
        return
    txt_content = f"""REVIEWMAP - BÁO CÁO ĐĂNG NHẬP
{'='*50}
Thời gian kiểm tra: {data['checked_at']}
Tài khoản: {data['username']}
Lần đăng nhập cuối: {data['time']}
IP gần nhất: {data['ip']}
Hành động: {data['action']}
ID log: {data['id']}
"""
    with open("report.txt", "w", encoding="utf-8") as f:
        f.write(txt_content)

    with open("report.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def commit_and_push():
    if not GH_TOKEN or not GITHUB_REPOSITORY:
        return
    os.system("git config --global user.name 'ReviewMap Bot'")
    os.system("git config --global user.email 'bot@example.com'")
    os.system(f"git remote set-url origin https://x-access-token:{GH_TOKEN}@github.com/{GITHUB_REPOSITORY}.git")
    os.system("git add report.txt report.json")
    os.system('git commit -m "Update: Báo cáo đăng nhập $(date)" || echo "No changes"')
    os.system("git push origin HEAD:main --quiet || echo 'Push failed'")


def main():
    if not USERNAME or not PASSWORD:
        send_telegram("Thiếu USERNAME hoặc PASSWORD trong Secrets!")
        return

    display = Display(visible=0, size=(1920, 1080))
    display.start()

    driver = None
    login_success = False

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            driver = create_driver()
            print(f"Thử đăng nhập lần {attempt}...")

            if login(driver):
                login_success = True
                print("Đăng nhập thành công!")

                # Bước 1: Kiểm tra popup nhiệm vụ mới
                driver.get(HOME_URL)
                has_new_task = check_new_task_popup(driver)

                # Bước 2: Lấy thông tin đăng nhập cuối + lưu file
                last_login = get_last_login_info(driver)
                if last_login:
                    msg = (f"<b>Đăng nhập ReviewMap thành công!</b>\n"
                           f"Tài khoản: <code>{last_login['username']}</code>\n"
                           f"Đăng nhập cuối: <b>{last_login['time']}</b>\n"
                           f"IP: <code>{last_login['ip']}</code>\n"
                           f"Kiểm tra lúc: {last_login['checked_at']}")
                    if has_new_task:
                        msg = "\n" + msg
                    send_telegram(msg)

                    save_report(last_login)
                    commit_and_push()
                else:
                    send_telegram("Đăng nhập OK nhưng không lấy được lịch sử hoạt động")

                break

        except Exception as e:
            print(f"Lỗi lần {attempt}: {e}")
        finally:
            if driver:
                driver.quit()

        if attempt < MAX_RETRIES:
            time.sleep(15)

    display.stop()

    # Chỉ gửi thất bại 1 lần duy nhất sau 3 lần thử
    if not login_success:
        send_telegram("ĐĂNG NHẬP REVIEWMAP THẤT BẠI SAU 3 LẦN THỬ!\n"
                      "Kiểm tra lại tài khoản, mật khẩu hoặc web đang chặn bot.")

if __name__ == "__main__":
    main()
