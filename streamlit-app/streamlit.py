import streamlit as st
import threading
import time
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

# Global for scheduled time (used to prevent manual runs when scheduled)
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

# Check LMS connectivity with retries
def check_lms_connectivity(max_retries=3, delay=2):
    lms_url = "https://lms2.ai.saveetha.in/"
    st.session_state.status = "Checking LMS connectivity..."
    for attempt in range(max_retries):
        try:
            response = requests.get(lms_url, timeout=5)
            if response.status_code == 200:
                st.session_state.status = f"LMS URL is accessible (Attempt {attempt + 1}/{max_retries})."
                return True
            else:
                st.session_state.status = f"LMS URL returned status code: {response.status_code} (Attempt {attempt + 1}/{max_retries})"
        except requests.exceptions.RequestException as e:
            st.session_state.status = f"Failed to connect to LMS URL: {e} (Attempt {attempt + 1}/{max_retries})"
        if attempt < max_retries - 1:
            time.sleep(delay)
    st.session_state.status = "LMS URL is not accessible after maximum retries."
    return False

def _generate_interval_start_times(overall_start_dt, overall_end_dt, interval_m, break_start_dt, break_end_dt):
    times = []
    current_time = overall_start_dt
    while current_time < overall_end_dt:
        is_during_break = False
        if break_start_dt and break_end_dt:
            if break_start_dt <= current_time < break_end_dt:
                is_during_break = True
        
        if not is_during_break:
            times.append(current_time.strftime("%I:%M %p").lstrip('0').replace(' 0', ' ').replace(':00 ', ':00').replace('AM',' AM').replace('PM',' PM'))
        
        current_time += timedelta(minutes=interval_m)
        
        # If current_time falls into a break, jump to the end of the break
        if break_start_dt and break_end_dt and break_start_dt <= current_time < break_end_dt:
            current_time = break_end_dt
            
    return times

