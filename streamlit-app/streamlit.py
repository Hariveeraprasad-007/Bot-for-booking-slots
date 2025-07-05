import streamlit as st
import threading
import time
import gc  # For explicit garbage collection
import os  # For memory monitoring
from datetime import datetime, timedelta
import re
import schedule
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import StaleElementReferenceException, NoSuchElementException, TimeoutException, ElementClickInterceptedException
import requests
from webdriver_manager.chrome import ChromeDriverManager
from dateutil import parser

# Performance optimization: Set cache for webdriver manager to reduce startup time
os.environ['WDM_LOG_LEVEL'] = '0'  # Reduce webdriver manager logging
os.environ['WDM_PRINT_FIRST_LINE'] = 'False'

# Memory management function
def cleanup_memory():
    """Force garbage collection to free up memory"""
    gc.collect()
    
# Performance monitoring
def get_memory_usage():
    """Get current memory usage in MB (Unix only)"""
    try:
        import psutil
        process = psutil.Process(os.getpid())
        return process.memory_info().rss / 1024 / 1024  # Convert to MB
    except ImportError:
        return None

# Global for scheduled time and scheduler thread control
scheduled_time = None
scheduler_thread = None
scheduler_stop_event = threading.Event()

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
        if headless:
            options.add_argument("--headless=new")
        
        # Memory optimization for cloud environment
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-plugins")
        options.add_argument("--disable-images")
        # options.add_argument("--disable-javascript")  # Commented out - might be needed for booking
        options.add_argument("--disable-css-backgrounds")
        options.add_argument("--disable-background-timer-throttling")
        options.add_argument("--disable-backgrounding-occluded-windows")
        options.add_argument("--disable-renderer-backgrounding")
        options.add_argument("--disable-features=TranslateUI")
        options.add_argument("--disable-features=VizDisplayCompositor")
        
        # Minimal window size for memory efficiency
        options.add_argument("--window-size=800,600")
        
        # Faster page loading strategy
        options.add_argument("--page-load-strategy=none")
        
        # Memory management
        options.add_argument("--memory-pressure-off")
        options.add_argument("--max_old_space_size=512")
        
        # Disable unnecessary features
        options.add_experimental_option("prefs", {
            "profile.managed_default_content_settings.images": 2,
            "profile.default_content_settings.popups": 0,
            "profile.managed_default_content_settings.media_stream": 2,
            "profile.managed_default_content_settings.notifications": 2
        })
        
        if proxy and re.match(r'^(http|https|socks5)://[\w\.-]+:\d+$', proxy):
            options.add_argument(f'--proxy-server={proxy}')
        elif proxy:
            st.warning(f"Invalid proxy format: {proxy}. Proceeding without proxy.")
            st.session_state.status = f"Warning: Invalid proxy format: {proxy}. Proceeding without proxy."

        with webdriver.Chrome(service=webdriver.chrome.service.Service(ChromeDriverManager().install()), options=options) as driver:
            # Optimized implicit wait for cloud environment
            driver.implicitly_wait(1.0)  # Reduced from default
            
            # Set page load timeout to prevent hanging
            driver.set_page_load_timeout(30)
            
            st.session_state.status = "Logging in..."
            driver.get("https://lms2.ai.saveetha.in/course/view.php?id=302")
            try:
                # Reduced wait time and optimized polling for cloud
                username_field = WebDriverWait(driver, 8, poll_frequency=0.5).until(
                    EC.presence_of_element_located((By.NAME, 'username'))
                )
                username_field.send_keys(username)
                driver.find_element(By.NAME, 'password').send_keys(password)
                driver.find_element(By.ID, 'loginbtn').click()
                st.session_state.status = "Logged in."
            except TimeoutException as e:
                st.error(f"Login timeout: {e}. Fields not found.")
                st.session_state.status = f"Error: Login failed, fields not found."
                return
            except NoSuchElementException:
                st.session_state.status = "Already logged in or login elements not present. Continuing..."

            try:
                date_obj = datetime.strptime(date.strip(), "%d %m %Y")
                formatted_date_for_comparison = date_obj.strftime("%A, %d %B %Y")
            except ValueError:
                st.error(f"Invalid date format: {date}. Expected format: DD MM YYYY")
                st.session_state.status = f"Error: Invalid date format provided."
                return

            normalized_start_time = normalize_time(start_time)
            normalized_end_time = normalize_time(end_time)
            st.session_state.status = f"Looking for slot: {formatted_date_for_comparison}, {normalized_start_time}-{normalized_end_time}"

            found_slot = False
            attempt = 0
            # Increased refresh interval for cloud efficiency (reduced CPU usage)
            refresh_interval = 2.0 if continuous else 1.0  # Slower polling to reduce CPU load

            deadline = None
            if check_until_time and continuous:
                try:
                    deadline_dt = parser.parse(check_until_time)
                    deadline = datetime.now().replace(hour=deadline_dt.hour, minute=deadline_dt.minute, second=0, microsecond=0)
                    if deadline < datetime.now():
                        deadline = deadline + timedelta(days=1)
                    st.session_state.status = f"Will check until {deadline.strftime('%H:%M:%S')}"
                except ValueError:
                    st.error(f"Invalid time format for 'Check Until Time': {check_until_time}. Use HH:MM (e.g., 21:30).")
                    st.session_state.status = f"Error: Invalid 'Check Until Time' format."
                    return

            while not found_slot and not scheduler_stop_event.is_set():
                attempt += 1
                st.session_state.status = f"Attempt {attempt}: Checking slot..."
                
                if deadline and datetime.now() > deadline:
                    st.error(f"Deadline {deadline.strftime('%H:%M:%S')} reached. Stopping continuous check.")
                    st.session_state.status = f"Deadline reached. Stopping."
                    return

                driver.get(scheduler_url)
                page_source = driver.page_source
                if any(error in page_source for error in ["503 Service Unavailable", "Service Temporarily Unavailable", "ERR_CONNECTION_REFUSED"]):
                    st.session_state.status = f"Server error detected. Retrying... (Attempt {attempt})"
                    time.sleep(refresh_interval)
                    continue

                try:
                    # Optimized wait with longer timeout but less frequent polling
                    WebDriverWait(driver, 5, poll_frequency=1.0).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "table#slotbookertable, table.generaltable"))
                    )
                except TimeoutException:
                    st.session_state.status = f"Table not loaded within 5 seconds. Retrying... (Attempt {attempt})"
                    time.sleep(refresh_interval)
                    continue

                # Quick checks for existing booking and frozen slots
                try:
                    WebDriverWait(driver, 1.0).until(
                        EC.presence_of_element_located((By.XPATH, "//button[contains(@class, 'btn') and contains(text(), 'Cancel booking')]"))
                    )
                    st.warning("Existing booking found. Please cancel it manually to book a new slot.")
                    st.session_state.status = "Existing booking found."
                    return
                except TimeoutException:
                    pass

                try:
                    WebDriverWait(driver, 1.0).until(
                        EC.presence_of_element_located((By.XPATH, "//th[contains(text(), 'Other participants')]"))
                    )
                    st.warning("Frozen slot detected. Please resolve this manually to book a new slot.")
                    st.session_state.status = "Frozen slot detected."
                    return
                except TimeoutException:
                    pass

                # Optimized row collection with reduced polling frequency
                all_rows = WebDriverWait(driver, 3, poll_frequency=0.5).until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, "table#slotbookertable tbody tr"))
                )
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
                            parsed_table_date = parser.parse(current_date_in_table)
                        except ValueError:
                            continue

                        if parsed_table_date.date() == date_obj.date():
                            table_start_time = normalize_time(cells[1].text.strip())
                            table_end_time = normalize_time(cells[2].text.strip())

                            if normalized_start_time == table_start_time and normalized_end_time == table_end_time:
                                st.session_state.status = f"Found target slot: {table_start_time}-{table_end_time}"
                                try:
                                    book_button = cells[7].find_element(By.XPATH, ".//button[contains(text(), 'Book slot')]")
                                    if book_button.is_enabled():
                                        ActionChains(driver).move_to_element(book_button).click().perform()
                                        found_slot = True
                                        st.session_state.status = "Book slot button clicked."
                                        try:
                                            # Optimized booking confirmation with reduced waits
                                            note_field = WebDriverWait(driver, 5, poll_frequency=0.5).until(
                                                EC.visibility_of_element_located((By.ID, "id_studentnote_editoreditable"))
                                            )
                                            note_field.send_keys("Booking for project work (automated)")
                                            submit_button = WebDriverWait(driver, 2, poll_frequency=0.5).until(
                                                EC.element_to_be_clickable((By.ID, "id_submitbutton"))
                                            )
                                            submit_button.click()
                                            st.session_state.status = "Note added and submit button clicked."
                                            
                                            try:
                                                # Reduced confirmation wait time
                                                WebDriverWait(driver, 8, poll_frequency=0.5).until(
                                                    EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'confirmed') or contains(text(), 'success') or contains(text(), 'Your booking is confirmed')]"))
                                                )
                                                st.success(f"Slot booked successfully: {day}, {date}, {start_time}-{end_time}")
                                                st.session_state.status = f"Slot booked successfully: {day}, {date}, {start_time}-{end_time}"
                                                return
                                            except TimeoutException:
                                                try:
                                                    # Fallback verification with optimized timing
                                                    WebDriverWait(driver, 3, poll_frequency=0.5).until(
                                                        EC.presence_of_element_located((By.XPATH, f"//tr[td[contains(text(), '{formatted_date_for_comparison}')]][td[contains(text(), '{normalized_start_time}')] and td[contains(text(), '{normalized_end_time}')]]//button[contains(text(), 'Cancel booking')]"))
                                                    )
                                                    st.success(f"Slot booked: {day}, {date}, {start_time}-{end_time} (Verified by 'Cancel booking' button)")
                                                    st.session_state.status = f"Slot booked: {day}, {date}, {start_time}-{end_time} (Verified)"
                                                    return
                                                except TimeoutException:
                                                    st.warning(f"Slot booked, but confirmation message not found. Please verify manually for: {day}, {date}, {start_time}-{end_time}")
                                                    st.session_state.status = f"Slot booked: {day}, {date}, {start_time}-{end_time} (Verify manually)"
                                                    return
                                        except TimeoutException as te:
                                            st.error(f"Failed to interact with note field or submit button: {te}")
                                            st.session_state.status = f"Error: Booking form interaction failed."
                                            return
                                    else:
                                        st.session_state.status = "Book slot button is disabled. Retrying..."
                                        break
                                except (NoSuchElementException, ElementClickInterceptedException) as e:
                                    st.error(f"Button interaction error: {e}. Retrying...")
                                    st.session_state.status = f"Error: Button interaction failed. Retrying..."
                                    break
                    except StaleElementReferenceException:
                        st.session_state.status = "Stale element detected, refreshing page and retrying..."
                        break
                    except Exception as e:
                        st.error(f"Error processing row: {e}")
                        st.session_state.status = f"Error: Row processing failed. Retrying..."
                        continue

                if not found_slot and not continuous:
                    st.error(f"Slot not found for {day}, {date}, {normalized_start_time}-{normalized_end_time}.")
                    st.session_state.status = f"Slot not found: {day}, {date}, {normalized_start_time}-{normalized_end_time}."
                    return
                
                if not found_slot:
                    time.sleep(refresh_interval)

    except Exception as e:
        st.error(f"An unexpected error occurred during the booking process: {e}")
        st.session_state.status = f"Unexpected error: {e}"
    finally:
        # Clean up memory after booking process
        cleanup_memory()

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

    slot = {"day": day, "date": date_obj.strftime("%d %m %Y"), "start_time": start_time, "end_time": end_time, "venue_id": selected_venue_id}
    st.session_state.slot_details.append(slot)
    st.session_state.slots_display.append(f"Venue: {selected_venue_id}, Day: {day}, Date: {slot['date']}, Start: {start_time}, End: {end_time}")
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
        st.session_state.status = "Error: Invalid schedule selected."
        return
    if not st.session_state.slot_details:
        st.error("Please add at least one slot to book.")
        st.session_state.status = "Error: No slots added."
        return
    if not username or not password:
        st.error("Please enter your username and password.")
        st.session_state.status = "Error: Missing credentials."
        return
    
    if not check_lms_connectivity():
        st.error("Cannot proceed with booking due to LMS connectivity issues.")
        st.session_state.status = "Error: LMS connectivity failed."
        return

    scheduler_url = urls[choice]
    
    current_booking_threads = []
    
    # Limit concurrent threads on single core cloud environment
    max_concurrent_threads = min(2, len(st.session_state.slot_details))  # Maximum 2 concurrent threads
    
    # Process slots in batches to avoid memory pressure
    for batch_start in range(0, len(st.session_state.slot_details), max_concurrent_threads):
        batch_end = min(batch_start + max_concurrent_threads, len(st.session_state.slot_details))
        batch_threads = []
        
        for i in range(batch_start, batch_end):
            slot = st.session_state.slot_details[i]
            proxy = proxies[i % len(proxies)] if proxies else None
            slot_scheduler_url = urls.get(slot["venue_id"], scheduler_url)

            thread = threading.Thread(target=slot_booking_process, args=(
                username, password, slot["day"], slot["date"], slot["start_time"], slot["end_time"],
                slot_scheduler_url, proxy, headless, continuous, check_until
            ))
            batch_threads.append(thread)
            current_booking_threads.append(thread)
            thread.start()
        
        # Wait for current batch to complete before starting next batch
        for thread in batch_threads:
            thread.join()
            # Small delay between thread completions to reduce resource pressure
            time.sleep(0.5)
            
        # Clean up memory after each batch
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
        
        schedule.every().day.at(schedule_time_formatted).do(lambda: run_booking(continuous=True))
        
        st.success(f"Booking scheduled daily at {schedule_time_formatted}")
        st.session_state.status = f"Status: Scheduled daily at {schedule_time_formatted}"

        def run_schedule_continuously():
            while not scheduler_stop_event.is_set():
                schedule.run_pending()
                # Increased sleep interval to reduce CPU usage on single core
                time.sleep(5)  # Check every 5 seconds instead of 1 second
        
        if not hasattr(st.session_state, 'scheduler_thread_running') or not st.session_state.scheduler_thread_running:
            scheduler_thread = threading.Thread(target=run_schedule_continuously, daemon=True)
            scheduler_thread.start()
            st.session_state.scheduler_thread_running = True
            st.session_state.status = "Scheduler daemon thread started."

    except ValueError:
        st.error("Invalid time format. Use HH:MM (e.g., 21:03).")
        st.session_state.status = "Error: Invalid schedule time format."

