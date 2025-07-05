import streamlit as st
import threading
import time
import gc
import os
from datetime import datetime, timedelta
import re
import schedule
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import (
    StaleElementReferenceException,
    NoSuchElementException,
    TimeoutException,
    ElementClickInterceptedException
)
import requests
from webdriver_manager.chrome import ChromeDriverManager
from dateutil import parser

scheduled_time = None
scheduler_thread = None
scheduler_stop_event = threading.Event()

def cleanup_memory():
    gc.collect()

def get_memory_usage():
    try:
        import psutil
        process = psutil.Process(os.getpid())
        return process.memory_info().rss / 1024 / 1024
    except ImportError:
        return None

venue_details = {
    "1731": {
        "slot_duration_minutes": 120,
        "overall_start_time_str": "8:00 AM",
        "overall_end_time_str": "4:30 PM",
        "break_time_str": ("12:00 PM", "1:00 PM"),
        "fixed_start_times_str": ["8:00 AM", "10:00 AM", "1:00 PM", "3:00 PM"]
    },
    "1851": {
        "slot_duration_minutes": 120,
        "overall_start_time_str": "8:00 AM",
        "overall_end_time_str": "4:30 PM",
        "break_time_str": ("12:00 PM", "1:00 PM"),
        "fixed_start_times_str": ["8:00 AM", "10:00 AM", "1:00 PM", "3:00 PM"]
    },
    "1852": {
        "slot_duration_minutes": 60,
        "overall_start_time_str": "8:00 AM",
        "overall_end_time_str": "4:00 PM",
        "break_time_str": ("12:00 PM", "1:00 PM"),
        "fixed_start_times_str": ["8:00 AM", "9:00 AM", "10:00 AM", "11:00 AM", "1:00 PM", "2:00 PM", "3:00 PM"]
    },
    "1611": {
        "slot_duration_minutes": 15,
        "overall_start_time_str": "8:00 AM",
        "overall_end_time_str": "4:30 PM",
        "break_time_str": ("12:00 PM", "1:00 PM"),
        "generate_all_intervals": True
    }
}

urls = {
    "1731": "https://lms2.ai.saveetha.in/mod/scheduler/view.php?id=36638",
    "1851": "https://lms2.ai.saveetha.in/mod/scheduler/view.php?id=36298",
    "1852": "https://lms2.ai.saveetha.in/mod/scheduler/view.php?id=37641",
    "1611": "https://lms2.ai.saveetha.in/mod/scheduler/view.php?id=36137"
}

def check_lms_connectivity(max_retries=3, delay=2):
    lms_url = "https://lms2.ai.saveetha.in/"
    st.session_state.status = "Checking LMS connectivity..."
    for attempt in range(max_retries):
        try:
            response = requests.get(lms_url, timeout=5)
            if response.status_code == 200 and "login" in response.text.lower():
                st.session_state.status = f"LMS login page is accessible (Attempt {attempt + 1}/{max_retries})."
                return True
            elif response.status_code == 200:
                st.session_state.status = f"LMS URL accessible but login page not found (Attempt {attempt + 1}/{max_retries})."
            else:
                st.session_state.status = f"LMS URL returned status code: {response.status_code} (Attempt {attempt + 1}/{max_retries})."
        except requests.exceptions.RequestException as e:
            st.session_state.status = f"Failed to connect to LMS URL: {e} (Attempt {attempt + 1}/{max_retries})."
        if attempt < max_retries - 1:
            time.sleep(delay)
    st.session_state.status = "LMS URL is not accessible after maximum retries."
    return False

def normalize_time(time_str):
    try:
        dt = parser.parse(time_str, fuzzy=True)
        return dt.strftime("%I:%M %p").lstrip('0').replace(' 0', ' ').replace(':00 ', ':00').replace('AM', ' AM').replace('PM', ' PM')
    except ValueError:
        return time_str