def slot_booking_process(username, password, day, date, start_time, end_time, scheduler_url, proxy, headless, continuous=False, check_until_time=None):
    driver = None
    try:
        st.session_state.status = "Initializing browser..."

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
        if proxy:
            options.add_argument(f'--proxy-server={proxy}')

        try:
            driver = webdriver.Chrome(options=options)
        except Exception as e:
            st.error(f"Failed to initialize Chrome driver: {e}")
            st.session_state.status = f"Error: Failed to initialize browser: {e}"
            return

        st.session_state.status = "Logging in..."
        driver.get("https://lms2.ai.saveetha.in/course/view.php?id=302")
        try:
            username_field = WebDriverWait(driver, 5, poll_frequency=0.1).until(EC.presence_of_element_located((By.NAME, 'username')))
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
            st.error(f"Invalid date format: {date}")
            st.session_state.status = f"Error: Invalid date format provided."
            return

        def normalize_time(time_str):
            # Remove leading zeros from hour part for single digit hours
            normalized = re.sub(r'\s+', ' ', time_str.strip()).replace(':00 ', ':00').replace('AM', ' AM').replace('PM', ' PM')
            # Handle cases like "08:00 AM" to "8:00 AM" if not already handled by lstrip
            if normalized.startswith('0') and ':' in normalized:
                parts = normalized.split(':')
                if len(parts[0]) == 2: # Check if it's a two-digit hour like "08"
                    normalized = parts[0].lstrip('0') + ':' + ':'.join(parts[1:])
            return normalized.replace("  ", " ") # Remove any double spaces

        normalized_start_time = normalize_time(start_time)
        normalized_end_time = normalize_time(end_time)
        st.session_state.status = f"Looking for slot: {formatted_date_for_comparison}, {normalized_start_time}-{normalized_end_time}"

        found_slot = False
        attempt = 0
        refresh_interval = 0.5 # seconds

        deadline = None
        if check_until_time and continuous:
            try:
                deadline_dt = datetime.strptime(check_until_time, "%H:%M")
                deadline = datetime.now().replace(hour=deadline_dt.hour, minute=deadline_dt.minute, second=0, microsecond=0)
                if deadline < datetime.now(): # If the time is in the past today, set for tomorrow
                    deadline = deadline + timedelta(days=1)
                st.session_state.status = f"Will check until {deadline.strftime('%H:%M:%S')}"
            except ValueError:
                st.error(f"Invalid time format for 'Check Until Time': {check_until_time}. Use HH:MM (e.g., 21:30).")
                st.session_state.status = f"Error: Invalid 'Check Until Time' format."
                return

        while not found_slot:
            attempt += 1
            st.session_state.status = f"Attempt {attempt}: Checking slot..."
            
            if deadline and datetime.now() > deadline:
                st.error(f"Deadline {deadline.strftime('%H:%M:%S')} reached. Stopping continuous check.")
                st.session_state.status = f"Deadline reached. Stopping."
                return

            driver.get(scheduler_url)
            page_source = driver.page_source
            if "503 Service Unavailable" in page_source or "Service Temporarily Unavailable" in page_source or "ERR_CONNECTION_REFUSED" in page_source:
                st.session_state.status = f"503 Error detected. Retrying... (Attempt {attempt})"
                time.sleep(refresh_interval)
                continue

            try:
                WebDriverWait(driver, 2).until(EC.presence_of_element_located((By.CSS_SELECTOR, "table#slotbookertable, table.generaltable")))
            except TimeoutException:
                st.session_state.status = f"Table not loaded within 2 seconds. Retrying... (Attempt {attempt})"
                time.sleep(refresh_interval)
                continue

            try:
                WebDriverWait(driver, 0.5).until(EC.presence_of_element_located((By.XPATH, "//button[contains(@class, 'btn') and contains(text(), 'Cancel booking')]")))
                st.warning("Existing booking found. Please cancel it manually to book a new slot.")
                st.session_state.status = "Existing booking found."
                return
            except TimeoutException:
                pass

            try:
                WebDriverWait(driver, 0.5).until(EC.presence_of_element_located((By.XPATH, "//th[contains(text(), 'Other participants')]")))
                st.warning("Frozen slot detected. Please resolve this manually to book a new slot.")
                st.session_state.status = "Frozen slot detected."
                return
            except TimeoutException:
                pass

            all_rows = WebDriverWait(driver, 1, poll_frequency=0.1).until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "table#slotbookertable tbody tr")))
            current_date_in_table = ""

            for row in all_rows:
                try:
                    cells = row.find_elements(By.TAG_NAME, 'td')
                    if len(cells) < 8: # A valid slot row should have at least 8 cells
                        continue

                    date_cell_text = cells[0].text.strip()
                    if date_cell_text: # If the date cell is not empty, it's a new date header
                        current_date_in_table = date_cell_text

                    try:
                        parsed_table_date = datetime.strptime(current_date_in_table, "%A, %d %B %Y")
                    except ValueError:
                        continue # Skip rows that don't have a valid date format

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
                                        note_field = WebDriverWait(driver, 3, poll_frequency=0.1).until(EC.visibility_of_element_located((By.ID, "id_studentnote_editoreditable")))
                                        note_field.send_keys("Booking for project work (automated)")
                                        submit_button = WebDriverWait(driver, 1, poll_frequency=0.1).until(EC.element_to_be_clickable((By.ID, "id_submitbutton")))
                                        submit_button.click()
                                        st.session_state.status = "Note added and submit button clicked."
                                        
                                        # Verify booking success
                                        try:
                                            WebDriverWait(driver, 5, poll_frequency=0.1).until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'confirmed') or contains(text(), 'success') or contains(text(), 'Your booking is confirmed')]")))
                                            st.success(f"Slot booked successfully: {day}, {date}, {start_time}-{end_time}")
                                            st.session_state.status = f"Slot booked successfully: {day}, {date}, {start_time}-{end_time}"
                                            return
                                        except TimeoutException:
                                            # If specific success message not found, try to verify by looking for the booked slot again
                                            try:
                                                WebDriverWait(driver, 2, poll_frequency=0.1).until(EC.presence_of_element_located((By.XPATH, f"//tr[td[contains(text(), '{formatted_date_for_comparison}')]][td[contains(text(), '{start_time}')] and td[contains(text(), '{end_time}')]]//button[contains(text(), 'Cancel booking')]")))
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
                                    break # Exit the inner loop to refresh the page
                            except (NoSuchElementException, ElementClickInterceptedException) as e:
                                st.error(f"Button interaction error: {e}. Retrying...")
                                st.session_state.status = f"Error: Button interaction failed. Retrying..."
                                break # Exit the inner loop to refresh the page
                except StaleElementReferenceException:
                    st.session_state.status = "Stale element detected, refreshing page and retrying..."
                    break # Break from inner loop to re-fetch rows
                except Exception as e:
                    st.error(f"Error processing row: {e}")
                    st.session_state.status = f"Error: Row processing failed. Retrying..."
                    continue # Try the next row

            if not found_slot and not continuous:
                st.error(f"Slot not found for {day}, {date}, {normalized_start_time}-{normalized_end_time}.")
                st.session_state.status = f"Slot not found: {day}, {date}, {normalized_start_time}-{normalized_end_time}."
                return
            
            if not found_slot:
                time.sleep(refresh_interval) # Wait before next attempt in continuous mode

    except Exception as e:
        st.error(f"An unexpected error occurred during the booking process: {e}")
        st.session_state.status = f"Unexpected error: {e}"
    finally:
        if driver:
            try:
                driver.quit()
                st.session_state.status = "Browser closed."
            except Exception as e:
                st.warning(f"Error closing driver: {e}")

