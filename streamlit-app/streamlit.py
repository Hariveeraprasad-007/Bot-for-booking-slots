import streamlit as st
import threading
import time
from datetime import datetime, timedelta
import re
import schedule
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import StaleElementReferenceException, NoSuchElementException, TimeoutException, ElementClickInterceptedException
import requests
try:
    from playsound import playsound
    SOUND_AVAILABLE = True
except ImportError:
    SOUND_AVAILABLE = False
try:
    import GPUtil
    GPU_AVAILABLE = True
except ImportError:
    GPU_AVAILABLE = False

# Global lists to hold slot details, active threads, and drivers
slot_list = []
active_threads = []
active_drivers = []
scheduled_time = None

# Venue time slot configurations
venue_details = {
    "1731": {
        "slot_duration_minutes": 120,
        "overall_start_time_str": "8:00 AM", "overall_end_time_str": "4:30 PM",
        "break_time_str": ("12:00 PM", "1:00 PM"),
        "fixed_start_times_str": ["8:00 AM", "10:00 AM", "1:00 PM", "3:00 PM"]
    },
    "1851": {
        "slot_duration_minutes": 120,
        "overall_start_time_str": "8:00 AM", "overall_end_time_str": "4:30 PM",
        "break_time_str": ("12:00 PM", "1:00 PM"),
        "fixed_start_times_str": ["8:00 AM", "10:00 AM", "1:00 PM", "3:00 PM"]
    },
    "1852": {
        "slot_duration_minutes": 60,
        "overall_start_time_str": "8:00 AM", "overall_end_time_str": "4:00 PM",
        "break_time_str": ("12:00 PM", "1:00 PM"),
        "fixed_start_times_str": ["8:00 AM", "9:00 AM", "10:00 AM", "11:00 AM", "1:00 PM", "2:00 PM", "3:00 PM"]
    },
    "1611": {
        "slot_duration_minutes": 15,
        "overall_start_time_str": "8:00 AM", "overall_end_time_str": "4:30 PM",
        "break_time_str": ("12:00 PM", "1:00 PM"),
        "generate_all_intervals": True
    }
}

# URLs for scheduling
urls = {
    "1731": "https://lms2.ai.saveetha.in/mod/scheduler/view.php?id=36638",
    "1851": "https://lms2.ai.saveetha.in/mod/scheduler/view.php?id=36298",
    "1852": "https://lms2.ai.saveetha.in/mod/scheduler/view.php?id=37641",
    "1611": "https://lms2.ai.saveetha.in/mod/scheduler/view.php?id=36137"
}

