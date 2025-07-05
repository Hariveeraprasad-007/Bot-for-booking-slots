import tkinter as tk
from tkinter import ttk, messagebox
from tkcalendar import DateEntry
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import StaleElementReferenceException, NoSuchElementException, TimeoutException, ElementClickInterceptedException
import threading
import re
import time
from datetime import datetime, timedelta
import schedule
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
scheduled_time = None  # Store the scheduled time for validation

def check_gpu_availability():
    """Check if a GPU is available and return appropriate browser options."""
    if GPU_AVAILABLE:
        try:
            gpus = GPUtil.getGPUs()
            if gpus and any(gpu.load < 0.9 for gpu in gpus):
                print("GPU detected and available.")
                return True, "--enable-gpu"
            else:
                print("No available GPU or GPU fully utilized. Falling back to CPU.")
                return False, "--disable-gpu"
        except Exception as e:
            print(f"Error checking GPU: {e}. Falling back to CPU.")
            return False, "--disable-gpu"
    else:
        print("GPUtil not installed. Falling back to CPU.")
        return False, "--disable-gpu"

# --- Time Slot Generation Logic ---
def _generate_interval_start_times(overall_start_dt, overall_end_dt, interval_m, break_start_dt, break_end_dt):
    """
    Generates a list of start times at fixed intervals, skipping any time within a break.
    This is for venues like 1611 where all granular 15-min slots are available.
    """
    times = []
    current_time = overall_start_dt
    
    # Ensure current_time does not go past overall_end_dt (excluding the slot duration)
    while current_time < overall_end_dt: 
        # Check if current_time falls within the break
        is_during_break = False
        if break_start_dt and break_end_dt:
            if break_start_dt <= current_time < break_end_dt:
                is_during_break = True

        if not is_during_break:
            # Format time, removing leading zero for hour for common AM/PM display
            formatted_time = current_time.strftime("%I:%M %p").lstrip('0').replace(' 0', ' ').replace(':00 ', ':00').replace('AM',' AM').replace('PM',' PM')
            times.append(formatted_time)
        
        current_time += timedelta(minutes=interval_m)

        # If current_time jumps into or past break, move it past break_end_dt
        if break_start_dt and break_end_dt and break_start_dt <= current_time < break_end_dt:
            current_time = break_end_dt
            
    return times

# Venue time slot configurations
# Contains overall operating hours, slot durations, break times, and
# either fixed start times or a flag for interval generation.
venue_details = {
    "1731": {
        "slot_duration_minutes": 120, # 2 hours
        "overall_start_time_str": "8:00 AM", "overall_end_time_str": "4:30 PM",
        "break_time_str": ("12:00 PM", "1:00 PM"),
        "fixed_start_times_str": ["8:00 AM", "10:00 AM", "1:00 PM", "3:00 PM"]
    },
    "1851": {
        "slot_duration_minutes": 120, # 2 hours
        "overall_start_time_str": "8:00 AM", "overall_end_time_str": "4:30 PM",
        "break_time_str": ("12:00 PM", "1:00 PM"),
        "fixed_start_times_str": ["8:00 AM", "10:00 AM", "1:00 PM", "3:00 PM"]
    },
    "1852": {
        "slot_duration_minutes": 60, # 1 hour
        "overall_start_time_str": "8:00 AM", "overall_end_time_str": "4:00 PM",
        "break_time_str": ("12:00 PM", "1:00 PM"),
        "fixed_start_times_str": ["8:00 AM", "9:00 AM", "10:00 AM", "11:00 AM", "1:00 PM", "2:00 PM", "3:00 PM"]
    },
    "1611": {
        "slot_duration_minutes": 15, # 15 minutes
        "overall_start_time_str": "8:00 AM", "overall_end_time_str": "4:30 PM",
        "break_time_str": ("12:00 PM", "1:00 PM"),
        "generate_all_intervals": True # Flag to indicate dynamic generation based on slot_duration_minutes as interval
    }
}


from selenium.webdriver.common.action_chains import ActionChains

from selenium.webdriver.common.action_chains import ActionChains

