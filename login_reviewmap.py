# login_reviewmap.py
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

LOGIN_URL = "https://reviewmap.vn/login"
HOME_URL = "https://reviewmap.vn/"
PROFILE_URL = "https://reviewmap.vn/account/profile"
MAX_RETRIES = 3
REPORT_DIR = "reports"
# ===============================================

if not os.path.exists(REPORT_DIR):
    os.makedirs(REPORT_DIR)

def log(message):
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {message}")

def send_telegram(message):
    if not (TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID):
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}, timeout=10)
        log("Telegram: Đã gửi thông báo")
    except Exception as e:
        log(f"Telegram lỗi: {e}")

def create_driver():
    log("Khởi tạo ChromeDriver...")
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
    log("ChromeDriver sẵn sàng")
    return driver

def login(driver):
    log(f"Truy cập trang đăng nhập: {LOGIN_URL}")
    driver.get(LOGIN_URL)
    wait = WebDriverWait(driver, 20)
    try:
        log("Nhập username...")
        wait.until(EC.element_to_be_clickable((By.NAME, "username"))).send_keys(USERNAME)
        log("Nhập password...")
        driver.find_element(By.NAME, "password").send_keys(PASSWORD)
        log("Click Đăng Nhập...")
        driver.find_element(By.XPATH, "//button[contains(., 'Đăng Nhập')]").click()
        time.sleep(8)
        current = driver.current_url
        log(f"URL hiện tại: {current}")
        return current.startswith(HOME_URL)
    except Exception as e:
        log(f"Lỗi đăng nhập: {e}")
        return False

def has_new_task_popup(driver):
    log("Kiểm tra popup NHẬN NHIỆM VỤ...")
    try:
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        time.sleep(3)

        # Cách 1: Tìm "Time XXp"
        if driver.find_elements(By.XPATH, "//h4[contains(translate(., 'TIME', 'time'), 'time') and contains(., 'p')]"):
            log("PHÁT HIỆN NHIỆM VỤ MỚI! (Time XXp)")
            return True

        # Cách 2: Tìm nút "Đồng Ý" có onclick="getJob"
        if driver.find_elements(By.XPATH, "//button[@onclick='getJob(this)' or contains(@onclick, 'getJob')]"):
            log("PHÁT HIỆN NHIỆM VỤ MỚI! (Nút Đồng Ý)")
            return True

        # Cách 3: Tìm tiêu đề "NHẬN NHIỆM VỤ"
        if driver.find_elements(By.XPATH, "//h3[contains(., 'NHẬN NHIỆM VỤ')]"):
            log("PHÁT HIỆN NHIỆM VỤ MỚI! (Tiêu đề popup)")
            return True

        log("Không có nhiệm vụ mới")
        return False
    except Exception as e:
        log(f"Lỗi kiểm tra popup: {e}")
        return False

def get_last_login_info(driver):
    log(f"Truy cập trang cá nhân: {PROFILE_URL}")
    driver.get(PROFILE_URL)
    try:
        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.CSS_SELECTOR, "table#datatable tbody tr")))
        rows = driver.find_elements(By.CSS_SELECTOR, "table#datatable tbody tr")
        for row in rows:
            cells = row.find_elements(By.TAG_NAME, "td")
            if len(cells) >= 5 and "Đăng nhập thành công qua WEB" in cells[2].text:
                info = {
                    "username": cells[1].text.strip(),
                    "last_login_time": cells[4].text.strip(),
                    "last_ip": cells[3].text.strip(),
                    "action": cells[2].text.strip(),
                    "log_id": cells[0].text.strip()
                }
                log(f"Tìm thấy log: {info['last_login_time']} - IP {info['last_ip']}")
                return info
        log("Không thấy dòng đăng nhập thành công")
        return None
    except Exception as e:
        log(f"Lỗi lấy thông tin: {e}")
        return None

def save_report(has_task, login_info):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    status = "CÓ NHIỆM VỤ MỚI" if has_task else "KHÔNG CÓ NHIỆM VỤ"

    new_entry = f"""REVIEWMAP - BÁO CÁO KIỂM TRA
{'='*60}
Thời gian kiểm tra: {now}
TRẠNG THÁI NHIỆM VỤ: {status}
{'-'*60}
Tài khoản       : {login_info.get('username', 'N/A')}
Đăng nhập cuối  : {login_info.get('last_login_time', 'N/A')}
IP gần nhất     : {login_info.get('last_ip', 'N/A')}
Hành động       : {login_info.get('action', 'N/A')}
ID log          : {login_info.get('log_id', 'N/A')}
{'='*60}

"""

    txt_path = f"{REPORT_DIR}/report.txt"
    old_content = ""
    if os.path.exists(txt_path):
        with open(txt_path, "r", encoding="utf-8") as f:
            old_content = f.read()

    full_content = new_entry + old_content
    lines = full_content.strip().split('\n')
    if len(lines) > 5000:
        lines = lines[:5000]
        log(f"Đã cắt bớt log cũ → còn 5000 dòng")

    with open(txt_path, "w", encoding="utf-8") as f:
        f.write('\n'.join(lines) + '\n')
    log(f"Đã thêm báo cáo mới lên đầu – Tổng: {len(lines)} dòng")

    # JSON: chỉ lưu bản mới nhất
    with open(f"{REPORT_DIR}/report.json", "w", encoding="utf-8") as f:
        json.dump({
            "last_check": now,
            "has_new_task": has_task,
            "task_status": status,
            "account": login_info or {}
        }, f, ensure_ascii=False, indent=2)

def main():
    log("BẮT ĐẦU REVIEWMAP CHECKER")

    if not USERNAME or not PASSWORD:
        log("Thiếu username/password!")
        return

    display = Display(visible=0, size=(1920, 1080))
    display.start()

    driver = None
    success = False

    for attempt in range(1, MAX_RETRIES + 1):
        log(f"\n=== LẦN THỬ {attempt}/{MAX_RETRIES} ===")
        try:
            driver = create_driver()

            if login(driver):
                success = True
                driver.get(HOME_URL)
                has_task = has_new_task_popup(driver)

                if has_task:
                    send_telegram("CÓ NHIỆM VỤ REVIEW MAPS MỚI!\n"
                                  "Time 60p - Phần thưởng 6,000đ\n"
                                  "Nhanh tay nhấn Đồng Ý kẻo hết!")

                login_info = get_last_login_info(driver)
                save_report(has_task, login_info)
                log("HOÀN TẤT – FILE ĐÃ ĐƯỢC CẬP NHẬT!")
                break

        except Exception as e:
            log(f"Lỗi nghiêm trọng: {e}")
        finally:
            if driver:
                driver.quit()

        time.sleep(20)

    display.stop()

    if not success:
        send_telegram("ĐĂNG NHẬP THẤT BẠI SAU 3 LẦN!\nKiểm tra tài khoản hoặc web đang chặn")

    log("KẾT THÚC CHƯƠNG TRÌNH")

if __name__ == "__main__":
    main()