def _generate_interval_start_times(overall_start_dt, overall_end_dt, interval_m, break_start_dt, break_end_dt):
    times = []
    current_time = overall_start_dt
    while current_time < overall_end_dt:
        is_during_break = False
        if break_start_dt and break_end_dt:
            if break_start_dt <= current_time < break_end_dt:
                is_during_break = True
        if not is_during_break:
            times.append(current_time.strftime("%I:%M %p").lstrip('0').replace(' 0', ' ').replace(':00 ', ':00').replace('AM', ' AM').replace('PM', ' PM'))
        current_time += timedelta(minutes=interval_m)
        if break_start_dt and break_end_dt and break_start_dt <= current_time < break_end_dt:
            current_time = break_end_dt
    return times

def slot_booking_process(username, password, day, date, start_time, end_time, scheduler_url, proxy, headless, continuous=False, check_until_time=None):
    try:
        st.session_state.status = "Initializing browser..."
        options = ChromeOptions()
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=800,600")
        if proxy and re.match(r'^(http|https|socks5)://[\w\.-]+:\d+$', proxy):
            options.add_argument(f'--proxy-server={proxy}')

        driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=options)
        driver.set_page_load_timeout(30)
        driver.implicitly_wait(1.0)
        try:
            st.session_state.status = "Logging in..."
            driver.get("https://lms2.ai.saveetha.in/course/view.php?id=302")
            username_field = WebDriverWait(driver, 8, poll_frequency=0.5).until(
                EC.presence_of_element_located((By.NAME, 'username'))
            )
            username_field.send_keys(username)
            driver.find_element(By.NAME, 'password').send_keys(password)
            driver.find_element(By.ID, 'loginbtn').click()
            try:
                date_obj = datetime.strptime(date.strip(), "%d %m %Y")
                formatted_date_for_comparison = date_obj.strftime("%A, %d %B %Y")
            except ValueError:
                st.error(f"Invalid date format: {date}")
                return
            normalized_start_time = normalize_time(start_time)
            normalized_end_time = normalize_time(end_time)
            st.session_state.status = f"Looking for slot: {formatted_date_for_comparison}, {normalized_start_time}-{normalized_end_time}"
            found_slot = False
            attempt = 0
            refresh_interval = 2.0 if continuous else 1.0
            deadline = None
            if check_until_time and continuous:
                try:
                    deadline_dt = parser.parse(check_until_time)
                    deadline = datetime.now().replace(hour=deadline_dt.hour, minute=deadline_dt.minute, second=0, microsecond=0)
                    if deadline < datetime.now():
                        deadline = deadline + timedelta(days=1)
                except ValueError:
                    st.error(f"Invalid time format for 'Check Until Time': {check_until_time}")
                    return
            while not found_slot and not scheduler_stop_event.is_set():
                attempt += 1
                st.session_state.status = f"Attempt {attempt}: Checking slot..."
                if deadline and datetime.now() > deadline:
                    st.error(f"Deadline {deadline.strftime('%H:%M:%S')} reached.")
                    return
                driver.get(scheduler_url)
                if "503 Service Unavailable" in driver.page_source:
                    time.sleep(refresh_interval)
                    continue
                try:
                    table = WebDriverWait(driver, 5, poll_frequency=1.0).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "table#slotbookertable"))
                    )
                except TimeoutException:
                    continue
                try:
                    cancel_button = driver.find_element(By.XPATH, "//button[contains(@class, 'btn') and contains(text(), 'Cancel booking')]")
                    st.warning("Existing booking found.")
                    return
                except NoSuchElementException:
                    pass
                all_rows = driver.find_elements(By.CSS_SELECTOR, "table#slotbookertable tbody tr")
                current_date = ""
                for row in all_rows:
                    try:
                        cells = row.find_elements(By.TAG_NAME, 'td')
                        if len(cells) < 8:
                            continue
                        date_cell = cells[0].text.strip()
                        if date_cell:
                            current_date = date_cell
                        if current_date == formatted_date_for_comparison:
                            table_start = normalize_time(cells[1].text.strip())
                            table_end = normalize_time(cells[2].text.strip())
                            if normalized_start_time == table_start and normalized_end_time == table_end:
                                book_button = cells[7].find_element(By.XPATH, ".//button[contains(text(), 'Book slot')]")
                                if book_button.is_enabled():
                                    ActionChains(driver).move_to_element(book_button).click().perform()
                                    note_field = WebDriverWait(driver, 5).until(
                                        EC.presence_of_element_located((By.ID, "id_studentnote_editoreditable"))
                                    )
                                    note_field.send_keys("Booking for project work")
                                    submit_button = WebDriverWait(driver, 2).until(
                                        EC.element_to_be_clickable((By.ID, "id_submitbutton"))
                                    )
                                    submit_button.click()
                                    try:
                                        WebDriverWait(driver, 8).until(
                                            EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'confirmed')]"))
                                        )
                                        st.success(f"Slot booked successfully: {day}, {date}, {start_time}-{end_time}")
                                        return
                                    except TimeoutException:
                                        st.warning("Booking status unclear. Please verify manually.")
                                        return
                    except (StaleElementReferenceException, ElementClickInterceptedException):
                        break
                    except Exception as e:
                        st.error(f"Error processing row: {e}")
                        continue
                if not found_slot and not continuous:
                    st.error(f"Slot not found for {day}, {date}, {normalized_start_time}-{normalized_end_time}.")
                    return
                time.sleep(refresh_interval)
        finally:
            try:
                driver.quit()
            except:
                pass
            cleanup_memory()
    except Exception as e:
        st.error(f"An unexpected error occurred: {e}")
        st.session_state.status = f"Unexpected error: {e}"