def slot_booking_process(username_input, password_input, day, date, start_time, end_time, scheduler_url, proxy, headless, browser_choice, root, continuous=False, check_until_time=None):
    driver = None
    try:
        # Check GPU availability
        use_gpu, gpu_arg = check_gpu_availability()
        root.after(0, lambda: status_label.config(text=f"Using {'GPU' if use_gpu else 'CPU'} | Initializing..."))

        # Parse check_until_time
        deadline = None
        if check_until_time and continuous:
            try:
                deadline = datetime.strptime(check_until_time, "%H:%M")
                deadline = datetime.now().replace(hour=deadline.hour, minute=deadline.minute, second=0, microsecond=0)
                if deadline < datetime.now():
                    deadline = deadline.replace(day=deadline.day + 1)
                print(f"Will check until {deadline.strftime('%H:%M:%S')}")
            except ValueError:
                print(f"Invalid check until time format: {check_until_time}")
                root.after(0, lambda: messagebox.showerror("Error", "Invalid time format. Use HH:MM (e.g., 21:30)."))
                return

        # Browser setup (optimized for performance)
        if browser_choice == "Chrome":
            options = ChromeOptions()
            options.add_argument("--headless=new")  # Always headless for performance
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")
            options.add_argument("--window-size=800,600")  # Smaller window for memory efficiency
            options.add_argument("--disable-extensions")
            options.add_argument("--disable-plugins")
            options.add_argument("--disable-images")
            options.add_argument("--disable-css-backgrounds")
            options.add_argument("--disable-background-timer-throttling")
            options.add_argument("--disable-backgrounding-occluded-windows")
            options.add_argument("--disable-renderer-backgrounding")
            options.add_argument("--page-load-strategy=none")  # Don't wait for all resources
            options.add_argument("--memory-pressure-off")
            options.add_experimental_option("prefs", {
                "profile.managed_default_content_settings.images": 2,
                "profile.default_content_settings.popups": 0,
                "profile.managed_default_content_settings.media_stream": 2,
                "profile.managed_default_content_settings.notifications": 2
            })
            driver = webdriver.Chrome(options=options)
        elif browser_choice == "Firefox":
            options = FirefoxOptions()
            options.add_argument("--headless")
            if proxy:
                options.set_preference("network.proxy.type", 1)
                options.set_preference("network.proxy.http", proxy.split(":")[0])
                options.set_preference("network.proxy.http_port", int(proxy.split(":")[1]))
            options.set_preference("permissions.default.image", 2)
            options.set_preference("dom.ipc.processCount", 4)  # Reduced from 8 for memory efficiency
            options.set_preference("media.autoplay.enabled", False)
            options.set_preference("media.navigator.enabled", False)
            driver = webdriver.Firefox(options=options)
        elif browser_choice == "Edge":
            options = EdgeOptions()
            options.add_argument("--headless")
            options.add_argument("--disable-gpu")
            options.add_argument("--window-size=800,600")  # Smaller window
            options.add_argument("--disable-images")
            options.add_argument("--disable-css-backgrounds")
            options.add_argument("--page-load-strategy=none")
            driver = webdriver.Edge(options=options)
        else:
            raise ValueError("Unsupported browser")

        active_drivers.append(driver)
        print(f"Running in {browser_choice} headless mode")
        driver.implicitly_wait(1.0)  # Increased from 0.2 for better reliability
        driver.set_page_load_timeout(30)  # Prevent hanging on slow connections

        # Login with optimized timing
        root.after(0, lambda: status_label.config(text="Logging in..."))
        driver.get("https://lms2.ai.saveetha.in/course/view.php?id=302")
        try:
            # Optimized wait times for better performance on limited resources
            username_field = WebDriverWait(driver, 5, poll_frequency=0.5).until(
                EC.presence_of_element_located((By.NAME, 'username'))
            )
            username_field.send_keys(username_input)
            driver.find_element(By.NAME, 'password').send_keys(password_input)
            driver.find_element(By.ID, 'loginbtn').click()
            print("Logged in")
        except TimeoutException as e:
            print(f"Login timeout: {e}")
            root.after(0, lambda: messagebox.showerror("Error", "❌ Login failed: Fields not found."))
            return

        # Parse date
        try:
            date_obj = datetime.strptime(date.strip(), "%d %m %Y")
            formatted_date_for_comparison = date_obj.strftime("%A, %d %B %Y")
        except ValueError:
            print(f"Invalid date format: {date}")
            root.after(0, lambda: messagebox.showerror("Error", f"❌ Invalid date format: {date}"))
            return

        # Normalize time function
        def normalize_time(time_str):
            return re.sub(r'\s+', ' ', time_str.strip().lstrip('0').replace(':00 ', ':00').replace('AM', ' AM').replace('PM', ' PM')).replace("  ", " ")

        normalized_start_time = normalize_time(start_time)
        normalized_end_time = normalize_time(end_time)
        print(f"Looking for slot: {formatted_date_for_comparison}, {normalized_start_time}-{normalized_end_time}")

        found_slot = False
        attempt = 0
        refresh_interval = 0.5

        while not found_slot:
            attempt += 1
            loop_start_time = time.time()
            root.after(0, lambda: status_label.config(text=f"Attempt {attempt}: Checking slot..."))

            # Check deadline
            if deadline and datetime.now() > deadline:
                print(f"Deadline {deadline.strftime('%H:%M:%S')} reached.")
                root.after(0, lambda: messagebox.showerror("Failure", f"❌ Slot not found for {day}, {date}, {start_time}-{end_time}."))
                return

            # Navigate to scheduler
            driver.get(scheduler_url)

            page_source = driver.page_source
            if "503 Service Unavailable" in page_source or "Service Temporarily Unavailable" in page_source or "ERR_CONNECTION_REFUSED" in page_source:
                print(f"Detected 503/Connection error on attempt {attempt}. Retrying...")
                root.after(0, lambda: status_label.config(text=f"503 Error detected. Retrying... (Attempt {attempt})"))
                time.sleep(refresh_interval)
                continue

                # Wait for the table to be present after refresh - reduced to 2 seconds
            WebDriverWait(driver, 2).until(EC.presence_of_element_located((By.CSS_SELECTOR, "table#slotbookertable, table.generaltable")))

                # Check for existing booking (Cancel booking button) immediately after refresh
            try:
                WebDriverWait(driver, 0.5).until(
                    EC.presence_of_element_located((By.XPATH, "//button[contains(@class, 'btn') and contains(text(), 'Cancel booking')]"))
                )
                print("Existing booking found. Stopping process.")
                root.after(0, lambda: messagebox.showwarning("Booking Exists", "You already have an upcoming slot booked. Please cancel it to book a new slot."))
                return
            except TimeoutException:
                pass

                # Check for frozen slot immediately after refresh
            try:
                WebDriverWait(driver, 0.5).until(
                    EC.presence_of_element_located((By.XPATH, "//th[contains(text(), 'Other participants')]"))
                )
                print("Frozen slot detected. Stopping process.")
                root.after(0, lambda: messagebox.showwarning("Slot Frozen", "Your slot is frozen. Please resolve this to book a new slot."))
                return
            except TimeoutException:
                pass


            # Parse table rows
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
                            print(f"Found slot: {table_start_time}-{table_end_time}")
                            try:
                                book_button = cells[7].find_element(By.XPATH, ".//button[contains(text(), 'Book slot')]")
                                if book_button.is_enabled():
                                    print("Booking slot...")
                                    ActionChains(driver).move_to_element(book_button).click().perform()
                                    found_slot = True

                                    # Post-booking form logic (unchanged)
                                    try:
                                        note_field = WebDriverWait(driver, 3, poll_frequency=0.1).until(EC.visibility_of_element_located((By.ID, "id_studentnote_editoreditable")))
                                        note_field.send_keys("Booking for project work (automated)")
                                        submit_button = WebDriverWait(driver, 1, poll_frequency=0.1).until(EC.element_to_be_clickable((By.ID, "id_submitbutton")))
                                        submit_button.click()

                                        # Verify booking
                                        try:
                                            WebDriverWait(driver, 2, poll_frequency=0.1).until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'confirmed') or contains(text(), 'success')]")))
                                            print("Booking confirmed.")
                                        except TimeoutException:
                                            print("No confirmation text, checking booked slot...")
                                            WebDriverWait(driver, 2, poll_frequency=0.1).until(EC.presence_of_element_located((By.XPATH, f"//tr[td[contains(text(), '{formatted_date_for_comparison}')]][td[contains(text(), '{start_time}')] and td[contains(text(), '{end_time}')]]")))
                                            print("Slot found in booked section.")
                                        root.after(0, lambda: messagebox.showinfo("Success", f"Slot booked: {day}, {date}, {start_time}-{end_time} ✅"))
                                        if SOUND_AVAILABLE:
                                            try:
                                                playsound('success.wav')
                                            except Exception as se:
                                                print(f"Error playing sound: {se}")
                                        return
                                    except TimeoutException:
                                        print("No form found, assuming success.")
                                        root.after(0, lambda: messagebox.showinfo("Success", f"Slot booked: {day}, {date}, {start_time}-{end_time} ✅ (Verify manually)"))
                                        return
                                else:
                                    print("Book slot button disabled.")
                                    break
                            except (NoSuchElementException, ElementClickInterceptedException) as e:
                                print(f"Button interaction error: {e}")
                                break
                except StaleElementReferenceException:
                    print("Stale element, retrying...")
                    break
                except Exception as e:
                    print(f"Row processing error: {e}")
                    continue

            if not continuous:
                print("Slot not found in single attempt.")
                root.after(0, lambda: messagebox.showerror("Failure", f"❌ Slot not found for {day}, {date}, {start_time}-{end_time}."))
                return
            time.sleep(refresh_interval)

    except Exception as e:
        print(f"Unexpected error: {e}")
        root.after(0, lambda: messagebox.showerror("Error", f"❌ Error: {str(e)}"))
    finally:
        if driver:
            print("Closing browser")
            if driver in active_drivers:
                active_drivers.remove(driver)
            try:
                driver.quit()
            except Exception:
                pass