# Streamlit UI
st.title("Enhanced Slot Booking Bot - Saveetha LMS")
st.markdown("---")

# Security warning
st.warning("Note: Passwords are stored in plain text in session state. For production use, consider using a secure credential management system.")

# Initialize session state defaults
if 'slot_details' not in st.session_state:
    st.session_state.slot_details = []
if 'slots_display' not in st.session_state:
    st.session_state.slots_display = []
if 'status' not in st.session_state:
    st.session_state.status = "Status: Idle"
if 'start_time_options' not in st.session_state:
    st.session_state.start_time_options = []
if 'end_time' not in st.session_state:
    st.session_state.end_time = ""
if 'schedule_venue_id' not in st.session_state:
    st.session_state.schedule_venue_id = list(venue_details.keys())[0]
if 'username' not in st.session_state:
    st.session_state.username = ""
if 'password' not in st.session_state:
    st.session_state.password = ""
if 'proxies' not in st.session_state:
    st.session_state.proxies = ""
if 'schedule_time' not in st.session_state:
    st.session_state.schedule_time = ""
if 'check_until' not in st.session_state:
    st.session_state.check_until = ""
if 'headless' not in st.session_state:
    st.session_state.headless = True
if 'date_input_value' not in st.session_state:
    st.session_state.date_input_value = datetime.today()