def add_slot(date_input_str, start_time, schedule_id):
    try:
        date_obj = datetime.strptime(date_input_str, "%Y-%m-%d")
        day = date_obj.strftime("%A")
    except ValueError:
        st.error("Please select a valid date.")
        return
    end_time = st.session_state.end_time
    if not all([day, date_input_str, start_time, end_time]):
        st.error("Please fill in all slot fields.")
        return
    selected_venue_id = schedule_id
    if selected_venue_id in venue_details:
        config = venue_details[selected_venue_id]
        expected_start_times = []
        if "fixed_start_times_str" in config:
            expected_start_times = config["fixed_start_times_str"]
        elif "generate_all_intervals" in config and config["generate_all_intervals"]:
            overall_start_dt = parser.parse(config["overall_start_time_str"])
            overall_end_dt = parser.parse(config["overall_end_time_str"])
            break_start_dt = parser.parse(config["break_time_str"][0]) if config["break_time_str"] else None
            break_end_dt = parser.parse(config["break_time_str"][1]) if config["break_time_str"] else None
            expected_start_times = _generate_interval_start_times(
                overall_start_dt, overall_end_dt, config["slot_duration_minutes"],
                break_start_dt, break_end_dt
            )
        normalized_selected_start_time = normalize_time(start_time)
        if normalized_selected_start_time not in [normalize_time(t) for t in expected_start_times]:
            st.error(f"The selected start time '{start_time}' is not valid for venue {selected_venue_id}.")
            return
    slot = {
        "day": day,
        "date": date_obj.strftime("%d %m %Y"),
        "start_time": start_time,
        "end_time": end_time,
        "venue_id": selected_venue_id
    }
    st.session_state.slot_details.append(slot)
    st.session_state.slots_display.append(
        f"Venue: {selected_venue_id}, Day: {day}, Date: {slot['date']}, "
        f"Start: {start_time}, End: {end_time}"
    )
    st.success("Slot added successfully!")

def remove_slot(index):
    if index < len(st.session_state.slot_details):
        st.session_state.slot_details.pop(index)
        st.session_state.slots_display.pop(index)
        st.rerun()

def stop_process():
    global scheduled_time, scheduler_thread
    schedule.clear()
    scheduler_stop_event.set()
    scheduled_time = None
    st.session_state.status = "Stopping all processes..."
    st.session_state.scheduler_thread_running = False
    st.success("All booking processes and schedules stopped.")
    st.session_state.status = "Status: Stopped"