def add_slot():
    date = entry_date.get()
    try:
        date_obj = datetime.strptime(date.strip(), "%d %m %Y")
        day = date_obj.strftime("%A")
        combo_day.set(day)
    except ValueError:
        messagebox.showwarning("Invalid Date", "Please enter a valid date.")
        return

    start_time = entry_start_time.get()
    end_time = entry_end_time.get()
    
    if not all([day, date, start_time, end_time]):
        messagebox.showwarning("Input Missing", "Please fill in all slot fields.")
        return
    
    selected_venue_id = combo_schedule.get()
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
                overall_start_dt, overall_end_dt, config["slot_duration_minutes"], # For 1611, slot_duration is the interval
                break_start_dt, break_end_dt
            )
        
        if start_time not in expected_start_times:
            messagebox.showwarning("Invalid Start Time", f"The selected start time '{start_time}' is not a valid start time for venue {selected_venue_id}.")
            return
            
    slot = {"day": day, "date": date, "start_time": start_time, "end_time": end_time}
    slot_list.append(slot)
    slot_str = f"Day: {day}, Date: {date}, Start: {start_time}, End: {end_time}"
    listbox_slots.insert(tk.END, slot_str)
    entry_start_time.set("")
    entry_end_time.set("")

def remove_slot():
    selected = listbox_slots.curselection()
    if selected:
        index = selected[0]
        listbox_slots.delete(index)
        slot_list.pop(index)