# Check LMS connectivity
def check_lms_connectivity():
    lms_url = "https://lms2.ai.saveetha.in/"
    try:
        response = requests.get(lms_url, timeout=5)
        if response.status_code == 200:
            st.success("LMS URL is accessible.")
            return True
        else:
            st.error(f"LMS URL returned status code: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        st.error(f"Failed to connect to LMS URL: {e}")
        return False

def check_gpu_availability():
    if GPU_AVAILABLE:
        try:
            gpus = GPUtil.getGPUs()
            if gpus and any(gpu.load < 0.9 for gpu in gpus):
                st.info("GPU detected and available.")
                return True, "--enable-gpu"
            else:
                st.warning("No available GPU or GPU fully utilized. Falling back to CPU.")
                return False, "--disable-gpu"
        except Exception as e:
            st.error(f"Error checking GPU: {e}. Falling back to CPU.")
            return False, "--disable-gpu"
    else:
        st.warning("GPUtil not installed. Falling back to CPU.")
        return False, "--disable-gpu"

def _generate_interval_start_times(overall_start_dt, overall_end_dt, interval_m, break_start_dt, break_end_dt):
    times = []
    current_time = overall_start_dt
    while current_time < overall_end_dt:
        is_during_break = False
        if break_start_dt and break_end_dt:
            if break_start_dt <= current_time < break_end_dt:
                is_during_break = True
        if not is_during_break:
            formatted_time = current_time.strftime("%I:%M %p").lstrip('0').replace(' 0', ' ').replace(':00 ', ':00').replace('AM',' AM').replace('PM',' PM')
            times.append(formatted_time)
        current_time += timedelta(minutes=interval_m)
        if break_start_dt and break_end_dt and break_start_dt <= current_time < break_end_dt:
            current_time = break_end_dt
    return times

def slot_booking_process(username_input, password_input, day, date, start_time, end_time, scheduler_url, proxy, headless, browser_choice, continuous=False, check_until_time=None):
    driver = None
    try:
        use_gpu, gpu_arg = check_gpu_availability()
        st.session_state.status = f"Using {'GPU' if use_gpu else 'CPU'} | Initializing..."

        deadline = None
        if check_until_time and continuous:
            try:
                deadline = datetime.strptime(check_until_time, "%H:%M")
                deadline = datetime.now().replace(hour=deadline.hour, minute=deadline.minute, second=0, microsecond=0)
                if deadline < datetime.now():
                    deadline = deadline.replace(day=deadline.day + 1)
                st.write(f"Will check until {deadline.strftime('%H:%M:%S')}")
            except ValueError:
                st.error(f"Invalid time format: {check_until_time}. Use HH:MM (e.g., 21:30).")
                return

        if browser_choice == "Chrome":
            options = ChromeOptions()
            options.add_argument("--headless=new")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")
            options.add_argument("--window-size=1280,720")
            options.add_argument("--disable-extensions")
            options.add_argument("--blink-settings=imagesEnabled=false")
            options.add_argument("--page-load-strategy=eager")
            options.add_experimental_option("prefs", {"profile.managed_default_content_settings.images": 2})
            try:
                driver = webdriver.Chrome(options=options)
            except Exception as e:
                st.error(f"Failed to initialize Chrome driver: {e}")
                return
        elif browser_choice == "Firefox":
            options = FirefoxOptions()
            options.add_argument("--headless")
            if proxy:
                options.set_preference("network.proxy.type", 1)
                options.set_preference("network.proxy.http", proxy.split(":")[0])
                options.set_preference("network.proxy.http_port", int(proxy.split(":")[1]))
            options.set_preference("permissions.default.image", 2)
            options.set_preference("dom.ipc.processCount", 8)
            try:
                driver = webdriver.Firefox(options=options)
            except Exception as e:
                st.error(f"Failed to initialize Firefox driver: {e}")
                return
        elif browser_choice == "Edge":
            options = EdgeOptions()
            options.add_argument("--headless")
            options.add_argument("--disable-gpu")
            options.add_argument("--window-size=1280,720")
            options.add_argument("--blink-settings=imagesEnabled=false")
            options.add_argument("--page-load-strategy=eager")
            try:
                driver = webdriver.Edge(options=options)
            except Exception as e:
                st.error(f"Failed to initialize Edge driver: {e}")
                return
        else:
            raise ValueError("Unsupported browser")

        active_drivers.append(driver)
        st.write(f"Running in {browser_choice} headless mode")
        driver.implicitly_wait(0.2)

        st.session_state.status = "Logging in..."
        driver.get("https://lms2.ai.saveetha.in/course/view.php?id=302")
        try:
            username_field = WebDriverWait(driver, 3, poll_frequency=0.1).until(EC.presence_of_element_located((By.NAME, 'username')))
            username_field.send_keys(username_input)
            driver.find_element(By.NAME, 'password').send_keys(password_input)
            driver.find_element(By.ID, 'loginbtn').click()
            st.write("Logged in")
        except TimeoutException as e:
            st.error(f"Login timeout: {e}. Fields not found.")
            return

        try:
            date_obj = datetime.strptime(date.strip(), "%d %m %Y")
            formatted_date_for_comparison = date_obj.strftime("%A, %d %B %Y")
        except ValueError:
            st.error(f"Invalid date format: {date}")
            return

        def normalize_time(time_str):
            return re.sub(r'\s+', ' ', time_str.strip().lstrip('0').replace(':00 ', ':00').replace('AM', ' AM').replace('PM', ' PM')).replace("  ", " ")

        normalized_start_time = normalize_time(start_time)
        normalized_end_time = normalize_time(end_time)
        st.write(f"Looking for slot: {formatted_date_for_comparison}, {normalized_start_time}-{normalized_end_time}")

        found_slot = False
        attempt = 0
        refresh_interval = 0.5

        while not found_slot:
            attempt += 1
            st.session_state.status = f"Attempt {attempt}: Checking slot..."
            if deadline and datetime.now() > deadline:
                st.error(f"Deadline {deadline.strftime('%H:%M:%S')} reached.")
                return

            driver.get(scheduler_url)
            page_source = driver.page_source
            if "503 Service Unavailable" in page_source or "Service Temporarily Unavailable" in page_source or "ERR_CONNECTION_REFUSED" in page_source:
                st.session_state.status = f"503 Error detected. Retrying... (Attempt {attempt})"
                time.sleep(refresh_interval)
                continue

            WebDriverWait(driver, 2).until(EC.presence_of_element_located((By.CSS_SELECTOR, "table#slotbookertable, table.generaltable")))
            try:
                WebDriverWait(driver, 0.5).until(EC.presence_of_element_located((By.XPATH, "//button[contains(@class, 'btn') and contains(text(), 'Cancel booking')]")))
                st.warning("Existing booking found. Please cancel it to book a new slot.")
                return
            except TimeoutException:
                pass

            try:
                WebDriverWait(driver, 0.5).until(EC.presence_of_element_located((By.XPATH, "//th[contains(text(), 'Other participants')]")))
                st.warning("Frozen slot detected. Please resolve this to book a new slot.")
                return
            except TimeoutException:
                pass

            all_rows = WebDriverWait(driver, 1, poll_frequency=0.1).until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "table#slotbookertable tbody tr")))
            current_date_in_table = ""

            for row in all_rows:
                try:
                    cells = row.find_elements(By.TAG_NAME, 'td')
                    if len(cells) < 8:
                        continue

                    date_cell_text = cells[0].text.strip()
                    if date_cell_text:
                        current_date_in_table = date_cell_text

                    try:
                        parsed_table_date = datetime.strptime(current_date_in_table, "%A, %d %B %Y")
                    except ValueError:
                        continue

                    if parsed_table_date.date() == date_obj.date():
                        table_start_time = normalize_time(cells[1].text.strip())
                        table_end_time = normalize_time(cells[2].text.strip())

                        if normalized_start_time == table_start_time and normalized_end_time == table_end_time:
                            st.write(f"Found slot: {table_start_time}-{table_end_time}")
                            try:
                                book_button = cells[7].find_element(By.XPATH, ".//button[contains(text(), 'Book slot')]")
                                if book_button.is_enabled():
                                    ActionChains(driver).move_to_element(book_button).click().perform()
                                    found_slot = True
                                    try:
                                        note_field = WebDriverWait(driver, 3, poll_frequency=0.1).until(EC.visibility_of_element_located((By.ID, "id_studentnote_editoreditable")))
                                        note_field.send_keys("Booking for project work (automated)")
                                        submit_button = WebDriverWait(driver, 1, poll_frequency=0.1).until(EC.element_to_be_clickable((By.ID, "id_submitbutton")))
                                        submit_button.click()
                                        try:
                                            WebDriverWait(driver, 2, poll_frequency=0.1).until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'confirmed') or contains(text(), 'success')]")))
                                            st.success(f"Slot booked: {day}, {date}, {start_time}-{end_time}")
                                            if SOUND_AVAILABLE:
                                                try:
                                                    playsound('success.wav')
                                                except Exception as se:
                                                    st.error(f"Error playing sound: {se}")
                                            return
                                        except TimeoutException:
                                            WebDriverWait(driver, 2, poll_frequency=0.1).until(EC.presence_of_element_located((By.XPATH, f"//tr[td[contains(text(), '{formatted_date_for_comparison}')]][td[contains(text(), '{start_time}')] and td[contains(text(), '{end_time}')]]")))
                                            st.success(f"Slot booked: {day}, {date}, {start_time}-{end_time}")
                                            return
                                    except TimeoutException:
                                        st.success(f"Slot booked: {day}, {date}, {start_time}-{end_time} (Verify manually)")
                                        return
                                else:
                                    st.write("Book slot button disabled.")
                                    break
                            except (NoSuchElementException, ElementClickInterceptedException) as e:
                                st.error(f"Button interaction error: {e}")
                                break
                except StaleElementReferenceException:
                    st.write("Stale element, retrying...")
                    break
                except Exception as e:
                    st.error(f"Row processing error: {e}")
                    continue

            if not continuous:
                st.error(f"Slot not found for {day}, {date}, {start_time}-{end_time}.")
                return
            time.sleep(refresh_interval)

    except Exception as e:
        st.error(f"Unexpected error: {e}")
    finally:
        if driver:
            if driver in active_drivers:
                active_drivers.remove(driver)
            try:
                driver.quit()
            except Exception:
                pass