if 'scheduler_thread_running' not in st.session_state:
    st.session_state.scheduler_thread_running = False

# Credentials
st.subheader("User Credentials")
username = st.text_input("Username", value=st.session_state.username, key="username_input", help="Your Saveetha LMS username.")
password = st.text_input("Password", type="password", value=st.session_state.password, key="password_input", help="Your Saveetha LMS password.")
st.session_state.username = username
st.session_state.password = password

st.markdown("---")

# Configuration
st.subheader("Bot Configuration")
schedule_venue_id = st.selectbox("Select Venue Schedule", list(venue_details.keys()), index=list(venue_details.keys()).index(st.session_state.schedule_venue_id), key="schedule_venue_id_select", help="Choose the venue for booking.")
proxies = st.text_input("Proxies (comma-separated, e.g., http://proxy1:port,http://proxy2:port)", value=st.session_state.proxies, key="proxies_input", help="Optional: Add proxy servers for booking.")
schedule_time = st.text_input("Schedule Time (HH:MM, e.g., 21:03)", value=st.session_state.schedule_time, key="schedule_time_input", help="Set a specific time for daily automated booking.")
check_until = st.text_input("Check Until Time (HH:MM, e.g., 21:30, optional)", value=st.session_state.check_until, key="check_until_input", help="If continuous booking is enabled, the bot will stop checking after this time.")
headless = st.checkbox("Run Headless (Browser not visible, recommended for continuous refresh)", value=st.session_state.headless, key="headless_input")