def stop_process():
    schedule.clear()
    global scheduled_time
    scheduled_time = None
    print("All scheduled jobs cleared.")

    for driver in active_drivers[:]:
        try:
            driver.quit()
            active_drivers.remove(driver)
            print("Closed an active browser instance.")
        except Exception as e:
            print(f"Error closing driver: {e}")

    for thread in active_threads[:]:
        try:
            active_threads.remove(thread)
            print("Removed a tracked thread.")
        except Exception as e:
            print(f"Error removing thread: {e}")

    messagebox.showinfo("Stopped", "All booking processes and schedules have been stopped.")
    status_label.config(text="Status: Stopped")

def run_booking(continuous=False):
    global scheduled_time
    if scheduled_time:
        now = datetime.now()
        scheduled = datetime.strptime(scheduled_time, "%H:%M")
        scheduled_today = now.replace(hour=scheduled.hour, minute=scheduled.minute, second=0, microsecond=0)
        time_diff = abs((now - scheduled_today).total_seconds())
        if time_diff > 60:
            print(f"Booking attempt ignored: Current time {now.strftime('%H:%M:%S')} is not within 1 minute of scheduled time {scheduled_time}")
            return

    username = entry_username.get()
    password = entry_password.get()
    choice = combo_schedule.get()
    browser_choice = combo_browser.get()
    headless_mode = headless_var.get()
    proxies = entry_proxies.get().split(",") if entry_proxies.get() else []
    check_until_time = entry_check_until.get().strip() or None

    urls = {
        "1731": "https://lms2.ai.saveetha.in/mod/scheduler/view.php?id=36638",
        "1851": "https://lms2.ai.saveetha.in/mod/scheduler/view.php?id=36298",
        "1852": "https://lms2.ai.saveetha.in/mod/scheduler/view.php?id=37641",
        "1611": "https://lms2.ai.saveetha.in/mod/scheduler/view.php?id=36137"
    }

    if choice not in urls:
        messagebox.showerror("Error", "Invalid schedule selected.")
        return
    if not slot_list:
        messagebox.showwarning("No Slots", "Please add at least one slot to book.")
        return

    scheduler_url = urls[choice]

    print(f"Starting booking process at {datetime.now().strftime('%H:%M:%S')}...")
    for i, slot in enumerate(slot_list):
        proxy = proxies[i % len(proxies)] if proxies else None
        thread = threading.Thread(target=slot_booking_process, args=(
            username, password, slot["day"], slot["date"], slot["start_time"], slot["end_time"],
            scheduler_url, proxy, headless_mode, browser_choice, root, continuous, check_until_time
        ))
        active_threads.append(thread)
        thread.start()