def add_slot():
    date = st.session_state.date_input
    try:
        date_obj = datetime.strptime(date, "%Y-%m-%d")
        day = date_obj.strftime("%A")
        st.session_state.day = day
    except ValueError:
        st.error("Please select a valid date.")
        return

    start_time = st.session_state.start_time
    end_time = st.session_state.end_time
    if not all([day, date, start_time, end_time]):
        st.error("Please fill in all slot fields.")
        return

    selected_venue_id = st.session_state.schedule
    if selected_venue_id in venue_details:
        config = venue_details[selected_venue_id]
        overall_start_dt = datetime.strptime(config["overall_start_time_str"], "%I:%M %p")
        overall_end_dt = datetime.strptime(config["overall_end_time_str"], "%I:%M %p")
        break_start_dt = None
        break_end_dt = None
        if config["break_time_str"]:
            break_start_dt = datetime.strptime(config["break_time_str"][0], "%I:%M %p")
            break_end_dt = datetime.strptime(config["break_time_str"][1], "%I:%M %p")

        expected_start_times = []
        if "fixed_start_times_str" in config:
            expected_start_times = config["fixed_start_times_str"]
        elif "generate_all_intervals" in config and config["generate_all_intervals"]:
            expected_start_times = _generate_interval_start_times(
                overall_start_dt, overall_end_dt, config["slot_duration_minutes"],
                break_start_dt, break_end_dt
            )

        if start_time not in expected_start_times:
            st.error(f"The selected start time '{start_time}' is not valid for venue {selected_venue_id}.")
            return

    slot = {"day": day, "date": date_obj.strftime("%d %m %Y"), "start_time": start_time, "end_time": end_time}
    slot_list.append(slot)
    st.session_state.slots.append(f"Day: {day}, Date: {slot['date']}, Start: {start_time}, End: {end_time}")