st.session_state.schedule_venue_id = schedule_venue_id
st.session_state.proxies = proxies
st.session_state.schedule_time = schedule_time
st.session_state.check_until = check_until
st.session_state.headless = headless

st.markdown("---")

# Slot Details for Adding
st.subheader("Add Slot Details")
date_input = st.date_input("Select Date", min_value=datetime.today(), value=st.session_state.date_input_value, key="date_input_field")
st.session_state.date_input_value = date_input

day_auto_filled = date_input.strftime("%A")
st.text_input("Day (Auto-filled)", value=day_auto_filled, disabled=True, key="day_display")

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
            overall_start_dt, overall_end_dt, config["slot_duration_minutes"],
            break_start_dt, break_end_dt
        )
else:
    st.session_state.start_time_options = []

start_time = st.selectbox("Start Time", st.session_state.start_time_options, key="start_time_input", help="Select the start time for your booking slot.")

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

st.text_input("End Time (Auto-calculated)", value=st.session_state.end_time, disabled=True, key="end_time_input")

if st.button("Add Slot to List", key="add_slot_button"):
    add_slot(date_input.strftime("%Y-%m-%d"), start_time, schedule_venue_id)

st.markdown("---")

# Selected Slots Display
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

# Actions
st.subheader("Actions")
col_book, col_schedule, col_stop = st.columns(3)
with col_book:
    if st.button("Book Slots Now (Continuous Check)", key="book_now_button"):
        run_booking(continuous=True)