def schedule_booking():
    global scheduled_time
    schedule_time = entry_schedule_time.get()
    try:
        datetime.strptime(schedule_time, "%H:%M")
        schedule.clear()
        scheduled_time = schedule_time
        schedule.every().day.at(schedule_time).do(lambda: run_booking(continuous=True))
        print(f"Scheduled booking daily at {schedule_time}")
        messagebox.showinfo("Scheduled", f"Booking scheduled daily at {schedule.next_run().strftime('%Y-%m-%d %H:%M:%S')}.")
        status_label.config(text=f"Status: Scheduled at {schedule_time}")

        def run_schedule():
            while True:
                now = datetime.now()
                next_run = schedule.next_run()
                if next_run:
                    time_to_next = (next_run - now).total_seconds()
                    print(f"Next scheduled run at {next_run.strftime('%H:%M:%S')} ({time_to_next:.0f} seconds from now)")
                schedule.run_pending()
                time.sleep(30)
        threading.Thread(target=run_schedule, daemon=True).start()
    except ValueError:
        messagebox.showerror("Error", "Invalid time format. Use HH:MM (e.g., 21:03).")

def on_date_selected(event=None):
    date = entry_date.get()
    try:
        date_obj = datetime.strptime(date.strip(), "%d %m %Y")
        day = date_obj.strftime("%A")
        combo_day.set(day)
    except ValueError:
        combo_day.set("")

def on_schedule_selected(event=None):
    selected_venue_id = combo_schedule.get()
    if selected_venue_id in venue_details:
        config = venue_details[selected_venue_id]
        
        # Parse overall start/end/break times to datetime objects
        overall_start_dt = datetime.strptime(config["overall_start_time_str"], "%I:%M %p")
        overall_end_dt = datetime.strptime(config["overall_end_time_str"], "%I:%M %p")
        
        break_start_dt = None
        break_end_dt = None
        if config["break_time_str"]:
            break_start_dt = datetime.strptime(config["break_time_str"][0], "%I:%M %p")
            break_end_dt = datetime.strptime(config["break_time_str"][1], "%I:%M %p")

        start_time_options = []
        if "fixed_start_times_str" in config:
            # Use predefined fixed start times
            start_time_options = config["fixed_start_times_str"]
        elif "generate_all_intervals" in config and config["generate_all_intervals"]:
            # Generate start times based on interval (used for 1611)
            start_time_options = _generate_interval_start_times(
                overall_start_dt, overall_end_dt, config["slot_duration_minutes"], # For 1611, slot_duration is the interval
                break_start_dt, break_end_dt
            )
        
        entry_start_time['values'] = start_time_options
        
        # Set default start time if available
        if start_time_options:
            entry_start_time.set(start_time_options[0])
            on_start_time_selected() # Call this to set the initial end time
        else:
            entry_start_time.set("")
            entry_end_time.set("") # Clear end time if no start times
    else:
        entry_start_time['values'] = []
        entry_start_time.set("")
        entry_end_time.set("")

def on_start_time_selected(event=None):
    selected_start_time_str = entry_start_time.get()
    selected_venue_id = combo_schedule.get()

    if selected_start_time_str and selected_venue_id in venue_details:
        config = venue_details[selected_venue_id]
        try:
            start_dt_obj = datetime.strptime(selected_start_time_str.strip(), "%I:%M %p")
            overall_end_dt = datetime.strptime(config["overall_end_time_str"], "%I:%M %p")

            # Calculate potential end time based on slot duration
            potential_end_dt_obj = start_dt_obj + timedelta(minutes=config["slot_duration_minutes"])
            
            # The actual end time should not exceed the venue's overall end time
            actual_end_dt_obj = min(potential_end_dt_obj, overall_end_dt)
            
            # Format the end time for display
            end_time_str = actual_end_dt_obj.strftime("%I:%M %p").lstrip('0').replace(' 0', ' ').replace(':00 ', ':00').replace('AM',' AM').replace('PM',' PM')
            entry_end_time.set(end_time_str)
        except ValueError:
            entry_end_time.set("Invalid Time")
    else:
        entry_end_time.set("")