def remove_slot(index):
    if index < len(slot_list):
        slot_list.pop(index)
        st.session_state.slots.pop(index)

def stop_process():
    schedule.clear()
    global scheduled_time
    scheduled_time = None
    for driver in active_drivers[:]:
        try:
            driver.quit()
            active_drivers.remove(driver)
        except Exception:
            pass
    for thread in active_threads[:]:
        try:
            active_threads.remove(thread)
        except Exception:
            pass
    st.success("All booking processes and schedules stopped.")
    st.session_state.status = "Status: Stopped"

def run_booking(continuous=False):
    global scheduled_time
    if scheduled_time:
        now = datetime.now()
        scheduled = datetime.strptime(scheduled_time, "%H:%M")
        scheduled_today = now.replace(hour=scheduled.hour, minute=scheduled.minute, second=0, microsecond=0)
        time_diff = abs((now - scheduled_today).total_seconds())
        if time_diff > 60:
            st.write(f"Booking attempt ignored: Current time {now.strftime('%H:%M:%S')} is not within 1 minute of scheduled time {scheduled_time}")
            return

    username = st.session_state.username
    password = st.session_state.password
    choice = st.session_state.schedule
    browser_choice = "Chrome"  # Force Chrome for Streamlit Cloud compatibility
    headless_mode = st.session_state.headless
    proxies = st.session_state.proxies.split(",") if st.session_state.proxies else []
    check_until_time = st.session_state.check_until or None

    if choice not in urls:
        st.error("Invalid schedule selected.")
        return
    if not slot_list:
        st.error("Please add at least one slot to book.")
        return
    if not check_lms_connectivity():
        st.error("Cannot proceed with booking due to LMS connectivity issues.")
        return

    scheduler_url = urls[choice]
    for i, slot in enumerate(slot_list):
        proxy = proxies[i % len(proxies)] if proxies else None
        thread = threading.Thread(target=slot_booking_process, args=(
            username, password, slot["day"], slot["date"], slot["start_time"], slot["end_time"],
            scheduler_url, proxy, headless_mode, browser_choice, continuous, check_until_time
        ))
        active_threads.append(thread)
        thread.start()