def run_booking(continuous=False):
    username = st.session_state.username
    password = st.session_state.password
    choice = st.session_state.schedule_venue_id
    headless = st.session_state.headless
    proxies = [p.strip() for p in st.session_state.proxies.split(",") if p.strip()]
    check_until = st.session_state.check_until or None
    if choice not in urls:
        st.error("Invalid schedule selected.")
        return
    if not st.session_state.slot_details:
        st.error("Please add at least one slot to book.")
        return
    if not username or not password:
        st.error("Please enter your username and password.")
        return
    #if not check_lms_connectivity():
     #   st.error("Cannot proceed with booking due to LMS connectivity issues.")
      #  return
    scheduler_url = urls[choice]
    max_concurrent_threads = min(2, len(st.session_state.slot_details))
    for batch_start in range(0, len(st.session_state.slot_details), max_concurrent_threads):
        batch_end = min(batch_start + max_concurrent_threads, len(st.session_state.slot_details))
        batch_threads = []
        for i in range(batch_start, batch_end):
            slot = st.session_state.slot_details[i]
            proxy = proxies[i % len(proxies)] if proxies else None
            slot_scheduler_url = urls.get(slot["venue_id"], scheduler_url)
            thread = threading.Thread(
                target=slot_booking_process,
                args=(
                    username, password, slot["day"], slot["date"],
                    slot["start_time"], slot["end_time"], slot_scheduler_url,
                    proxy, headless, continuous, check_until
                )
            )
            batch_threads.append(thread)
            thread.start()
        for thread in batch_threads:
            thread.join()
            time.sleep(0.5)
        cleanup_memory()
    st.session_state.status = f"Booking process completed for {len(st.session_state.slot_details)} slots."

def schedule_booking(schedule_time_str):
    global scheduled_time, scheduler_thread
    try:
        schedule_dt = parser.parse(schedule_time_str, fuzzy=False)
        if not (0 <= schedule_dt.hour <= 23 and 0 <= schedule_dt.minute <= 59):
            raise ValueError("Invalid time")
        schedule_time_formatted = schedule_dt.strftime("%H:%M")
        schedule.clear()
        scheduler_stop_event.clear()
        scheduled_time = schedule_time_formatted
        schedule.every().day.at(schedule_time_formatted).do(
            lambda: run_booking(continuous=True)
        )
        st.success(f"Booking scheduled daily at {schedule_time_formatted}")
        st.session_state.status = f"Status: Scheduled daily at {schedule_time_formatted}"
        if not st.session_state.get('scheduler_thread_running', False):
            def run_schedule_continuously():
                while not scheduler_stop_event.is_set():
                    schedule.run_pending()
                    time.sleep(5)
            scheduler_thread = threading.Thread(
                target=run_schedule_continuously,
                daemon=True
            )
            scheduler_thread.start()
            st.session_state.scheduler_thread_running = True
    except ValueError:
        st.error("Invalid time format. Use HH:MM (e.g., 21:03).")
        st.session_state.status = "Error: Invalid schedule time format."