# --- GUI Layout ---
root = tk.Tk()
root.title("Enhanced Slot Booking Bot - Saveetha LMS")
root.geometry("500x950")

ttk.Label(root, text="Username").pack(pady=5)
entry_username = ttk.Entry(root, width=30)
entry_username.pack()

ttk.Label(root, text="Password").pack(pady=5)
entry_password = ttk.Entry(root, width=30, show="*")
entry_password.pack()

ttk.Label(root, text="Select Schedule").pack(pady=5)
combo_schedule = ttk.Combobox(root, values=list(venue_details.keys()), state="readonly")
combo_schedule.pack()
combo_schedule.set("1731") # Set a default value

ttk.Label(root, text="Select Browser").pack(pady=5)
combo_browser = ttk.Combobox(root, values=["Chrome", "Firefox", "Edge"], state="readonly")
combo_browser.pack()
combo_browser.set("Chrome")

ttk.Label(root, text="Proxies (comma-separated, e.g., http://proxy1:port,http://proxy2:port)").pack(pady=5)
entry_proxies = ttk.Entry(root, width=50)
entry_proxies.pack()

ttk.Label(root, text="Schedule Time (HH:MM, e.g., 21:03)").pack(pady=5)
entry_schedule_time = ttk.Entry(root, width=30)
entry_schedule_time.pack()

ttk.Label(root, text="Check Until Time (HH:MM, e.g., 21:30, optional)").pack(pady=5)
entry_check_until = ttk.Entry(root, width=30)
entry_check_until.pack()

ttk.Label(root, text="Date (Select or Type, e.g., 16 May 2025)").pack(pady=5)
entry_date = DateEntry(root, width=30, date_pattern="dd mm Y", state="normal")
entry_date.pack()
entry_date.bind("<<DateEntrySelected>>", on_date_selected)
entry_date.bind("<FocusOut>", on_date_selected)

ttk.Label(root, text="Day (Auto-filled)").pack(pady=5)
days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
combo_day = ttk.Combobox(root, values=days, state="readonly")
combo_day.pack()

ttk.Label(root, text="Start Time").pack(pady=5)
entry_start_time = ttk.Combobox(root, values=[], state="readonly", width=30)
entry_start_time.pack()

ttk.Label(root, text="End Time").pack(pady=5)
entry_end_time = ttk.Combobox(root, values=[], state="readonly", width=30)
entry_end_time.pack()

button_add_slot = ttk.Button(root, text="Add Slot", command=add_slot)
button_add_slot.pack(pady=5)

button_remove_slot = ttk.Button(root, text="Remove Selected Slot", command=remove_slot)
button_remove_slot.pack(pady=5)

frame_slots = ttk.Frame(root)
frame_slots.pack(pady=10)
listbox_slots = tk.Listbox(frame_slots, height=5, width=60)
scrollbar = ttk.Scrollbar(frame_slots, orient="vertical", command=listbox_slots.yview)
listbox_slots.config(yscrollcommand=scrollbar.set)
listbox_slots.pack(side="left", fill="both", expand=True)
scrollbar.pack(side="right", fill="y")

headless_var = tk.BooleanVar()
check_headless = ttk.Checkbutton(root, text="Run Headless (Continuous Refresh)", variable=headless_var)
check_headless.pack(pady=10)

status_label = ttk.Label(root, text="Status: Idle")
status_label.pack(pady=5)

button_book = ttk.Button(root, text="Book Slots Now", command=lambda: run_booking(continuous=True))
button_book.pack(pady=10)

button_schedule = ttk.Button(root, text="Schedule Booking", command=schedule_booking)
button_schedule.pack(pady=10)

button_stop = ttk.Button(root, text="Stop Process", command=stop_process)
button_stop.pack(pady=10)

# Bind events for dynamic updates
combo_schedule.bind("<<ComboboxSelected>>", on_schedule_selected)
entry_start_time.bind("<<ComboboxSelected>>", on_start_time_selected)

# Initial call to populate start/end times based on default schedule selection
on_schedule_selected()

root.mainloop()