def schedule_booking():
    global scheduled_time
    schedule_time = st.session_state.schedule_time
    try:
        datetime.strptime(schedule_time, "%H:%M")
        schedule.clear()
        scheduled_time = schedule_time
        schedule.every().day.at(schedule_time).do(lambda: run_booking(continuous=True))
        st.success(f"Booking scheduled daily at {schedule_time}")
        st.session_state.status = f"Status: Scheduled at {schedule_time}"

        def run_schedule():
            while True:
                schedule.run_pending()
                time.sleep(30)
        threading.Thread(target=run_schedule, daemon=True).start()
    except ValueError:
        st.error("Invalid time format. Use HH:MM (e.g., 21:03).")

# Streamlit UI
st.title("Enhanced Slot Booking Bot - Saveetha LMS")

# Initialize session state defaults
if 'username' not in st.session_state:
    st.session_state.username = ""
if 'password' not in st.session_state:
    st.session_state.password = ""
if 'slots' not in st.session_state:
    st.session_state.slots = []
if 'status' not in st.session_state:
    st.session_state.status = "Status: Idle"
if 'start_time_options' not in st.session_state:
    st.session_state.start_time_options = []
if 'end_time' not in st.session_state:
    st.session_state.end_time = ""
if 'day' not in st.session_state:
    st.session_state.day = ""
if 'schedule' not in st.session_state:
    st.session_state.schedule = list(venue_details.keys())[0]
if 'proxies' not in st.session_state:
    st.session_state.proxies = ""
if 'schedule_time' not in st.session_state:
    st.session_state.schedule_time = ""
if 'check_until' not in st.session_state:
    st.session_state.check_until = ""
if 'headless' not in st.session_state:
    st.session_state.headless = True
if 'date_input' not in st.session_state:
    st.session_state.date_input = datetime.today().strftime("%Y-%m-%d")

# Credentials
st.subheader("Credentials")
username = st.text_input("Username", value=st.session_state.username, key="username_input")
password = st.text_input("Password", type="password", value=st.session_state.password, key="password_input")
st.session_state.username = username
st.session_state.password = password