with col_schedule:
    if st.button("Schedule Daily Booking", key="schedule_booking_button"):
        schedule_booking(schedule_time)
with col_stop:
    if st.button("Stop All Processes", key="stop_process_button"):
        stop_process()

st.markdown("---")

# Performance monitoring (optimized for cloud)
if st.checkbox("Show Performance Info", value=False):
    col1, col2 = st.columns(2)
    with col1:
        memory_usage = get_memory_usage()
        if memory_usage:
            st.metric("Memory Usage", f"{memory_usage:.1f} MB")
            if memory_usage > 800:  # Warning if approaching 1GB limit
                st.warning("⚠️ High memory usage detected!")
        else:
            st.info("Memory monitoring not available")
    
    with col2:
        if st.button("Force Memory Cleanup"):
            cleanup_memory()
            st.success("Memory cleanup performed")

# Status Display
st.subheader("Current Status")
st.write(st.session_state.status)

# Important Note
st.markdown(
    """
    ---
    **Important Notes:**
    - **Scheduling/Continuous Booking**: This app uses Python's `threading` and `schedule` library for background tasks. This works locally, but in cloud deployments (e.g., Streamlit Community Cloud), threads may not persist due to Streamlit's process management. For production, use a dedicated task scheduler like Celery or Airflow.
    - **Session State**: In multi-user deployments, `st.session_state` may lead to race conditions. For production, consider a backend database or user-specific sessions.
    """
)