def add_slot(date_input_str, start_time, schedule_id):
    try:
        date_obj = datetime.strptime(date_input_str, "%Y-%m-%d")
        day = date_obj.strftime("%A")
    except ValueError:
        st.error("Please select a valid date.")
        return

    end_time = st.session_state.end_time # This is already calculated and stored in session state

    if not all([day, date_input_str, start_time, end_time]):
        st.error("Please fill in all slot fields.")
        return

    selected_venue_id = schedule_id
    if selected_venue_id in venue_details:
        config = venue_details[selected_venue_id]
        
        # Ensure start_time is valid for the selected venue
        expected_start_times = []
        if "fixed_start_times_str" in config:
            expected_start_times = config["fixed_start_times_str"]
        elif "generate_all_intervals" in config and config["generate_all_intervals"]:
            overall_start_dt = datetime.strptime(config["overall_start_time_str"], "%I:%M %p")
            overall_end_dt = datetime.strptime(config["overall_end_time_str"], "%I:%M %p")
            break_start_dt = None
            break_end_dt = None
            if config["break_time_str"]:
                break_start_dt = datetime.strptime(config["break_time_str"][0], "%I:%M %p")
                break_end_dt = datetime.strptime(config["break_time_str"][1], "%I:%M %p")

            expected_start_times = _generate_interval_start_times(
                overall_start_dt, overall_end_dt, config["slot_duration_minutes"],
                break_start_dt, break_end_dt
            )
        
        # Normalize the input start time for comparison
        def normalize_time_for_check(time_str):
            dt_obj = datetime.strptime(time_str, "%I:%M %p")
            return dt_obj.strftime("%I:%M %p").lstrip('0').replace(' 0', ' ').replace(':00 ', ':00').replace('AM',' AM').replace('PM',' PM')

        normalized_selected_start_time = normalize_time_for_check(start_time)

        # Check if the normalized selected start time is in the list of expected start times
        if normalized_selected_start_time not in [normalize_time_for_check(t) for t in expected_start_times]:
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
        st.experimental_rerun() # Rerun to refresh the list displayed

def stop_process():
    schedule.clear()
    global scheduled_time
    scheduled_time = None
    st.session_state.status = "Stopping all processes..."
    
    # In a real deployed Streamlit app, directly stopping Selenium instances launched in threads
    # might not be fully reliable due to Streamlit's process management.
    # This part primarily works for local execution.
    st.success("All booking processes and schedules stopped.")
    st.session_state.status = "Status: Stopped"

def run_booking(continuous=False):
    global scheduled_time

    username = st.session_state.username
    password = st.session_state.schedule_venue_id # Use the session state variable for selected venue ID
    choice = st.session_state.schedule_venue_id # Renamed from 'choice' to be consistent with venue ID
    headless = st.session_state.headless
    proxies = [p.strip() for p in st.session_state.proxies.split(",") if p.strip()] # Clean proxies list
    check_until = st.session_state.check_until or None

    if choice not in urls:
        st.error("Invalid schedule selected.")
        st.session_state.status = "Error: Invalid schedule selected."
        return
    if not st.session_state.slot_details: # Check the actual slot data list
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
    
    # Using a list to hold threads to manage them, though direct stopping is hard in Streamlit
    current_booking_threads = [] 
    
    for i, slot in enumerate(st.session_state.slot_details):
        proxy = proxies[i % len(proxies)] if proxies else None
        
        # Pass the correct scheduler_url for the venue associated with the slot
        # This assumes each slot has a 'venue_id'
        slot_scheduler_url = urls.get(slot["venue_id"], scheduler_url) # Use slot's venue_id if available, otherwise default

        thread = threading.Thread(target=slot_booking_process, args=(
            username, password, slot["day"], slot["date"], slot["start_time"], slot["end_time"],
            slot_scheduler_url, proxy, headless, continuous, check_until
        ))
        current_booking_threads.append(thread)
        thread.start()
    
    st.session_state.status = "Booking process initiated. Check logs for updates."
    # Note: Threads run in the background. Streamlit UI won't block for them.
    # For a production app, you'd need a more robust background task runner.

