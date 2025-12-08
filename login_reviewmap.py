import os
import time
import json
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
# ===============================================


def send_telegram(message):
    if not (TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID):
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}, timeout=10)
    except:
        pass


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


def has_new_task_popup(driver):
    """Kiểm tra có popup chứa từ 'time:' không"""
    try:
        time.sleep(5)  # Đợi popup hiện
        # Cách 1: tìm trong page source
        source = driver.page_source.lower()
        if "time:" in source:
            # Cách 2: tìm element có chứa "time:"
            elems = driver.find_elements(By.XPATH, "//*[contains(translate(text(),'TIME:','time:'),'time:')]")
            if elems:
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
                    "username": cells[1].text.strip(),
                    "last_login_time": cells[4].text.strip(),
                    "last_ip": cells[3].text.strip(),
                    "action": cells[2].text.strip(),
                    "log_id": cells[0].text.strip()
                }
        return None
    except Exception as e:
        print(f"Get info error: {e}")
        return None


def save_report(has_task, login_info):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    report_data = {
        "checked_at": now,
        "has_new_task": has_task,
        "task_status": "Có nhiệm vụ mới" if has_task else "Không có nhiệm vụ",
        "account_info": login_info or {}
    }

    # TXT – dễ đọc
    txt = f"""REVIEWMAP - BÁO CÁO KIỂM TRA
{'='*50}
Thời gian kiểm tra: {now}
Trạng thái nhiệm vụ: {report_data['task_status']}
{'-'*50}
Tài khoản: {login_info.get('username', 'N/A')}
Lần đăng nhập cuối: {login_info.get('last_login_time', 'N/A')}
IP gần nhất: {login_info.get('last_ip', 'N/A')}
Hành động: {login_info.get('action', 'N/A')}
ID log: {login_info.get('log_id', 'N/A')}
"""
    with open("report.txt", "w", encoding="utf-8") as f:
        f.write(txt)

    # JSON
    with open("report.json", "w", encoding="utf-8") as f:
        json.dump(report_data, f, ensure_ascii=False, indent=2)

    print(f"Đã lưu báo cáo – Có nhiệm vụ: {has_task}")


def commit_and_push():
    if not GH_TOKEN or not GITHUB_REPOSITORY:
        print("Không có GH_TOKEN → bỏ qua push")
        return
    os.system("git config --global user.name 'ReviewMap Bot'")
    os.system("git config --global user.email 'bot@example.com'")
    os.system(f"git remote set-url origin https://x-access-token:{GH_TOKEN}@github.com/{GITHUB_REPOSITORY}.git")
    os.system("git add report.txt report.json")
    os.system(f'git commit -m "Update: Kiểm tra lúc {datetime.now():%Y-%m-%d %H:%M}" || echo "No changes"')
    os.system("git push origin HEAD:main --quiet")


def main():
    if not USERNAME or not PASSWORD:
        send_telegram("Thiếu USERNAME hoặc PASSWORD!")
        return

    display = Display(visible=0, size=(1920, 1080))
    display.start()

    driver = None
    login_ok = False

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            driver = create_driver()
            print(f"Thử đăng nhập lần {attempt}...")

            if login(driver):
                login_ok = True

                # 1. Vào trang chủ kiểm tra popup nhiệm vụ
                driver.get(HOME_URL)
                has_task = has_new_task_popup(driver)

                # 2. Nếu có nhiệm vụ → báo Telegram ngay
                if has_task:
                    send_telegram("Có nhiệm vụ Review Maps mới!\nNhanh tay nhận kẻo hết!")

                # 3. Lấy thông tin đăng nhập cuối + lưu báo cáo
                login_info = get_last_login_info(driver)
                save_report(has_task, login_info)
                commit_and_push()

                print("Hoàn tất kiểm tra!")
                break

        except Exception as e:
            print(f"Lỗi lần {attempt}: {e}")
        finally:
            if driver:
                driver.quit()

        time.sleep(15)

    display.stop()

    # Chỉ báo thất bại 1 lần duy nhất
    if not login_ok:
        send_telegram("ĐĂNG NHẬP REVIEWMAP THẤT BẠI SAU 3 LẦN THỬ!\n"
                      "Kiểm tra tài khoản/mật khẩu hoặc web đang chặn bot.")


if __name__ == "__main__":
    main()