def init_session_state():
    defaults = {
        'slot_details': [],
        'slots_display': [],
        'status': "Status: Idle",
        'start_time_options': [],
        'end_time': "",
        'schedule_venue_id': list(venue_details.keys())[0],
        'username': "",
        'password': "",
        'proxies': "",
        'schedule_time': "",
        'check_until': "",
        'headless': True,
        'date_input_value': datetime.today(),
        'scheduler_thread_running': False
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

def main():
    st.title("Enhanced Slot Booking Bot - Saveetha LMS")
    st.markdown("---")
    init_session_state()
    st.warning("Note: Passwords are stored in plain text in session state. For production use, consider using a secure credential management system.")
    st.subheader("User Credentials")
    username = st.text_input("Username", value=st.session_state.username, key="username_input")
    password = st.text_input("Password", type="password", value=st.session_state.password, key="password_input")
    st.session_state.username = username
    st.session_state.password = password
    st.markdown("---")
    st.subheader("Bot Configuration")
    schedule_venue_id = st.selectbox(
        "Select Venue Schedule",
        list(venue_details.keys()),
        index=list(venue_details.keys()).index(st.session_state.schedule_venue_id),
        key="schedule_venue_id_select"
    )
    proxies = st.text_input(
        "Proxies (comma-separated)",
        value=st.session_state.proxies,
        key="proxies_input"
    )
    schedule_time = st.text_input(
        "Schedule Time (HH:MM)",
        value=st.session_state.schedule_time,
        key="schedule_time_input"
    )
    check_until = st.text_input(
        "Check Until Time (HH:MM, optional)",
        value=st.session_state.check_until,
        key="check_until_input"
    )
    headless = st.checkbox(
        "Run Headless",
        value=st.session_state.headless,
        key="headless_input"
    )
    st.session_state.schedule_venue_id = schedule_venue_id
    st.session_state.proxies = proxies
    st.session_state.schedule_time = schedule_time
    st.session_state.check_until = check_until
    st.session_state.headless = headless
    st.markdown("---")
    st.subheader("Add Slot Details")
    date_input = st.date_input(
        "Select Date",
        min_value=datetime.today(),
        value=st.session_state.date_input_value,
        key="date_input_field"
    )
    st.session_state.date_input_value = date_input
    day_auto_filled = date_input.strftime("%A")
    st.text_input("Day (Auto-filled)", value=day_auto_filled, disabled=True)
    if schedule_venue_id in venue_details:
        config = venue_details[schedule_venue_id]
        overall_start_dt = parser.parse(config["overall_start_time_str"])
        overall_end_dt = parser.parse(config["overall_end_time_str"])
        break_start_dt = parser.parse(config["break_time_str"][0]) if config["break_time_str"] else None
        break_end_dt = parser.parse(config["break_time_str"][1]) if config["break_time_str"] else None
        if "fixed_start_times_str" in config:
            st.session_state.start_time_options = config["fixed_start_times_str"]
        elif "generate_all_intervals" in config and config["generate_all_intervals"]:
            st.session_state.start_time_options = _generate_interval_start_times(
                overall_start_dt, overall_end_dt,
                config["slot_duration_minutes"],
                break_start_dt, break_end_dt
            )
    else:
        st.session_state.start_time_options = []
    start_time = st.selectbox("Start Time", st.session_state.start_time_options)
    if start_time and schedule_venue_id in venue_details:
        config = venue_details[schedule_venue_id]
        try:
            start_dt_obj = parser.parse(start_time)
            overall_end_dt = parser.parse(config["overall_end_time_str"])
            potential_end_dt_obj = start_dt_obj + timedelta(minutes=config["slot_duration_minutes"])
            actual_end_dt_obj = min(potential_end_dt_obj, overall_end_dt)
            st.session_state.end_time = actual_end_dt_obj.strftime("%I:%M %p").lstrip('0').replace(' 0', ' ').replace(':00 ', ':00').replace('AM', ' AM').replace('PM', ' PM')
        except ValueError:
            st.session_state.end_time = "Invalid Time"
    else:
        st.session_state.end_time = ""
    st.text_input("End Time (Auto-calculated)", value=st.session_state.end_time, disabled=True)
    if st.button("Add Slot to List"):
        add_slot(date_input.strftime("%Y-%m-%d"), start_time, schedule_venue_id)
    st.markdown("---")
    st.subheader("Current Booking Slots")
    if st.session_state.slots_display:
        for i, slot_display_str in enumerate(st.session_state.slots_display):
            col1, col2 = st.columns([4, 1])
            col1.write(slot_display_str)
            if col2.button("Remove", key=f"remove_slot_{i}"):
                remove_slot(i)
    else:
        st.info("No slots added yet. Add slots above to see them here.")
    st.markdown("---")
    st.subheader("Actions")
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("Book Slots Now"):
            run_booking(continuous=True)
    with col2:
        if st.button("Schedule Daily"):
            schedule_booking(schedule_time)
    with col3:
        if st.button("Stop All"):
            stop_process()
    st.markdown("---")
    if st.checkbox("Show Performance Info"):
        col1, col2 = st.columns(2)
        with col1:
            memory_usage = get_memory_usage()
            if memory_usage:
                st.metric("Memory Usage", f"{memory_usage:.1f} MB")
                if memory_usage > 800:
                    st.warning("⚠️ High memory usage detected!")
            else:
                st.info("Memory monitoring not available")
        with col2:
            if st.button("Force Memory Cleanup"):
                cleanup_memory()
                st.success("Memory cleanup performed")
    st.subheader("Current Status")
    st.write(st.session_state.status)

if __name__ == "__main__":
    main()