def schedule_booking(schedule_time_str):
    global scheduled_time
    try:
        schedule_dt = datetime.strptime(schedule_time_str, "%H:%M")
        schedule.clear() # Clear any previous schedules
        scheduled_time = schedule_time_str # Store the scheduled time globally
        
        # Schedule the booking to run daily at the specified time
        schedule.every().day.at(schedule_time_str).do(lambda: run_booking(continuous=True))
        
        st.success(f"Booking scheduled daily at {schedule_time_str}")
        st.session_state.status = f"Status: Scheduled daily at {schedule_time_str}"

        # Start the scheduler in a separate daemon thread
        # This thread keeps running in the background to check and execute scheduled jobs
        def run_schedule_continuously():
            while True:
                schedule.run_pending()
                time.sleep(1) # Check every second
        
        if not hasattr(st.session_state, 'scheduler_thread_running') or not st.session_state.scheduler_thread_running:
            scheduler_thread = threading.Thread(target=run_schedule_continuously, daemon=True)
            scheduler_thread.start()
            st.session_state.scheduler_thread_running = True # Mark thread as running
            st.session_state.status = "Scheduler daemon thread started."

    except ValueError:
        st.error("Invalid time format. Use HH:MM (e.g., 21:03).")
        st.session_state.status = "Error: Invalid schedule time format."


# Streamlit UI
st.title("Enhanced Slot Booking Bot - Saveetha LMS")
st.markdown("---")

# Initialize session state defaults
if 'slot_details' not in st.session_state:
    st.session_state.slot_details = [] # Stores actual slot data
if 'slots_display' not in st.session_state:
    st.session_state.slots_display = [] # Stores formatted strings for display
if 'status' not in st.session_state:
    st.session_state.status = "Status: Idle"
if 'start_time_options' not in st.session_state:
    st.session_state.start_time_options = []
if 'end_time' not in st.session_state:
    st.session_state.end_time = ""
if 'schedule_venue_id' not in st.session_state: # Renamed for clarity from 'schedule'
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
if 'date_input_value' not in st.session_state: # To store the actual date object from date_input
    st.session_state.date_input_value = datetime.today()

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
st.session_state.date_input_value = date_input # Store the actual date object

# Automatically determine day
day_auto_filled = date_input.strftime("%A")
st.text_input("Day (Auto-filled)", value=day_auto_filled, disabled=True, key="day_display")

# Populate start time options based on selected venue
if schedule_venue_id in venue_details:
    config = venue_details[schedule_venue_id]
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
else:
    st.session_state.start_time_options = [] # Clear options if venue not found

start_time = st.selectbox("Start Time", st.session_state.start_time_options, key="start_time_input", help="Select the start time for your booking slot.")

# Auto-calculate and display end time
if start_time and schedule_venue_id in venue_details:
    config = venue_details[schedule_venue_id]
    try:
        start_dt_obj = datetime.strptime(start_time, "%I:%M %p")
        overall_end_dt = datetime.strptime(config["overall_end_time_str"], "%I:%M %p")
        potential_end_dt_obj = start_dt_obj + timedelta(minutes=config["slot_duration_minutes"])
        
        # Ensure the calculated end time does not exceed the overall end time for the venue
        actual_end_dt_obj = min(potential_end_dt_obj, overall_end_dt)
        st.session_state.end_time = actual_end_dt_obj.strftime("%I:%M %p").lstrip('0').replace(' 0', ' ').replace(':00 ', ':00').replace('AM',' AM').replace('PM',' PM')
    except ValueError:
        st.session_state.end_time = "Invalid Time"
else:
    st.session_state.end_time = "" # Clear end time if start time or venue is not selected

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

# Status Display
st.subheader("Current Status")
st.write(st.session_state.status)

# Important Note about Threading in Streamlit
st.markdown(
    """
    ---
    **Important Note on Scheduling/Continuous Booking:**
    This application uses Python's `threading` and `schedule` library for background tasks.
    While this works for local execution, if you deploy this Streamlit app to a cloud platform
    (like Streamlit Community Cloud), these background threads might not persist reliably
    due to how Streamlit manages app processes. For robust, long-running background tasks
    in a deployed environment, consider using a separate backend service or a dedicated
    task scheduling system (e.g., Celery, Airflow).
    """
)
