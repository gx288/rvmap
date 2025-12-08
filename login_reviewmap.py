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
GH_TOKEN = os.getenv('GH_TOKEN')
GITHUB_REPOSITORY = os.getenv('GITHUB_REPOSITORY', '')

LOGIN_URL = "https://reviewmap.vn/login"
HOME_URL = "https://reviewmap.vn/"
PROFILE_URL = "https://reviewmap.vn/account/profile"
MAX_RETRIES = 3
REPORT_DIR = "reports"  # Tạo thư mục riêng cho đẹp
# ===============================================

if not os.path.exists(REPORT_DIR):
    os.makedirs(REPORT_DIR)
    print(f"Tạo thư mục: {REPORT_DIR}")

def log(message):
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {message}")

def send_telegram(message):
    if not (TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID):
        log("Thiếu config Telegram → bỏ qua gửi")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}, timeout=10)
        log("Đã gửi Telegram")
    except Exception as e:
        log(f"Gửi Telegram thất bại: {e}")

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
        log(f"Lỗi khi đăng nhập: {e}")
        return False

def has_new_task_popup(driver):
    log("Kiểm tra popup nhiệm vụ mới (có chứa 'time:')...")
    time.sleep(6)
    source = driver.page_source.lower()
    if "time:" in source:
        elems = driver.find_elements(By.XPATH, "//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ:', 'abcdefghijklmnopqrstuvwxyz:'), 'time:')]")
        if elems:
            log("PHÁT HIỆN NHIỆM VỤ MỚI!")
            return True
    log("Không có nhiệm vụ mới")
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
                log(f"Tìm thấy log đăng nhập: {info['last_login_time']} từ IP {info['last_ip']}")
                return info
        log("Không tìm thấy dòng 'Đăng nhập thành công'")
        return None
    except Exception as e:
        log(f"Lỗi lấy thông tin cá nhân: {e}")
        return None

def save_report(has_task, login_info):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    status = "CÓ NHIỆM VỤ MỚI" if has_task else "KHÔNG CÓ NHIỆM VỤ"

    txt_content = f"""REVIEWMAP - BÁO CÁO KIỂM TRA
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
    json_path = f"{REPORT_DIR}/report.json"

    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(txt_content)
    log(f"Đã ghi file: {txt_path}")

    report_json = {
        "checked_at": now,
        "has_new_task": has_task,
        "task_status": status,
        "account": login_info or {}
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report_json, f, ensure_ascii=False, indent=2)
    log(f"Đã ghi file: {json_path}")

def commit_and_push():
    if not GH_TOKEN:
        log("Không có GH_TOKEN → bỏ qua push")
        return False

    log("Bắt đầu commit & push lên GitHub...")
    try:
        os.system("git config --global user.name 'ReviewMap Bot'")
        os.system("git config --global user.email 'bot@noreply.github.com'")
        os.system(f"git remote set-url origin https://x-access-token:{GH_TOKEN}@github.com/{GITHUB_REPOSITORY}.git")

        os.system("git add reports/")
        os.system(f'git commit -m "Auto update: Kiểm tra ReviewMap {datetime.now():%Y-%m-%d %H:%M:%S}"')
        os.system("git push origin HEAD:main --force")
        log("PUSH THÀNH CÔNG! File đã lên repo")
        return True
    except Exception as e:
        log(f"Push thất bại: {e}")
        return False

def main():
    log("BẮT ĐẦU CHẠY REVIEWMAP CHECKER")

    if not USERNAME or not PASSWORD:
        log("Thiếu USERNAME hoặc PASSWORD!")
        send_telegram("LỖI: Thiếu username/password trong Secrets!")
        return

    display = Display(visible=0, size=(1920, 1080))
    display.start()
    log("Màn hình ảo đã bật")

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
                    send_telegram("CÓ NHIỆM VỤ REVIEW MAPS MỚI!\nNhanh tay vào nhận ngay!")

                login_info = get_last_login_info(driver)
                save_report(has_task, login_info)
                commit_and_push()
                log("HOÀN TẤT LẦN NÀY!")
                break
            else:
                log("Đăng nhập thất bại")

        except Exception as e:
            log(f"Lỗi nghiêm trọng lần {attempt}: {e}")
        finally:
            if driver:
                driver.quit()

        if attempt < MAX_RETRIES:
            log("Chờ 20 giây trước khi thử lại...")
            time.sleep(20)

    display.stop()

    if not success:
        send_telegram("ĐĂNG NHẬP THẤT BẠI HOÀN TOÀN SAU 3 LẦN!\nKiểm tra tài khoản hoặc web đang chặn bot.")

    log("KẾT THÚC CHƯƠNG TRÌNH")

if __name__ == "__main__":
    main()