# Configuration
st.subheader("Configuration")
schedule = st.selectbox("Select Schedule", list(venue_details.keys()), index=list(venue_details.keys()).index(st.session_state.schedule), key="schedule_input")
proxies = st.text_input("Proxies (comma-separated, e.g., http://proxy1:port,http://proxy2:port)", value=st.session_state.proxies, key="proxies_input")
schedule_time = st.text_input("Schedule Time (HH:MM, e.g., 21:03)", value=st.session_state.schedule_time, key="schedule_time_input")
check_until = st.text_input("Check Until Time (HH:MM, e.g., 21:30, optional)", value=st.session_state.check_until, key="check_until_input")
headless = st.checkbox("Run Headless (Continuous Refresh)", value=st.session_state.headless, key="headless_input")
st.session_state.schedule = schedule
st.session_state.proxies = proxies
st.session_state.schedule_time = schedule_time
st.session_state.check_until = check_until
st.session_state.headless = headless

# Slot Details
st.subheader("Slot Details")
date_input = st.date_input("Date", min_value=datetime.today(), value=datetime.strptime(st.session_state.date_input, "%Y-%m-%d"), key="date_input_field")
st.session_state.date_input = date_input.strftime("%Y-%m-%d")
try:
    date_obj = datetime.strptime(st.session_state.date_input, "%Y-%m-%d")
    st.session_state.day = date_obj.strftime("%A")
except ValueError:
    st.session_state.day = ""
st.text_input("Day (Auto-filled)", value=st.session_state.day, disabled=True, key="day_input")

if st.session_state.schedule in venue_details:
    config = venue_details[st.session_state.schedule]
    overall_start_dt = datetime.strptime(config["overall_start_time_str"], "%I:%M %p")
    overall_end_dt = datetime.strptime(config["overall_end_time_str"], "%I:%M %p")
    break_start_dt = None
    break_end_dt = None
    if config["break_time_str"]:
        break_start_dt = datetime.strptime(config["break_time_str"][0], "%I:%M %p")
        break_end_dt = datetime.strptime(config["break_time_str"][1], "%I:%M %p")

    if "fixed_start_times_str" in config:
        st.session_state.start_time_options = config["fixed_start_times_str"]
    elif "generate_all_intervals" in config and config["generate_all_intervals"]:
        st.session_state.start_time_options = _generate_interval_start_times(
            overall_start_dt, overall_end_dt, config["slot_duration_minutes"],
            break_start_dt, break_end_dt
        )

start_time = st.selectbox("Start Time", st.session_state.start_time_options, key="start_time_input")
st.session_state.start_time = start_time
if st.session_state.start_time and st.session_state.schedule in venue_details:
    config = venue_details[st.session_state.schedule]
    try:
        start_dt_obj = datetime.strptime(st.session_state.start_time, "%I:%M %p")
        overall_end_dt = datetime.strptime(config["overall_end_time_str"], "%I:%M %p")
        potential_end_dt_obj = start_dt_obj + timedelta(minutes=config["slot_duration_minutes"])
        actual_end_dt_obj = min(potential_end_dt_obj, overall_end_dt)
        st.session_state.end_time = actual_end_dt_obj.strftime("%I:%M %p").lstrip('0').replace(' 0', ' ').replace(':00 ', ':00').replace('AM',' AM').replace('PM',' PM')
    except ValueError:
        st.session_state.end_time = "Invalid Time"

st.text_input("End Time", value=st.session_state.end_time, disabled=True, key="end_time_input")

if st.button("Add Slot", key="add_slot"):
    add_slot()

# Selected Slots
st.subheader("Selected Slots")
for i, slot in enumerate(st.session_state.slots):
    col1, col2 = st.columns([4, 1])
    col1.write(slot)
    if col2.button("Remove", key=f"remove_{i}"):
        remove_slot(i)

# Actions
st.subheader("Actions")
col1, col2, col3 = st.columns(3)
if col1.button("Book Slots Now", key="book_now"):
    run_booking(continuous=True)
if col2.button("Schedule Booking", key="schedule_booking"):
    schedule_booking()
if col3.button("Stop Process", key="stop_process"):
    stop_process()

st.write(st.session_state.status)
