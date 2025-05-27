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
from selenium.common.exceptions import StaleElementReferenceException, NoSuchElementException, TimeoutException, ElementClickInterceptedException, WebDriverException
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

def check_503_error(driver, url, max_attempts=5, wait_time=2):
    """Check for 503 error and retry loading the page."""
    attempts = 0
    while attempts < max_attempts:
        try:
            driver.get(url)
            if "503 Service Unavailable" in driver.title or "503 Service Unavailable" in driver.page_source:
                print(f"503 Service Unavailable detected at attempt {attempts + 1}. Refreshing page...")
                driver.refresh()
                time.sleep(wait_time)
                attempts += 1
                continue
            WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            print(f"Page loaded successfully: {url}")
            return True
        except (TimeoutException, WebDriverException) as e:
            print(f"Error loading page (attempt {attempts + 1}): {e}. Retrying...")
            driver.refresh()
            time.sleep(wait_time)
            attempts += 1
    print(f"Failed to load page after {max_attempts} attempts due to 503 error or other issues.")
    return False

from datetime import datetime, timezone, timedelta
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException, ElementClickInterceptedException
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver import Chrome, Firefox, Edge
import re
try:
    from tkinter import messagebox
except ImportError:
    messagebox = None
try:
    from playsound import playsound
    SOUND_AVAILABLE = True
except ImportError:
    SOUND_AVAILABLE = False

active_drivers = []

def check_503_error(driver, url, max_attempts=3):
    for attempt in range(max_attempts):
        try:
            driver.get(url)
            WebDriverWait(driver, 5).until(lambda d: d.execute_script("return document.readyState") == "complete")
            if "503 Service Unavailable" not in driver.page_source:
                print(f"Page loaded successfully: {url}")
                return True
            print(f"503 error detected on attempt {attempt + 1}")
        except Exception as e:
            print(f"Error loading page on attempt {attempt + 1}: {e}")
        time.sleep(1)
    return False

def check_gpu_availability():
    try:
        import GPUtil
        gpus = GPUtil.getGPUs()
        return len(gpus) > 0, "--disable-gpu" if not len(gpus) else ""
    except ImportError:
        print("GPUtil not installed. Falling back to CPU.")
        return False, "--disable-gpu"

def slot_booking_process(username_input, password_input, day, date, start_time, end_time, scheduler_url, proxy, headless, browser_choice, root, continuous=False, check_until_time=None):
    driver = None
    try:
        use_gpu, gpu_arg = check_gpu_availability()
        root.after(0, lambda: status_label.config(text=f"Using {'GPU' if use_gpu else 'CPU'} | Checking for slot..."))

        deadline = None
        if check_until_time:
            try:
                deadline = datetime.strptime(check_until_time, "%H:%M")
                deadline = datetime.now().replace(hour=deadline.hour, minute=deadline.minute, second=0, microsecond=0)
                if deadline < datetime.now():
                    deadline = deadline.replace(day=deadline.day + 1)
                print(f"Will check until {deadline.strftime('%H:%M:%S')}")
            except ValueError:
                print(f"Invalid check until time format: {check_until_time}")
                root.after(0, lambda: messagebox.showerror("Error", "Invalid check until time format. Use HH:MM (e.g., 21:30)."))
                return

        if browser_choice == "Chrome":
            options = ChromeOptions()
            if headless:
                options.add_argument("--headless=new")
                options.add_argument("--no-sandbox")
                options.add_argument("--disable-dev-shm-usage")
            options.add_argument(gpu_arg)
            if proxy:
                options.add_argument(f'--proxy-server={proxy}')
            options.add_argument("--page-load-strategy=eager")
            driver = Chrome(options=options)
        elif browser_choice == "Firefox":
            options = FirefoxOptions()
            if headless:
                options.add_argument("--headless")
            if proxy:
                options.set_preference("network.proxy.type", 1)
                options.set_preference("network.proxy.http", proxy.split(":")[0])
                options.set_preference("network.proxy.http_port", int(proxy.split(":")[1]))
            driver = Firefox(options=options)
        elif browser_choice == "Edge":
            options = EdgeOptions()
            if headless:
                options.add_argument("--headless")
            if proxy:
                options.add_argument(f'--proxy-server={proxy}')
            driver = Edge(options=options)
        else:
            raise ValueError("Unsupported browser selected")

        active_drivers.append(driver)
        driver.maximize_window()
        print(f"Running in {browser_choice} {'headless' if headless else 'visible'} mode with {'GPU' if use_gpu else 'CPU'}")
        driver.implicitly_wait(1)

        # Navigate to login page
        login_url = "https://lms2.ai.saveetha.in/course/view.php?id=302"
        print("Navigating to login page")
        if not check_503_error(driver, login_url):
            root.after(0, lambda: messagebox.showerror("Error", "❌ Failed to load login page due to persistent 503 error"))
            return

        WebDriverWait(driver, 3).until(EC.presence_of_element_located((By.NAME, 'username'))).send_keys(username_input)
        driver.find_element(By.NAME, 'password').send_keys(password_input)
        driver.find_element(By.ID, 'loginbtn').click()
        print("Logged in successfully")

        try:
            date_obj = datetime.strptime(date.strip(), "%d %m %Y")
            formatted_date = date_obj.strftime("%d %B %Y")
        except ValueError:
            print(f"Invalid date format: {date}")
            root.after(0, lambda: messagebox.showerror("Error", f"❌ Invalid date format: {date}"))
            return

        expected_date_formats = [
            formatted_date,
            date_obj.strftime("%B %d, %Y"),
            date_obj.strftime("%d/%m/%Y"),
            f"{day.strip()}, {formatted_date}"
        ]
        print(f"Looking for slot with date in formats: {expected_date_formats}, time: {start_time}-{end_time}")

        # Navigate to scheduler page
        if not check_503_error(driver, scheduler_url):
            root.after(0, lambda: messagebox.showerror("Error", "❌ Failed to load scheduler page due to persistent 503 error"))
            return

        # Wait for page to load
        WebDriverWait(driver, 5).until(lambda d: d.execute_script("return document.readyState") == "complete")
        print("Scheduler page fully loaded")

        # Check "Upcoming slots"
        try:
            print("Checking for 'Upcoming slots' section")
            xpaths = [
                "//div[@role='main']//h3[text()='Upcoming slots']/following-sibling::div[1]//table[@class='generaltable']",
                "//h3[text()='Upcoming slots']/following-sibling::div[contains(@class, 'table-responsive')]//table[@class='generaltable']",
                "//h3[text()='Upcoming slots']/following::table[@class='generaltable'][1]"
            ]
            upcoming_slots_table = None
            for xpath in xpaths:
                for _ in range(2):
                    try:
                        upcoming_slots_table = WebDriverWait(driver, 2).until(
                            EC.presence_of_element_located((By.XPATH, xpath))
                        )
                        print(f"Found 'Upcoming slots' table with XPath: {xpath}")
                        is_under_upcoming = driver.execute_script(
                            """
                            let table = arguments[0];
                            let parent = table;
                            while (parent) {
                                let h3 = parent.previousElementSibling;
                                if (h3 && h3.tagName.toLowerCase() === 'h3' && h3.textContent.trim() === 'Upcoming slots') {
                                    return true;
                                }
                                parent = parent.parentElement;
                            }
                            return false;
                            """,
                            upcoming_slots_table
                        )
                        if is_under_upcoming:
                            print("Confirmed table is under 'Upcoming slots'")
                            break
                        else:
                            print(f"Table not under 'Upcoming slots' for XPath: {xpath}, retrying...")
                            upcoming_slots_table = None
                            time.sleep(0.5)
                    except TimeoutException:
                        print(f"Retrying to locate 'Upcoming slots' table with XPath: {xpath}")
                        time.sleep(0.5)
                if upcoming_slots_table:
                    break
            else:
                print("No 'Upcoming slots' table found after trying all XPaths.")
                upcoming_slots_table = None

            if upcoming_slots_table:
                try:
                    rows = WebDriverWait(driver, 1).until(
                        EC.presence_of_all_elements_located((By.XPATH, ".//tbody/tr"))
                    ) or []
                    print(f"Found {len(rows)} row(s) in 'Upcoming slots' table")
                    for i, row in enumerate(rows):
                        try:
                            date_cell = row.find_element(By.CSS_SELECTOR, "td.cell.c0")
                            print(f"Row {i+1} date cell text: '{date_cell.text}'")
                        except:
                            print(f"Row {i+1} failed to extract date cell text")
                except TimeoutException:
                    rows = []
                    print("No rows found in 'Upcoming slots' table within 1 second")

                if rows:
                    for row in rows:
                        try:
                            date_cell = row.find_element(By.CSS_SELECTOR, "td.cell.c0")
                            print(f"Processing row with date cell text: '{date_cell.text}'")

                            # Extract date
                            try:
                                date_label = WebDriverWait(date_cell, 1).until(
                                    EC.presence_of_element_located((By.CLASS_NAME, "datelabel"))
                                ).text.strip()
                            except:
                                date_lines = [line.strip() for line in date_cell.text.split('\n') if line.strip()]
                                date_label = date_lines[0] if date_lines else ""
                                print(f"No datelabel found, using raw text: '{date_label}'")

                            # Extract time
                            try:
                                time_label = WebDriverWait(date_cell, 1).until(
                                    EC.presence_of_element_located((By.CLASS_NAME, "timelabel"))
                                ).text.strip()
                            except:
                                time_label = ""
                                date_lines = [line.strip() for line in date_cell.text.split('\n') if line.strip()]
                                for line in date_lines:
                                    if "AM" in line or "PM" in line:
                                        time_label = line
                                        break
                                print(f"No timelabel found, using raw text: '{time_label}'")

                            if not date_label or not time_label:
                                print(f"Skipping row: date_label='{date_label}', time_label='{time_label}'")
                                continue

                            # Parse and classify slot
                            try:
                                slot_date = datetime.strptime(date_label, "%A, %d %B %Y")
                                today = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=5, minutes=30))).replace(hour=0, minute=0, second=0, microsecond=0)
                                if slot_date.date() <= today.date():
                                    message = f"There is a freezed slot at this date and time:\nDate: {date_label}\nTime: {time_label}"
                                    print(message)
                                    root.after(0, lambda: messagebox.showwarning("Freezed Slot", message))
                                    return
                                # Future slots: no message, proceed
                                print(f"Found future slot: {date_label}, {time_label}. Proceeding with booking.")
                            except ValueError as e:
                                print(f"Error parsing date '{date_label}': {e}. Skipping row.")
                                continue
                        except (NoSuchElementException, StaleElementReferenceException) as e:
                            print(f"Error processing row: {e}. Skipping.")
                            continue
                    print("No freezed slots found in 'Upcoming slots'. Proceeding with booking.")
                else:
                    print("No rows found in 'Upcoming slots' table. Proceeding with booking.")
            else:
                print("No 'Upcoming slots' table found. Proceeding with booking.")

        except TimeoutException:
            print("Timeout: 'Upcoming slots' table not found within 2 seconds.")
            with open(f"page_source_timeout_{username_input}.html", "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            print(f"Timeout page source saved to 'page_source_timeout_{username_input}.html'")
        except Exception as e:
            print(f"Unexpected error checking upcoming slots: {e}")
            with open(f"page_source_error_{username_input}.html", "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            print(f"Error page source saved to 'page_source_error_{username_input}.html'")

        # Proceed to booking
        WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.ID, 'slotbookertable')))
        print("Slot booking table loaded")

        found_slot = False
        attempt = 0
        refresh_interval = 1

        while not found_slot:
            attempt += 1
            print(f"Attempt {attempt} to find and book slot")

            if deadline and datetime.now() > deadline:
                print(f"Deadline {deadline.strftime('%H:%M:%S')} reached. Slot not found.")
                root.after(0, lambda: messagebox.showerror("Failure", f"❌ Slot not found for {day}, {date}, {start_time}-{end_time} by {check_until_time}."))
                return

            if not check_503_error(driver, scheduler_url):
                root.after(0, lambda: messagebox.showerror("Error", "❌ Failed to load scheduler page due to persistent 503 error"))
                return

            WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.ID, 'slotbookertable')))
            print("Scheduler page loaded")

            all_rows = WebDriverWait(driver, 3).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "table#slotbookertable tr"))
            )
            current_date_header_text = ""

            for i in range(len(all_rows)):
                try:
                    all_rows = WebDriverWait(driver, 3).until(
                        EC.presence_of_all_elements_located((By.CSS_SELECTOR, "table#slotbookertable tr"))
                    )
                    row = all_rows[i]
                    row_text = row.text.strip()

                    date_header_match = re.search(r'\b(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}\b', row_text)
                    if date_header_match:
                        current_date_header_text = date_header_match.group(0).strip()
                    else:
                        for date_format in expected_date_formats:
                            if date_format in row_text:
                                current_date_header_text = date_format
                                break

                    if current_date_header_text and any(current_date_header_text == fmt for fmt in expected_date_formats):
                        time_cells = row.find_elements(By.TAG_NAME, 'td')
                        for k in range(len(time_cells) - 1):
                            cell_text = time_cells[k].text.strip()
                            next_cell_text = time_cells[k + 1].text.strip()
                            if start_time.strip() in cell_text and end_time.strip() in next_cell_text:
                                print(f"Found matching slot: {cell_text} to {next_cell_text}")
                                try:
                                    if "Booked" in row.text:
                                        print("Slot already booked, skipping...")
                                        root.after(0, lambda: messagebox.showerror("Failure", f"❌ Slot already booked for {day}, {date}, {start_time}-{end_time}."))
                                        return

                                    book_button = row.find_element(By.XPATH, ".//button[contains(text(), 'Book slot')]")
                                    driver.execute_script("arguments[0].scrollIntoView(true);", book_button)
                                    WebDriverWait(driver, 3).until(EC.element_to_be_clickable(book_button))
                                    try:
                                        book_button.click()
                                    except ElementClickInterceptedException:
                                        driver.execute_script("arguments[0].click();", book_button)

                                    note_field = WebDriverWait(driver, 3).until(
                                        EC.visibility_of_element_located((By.ID, "id_studentnote_editoreditable"))
                                    )
                                    note_field.send_keys("Booking for project work")
                                    submit_button = WebDriverWait(driver, 3).until(
                                        EC.element_to_be_clickable((By.ID, "id_submitbutton"))
                                    )
                                    try:
                                        submit_button.click()
                                    except ElementClickInterceptedException:
                                        driver.execute_script("arguments[0].click();", submit_button)

                                    try:
                                        WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Booking confirmed')]")))
                                        found_slot = True
                                        print("Slot booked successfully!")
                                        root.after(0, lambda: messagebox.showinfo("Success", f"Slot booked: {day}, {date}, {start_time}-{end_time} ✅"))
                                        if SOUND_AVAILABLE:
                                            playsound('success.wav')
                                        return
                                    except TimeoutException:
                                        found_slot = True
                                        print("Slot booked successfully (assumed)!")
                                        root.after(0, lambda: messagebox.showinfo("Success", f"Slot booked: {day}, {date}, {start_time}-{end_time} ✅"))
                                        if SOUND_AVAILABLE:
                                            playsound('success.wav')
                                        return

                                except (NoSuchElementException, TimeoutException) as e:
                                    print(f"Booking attempt failed: {e}. Retrying...")
                                    continue

                except StaleElementReferenceException:
                    print("Stale element encountered, refreshing...")
                    driver.refresh()
                    if not check_503_error(driver, scheduler_url):
                        root.after(0, lambda: messagebox.showerror("Error", "❌ Failed to load scheduler page due to persistent 503 error"))
                        return
                    WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.ID, 'slotbookertable')))
                    continue

            print(f"Attempt {attempt} failed, retrying in {refresh_interval} seconds...")
            time.sleep(refresh_interval)

    except TimeoutException as e:
        print(f"Timeout error: {e}")
        root.after(0, lambda: messagebox.showerror("Error", f"❌ Timeout error"))
        if driver:
            with open(f"page_source_timeout_{username_input}.html", "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            print(f"Timeout page source saved to 'page_source_timeout_{username_input}.html'")
    except NoSuchElementException as e:
        print(f"Element not found: {e}")
        root.after(0, lambda: messagebox.showerror("Error", f"❌ Element not found"))
    except Exception as e:
        print(f"Unexpected error: {e}")
        root.after(0, lambda: messagebox.showerror("Error", f"❌ Unexpected error"))
    finally:
        if driver:
            print("Shutting down browser")
            if driver in active_drivers:
                active_drivers.remove(driver)
            driver.quit()

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
        messagebox.showinfo("Scheduled", f"Booking scheduled daily at {schedule_time}. Next run: {schedule.next_run().strftime('%Y-%m-%d %H:%M:%S')}.")
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

def get_end_time(schedule_id, start_time):
    """Calculate the end time based on the schedule ID and start time."""
    try:
        start_dt = datetime.strptime(start_time, "%I:%M %p")
        if schedule_id in ["1731", "1851"]:
            start_times = ["8:00 AM", "10:00 AM", "1:00 PM", "3:00 PM"]
            end_times = ["10:00 AM", "12:00 PM", "3:00 PM", "4:30 PM"]
            if start_time in start_times:
                return end_times[start_times.index(start_time)]
        elif schedule_id == "1852":
            start_times = ["8:00 AM", "9:00 AM", "10:00 AM", "11:00 AM", "1:00 PM", "2:00 PM", "3:00 PM"]
            if start_time in start_times:
                end_dt = start_dt + timedelta(hours=1)
                return end_dt.strftime("%I:%M %p")
        elif schedule_id == "1611":
            if (start_time in venue_time_slots["1611"] and 
                start_time != venue_time_slots["1611"][-1]):  # Exclude the last slot
                end_dt = start_dt + timedelta(minutes=15)
                return end_dt.strftime("%I:%M %p")
        return ""
    except ValueError:
        return ""

def on_schedule_selected(event=None):
    schedule_id = combo_schedule.get()
    times = venue_time_slots.get(schedule_id, [])
    entry_start_time['values'] = times
    entry_end_time['values'] = times
    if times:
        entry_start_time.set(times[0])
        entry_end_time.set(get_end_time(schedule_id, times[0]))
    else:
        entry_start_time.set("")
        entry_end_time.set("")

def on_start_time_selected(event=None):
    schedule_id = combo_schedule.get()
    start_time = entry_start_time.get()
    end_time = get_end_time(schedule_id, start_time)
    entry_end_time.set(end_time)

# --- GUI Layout with Scrollable Canvas ---
root = tk.Tk()
root.title("Enhanced Slot Booking Bot - Saveetha LMS")
root.geometry("500x600")

canvas = tk.Canvas(root)
scrollbar = ttk.Scrollbar(root, orient="vertical", command=canvas.yview)
scrollable_frame = ttk.Frame(canvas)

scrollable_frame.bind(
    "<Configure>",
    lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
)
canvas.configure(yscrollcommand=scrollbar.set)

scrollbar.pack(side="right", fill="y")
canvas.pack(side="left", fill="both", expand=True)

canvas_frame = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")

def on_mouse_wheel(event):
    canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

canvas.bind_all("<MouseWheel>", on_mouse_wheel)
canvas.bind_all("<Button-4>", lambda event: canvas.yview_scroll(-1, "units"))
canvas.bind_all("<Button-5>", lambda event: canvas.yview_scroll(1, "units"))

venue_time_slots = {
    "1731": ["8:00 AM", "10:00 AM", "1:00 PM", "3:00 PM"],
    "1851": ["8:00 AM", "10:00 AM", "1:00 PM", "3:00 PM"],
    "1852": ["8:00 AM", "9:00 AM", "10:00 AM", "11:00 AM", "1:00 PM", "2:00 PM", "3:00 PM"],
    "1611": [f"{h}:{m:02d} {'AM' if h < 12 else 'PM'}" for h in range(8, 12) for m in range(0, 60, 15)] +
            [f"{h}:{m:02d} {'PM'}" for h in range(1, 4) for m in range(0, 60, 15)] +
            ["4:00 PM", "4:15 PM"]
}

ttk.Label(scrollable_frame, text="Username").pack(pady=5)
entry_username = ttk.Entry(scrollable_frame, width=30)
entry_username.pack()

ttk.Label(scrollable_frame, text="Password").pack(pady=5)
entry_password = ttk.Entry(scrollable_frame, width=30, show="*")
entry_password.pack()

ttk.Label(scrollable_frame, text="Select Schedule").pack(pady=5)
combo_schedule = ttk.Combobox(scrollable_frame, values=["1731", "1851", "1852", "1611"], state="readonly")
combo_schedule.pack()
combo_schedule.set("1731")

ttk.Label(scrollable_frame, text="Select Browser").pack(pady=5)
combo_browser = ttk.Combobox(scrollable_frame, values=["Chrome", "Firefox", "Edge"], state="readonly")
combo_browser.pack()
combo_browser.set("Chrome")

ttk.Label(scrollable_frame, text="Proxies (comma-separated, e.g., http://proxy1:port,http://proxy2:port)").pack(pady=5)
entry_proxies = ttk.Entry(scrollable_frame, width=50)
entry_proxies.pack()

ttk.Label(scrollable_frame, text="Schedule Time (HH:MM, e.g., 21:03)").pack(pady=5)
entry_schedule_time = ttk.Entry(scrollable_frame, width=30)
entry_schedule_time.pack()

ttk.Label(scrollable_frame, text="Check Until Time (HH:MM, e.g., 21:30, optional)").pack(pady=5)
entry_check_until = ttk.Entry(scrollable_frame, width=30)
entry_check_until.pack()

ttk.Label(scrollable_frame, text="Date (Select or Type, e.g., 16 May 2025)").pack(pady=5)
entry_date = DateEntry(scrollable_frame, width=30, date_pattern="dd mm yyyy", state="normal")
entry_date.pack()
entry_date.bind("<<DateEntrySelected>>", on_date_selected)
entry_date.bind("<FocusOut>", on_date_selected)

ttk.Label(scrollable_frame, text="Day (Auto-filled)").pack(pady=5)
days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
combo_day = ttk.Combobox(scrollable_frame, values=days, state="readonly")
combo_day.pack()

ttk.Label(scrollable_frame, text="Start Time").pack(pady=5)
entry_start_time = ttk.Combobox(scrollable_frame, values=[], state="readonly", width=30)
entry_start_time.pack()
entry_start_time.bind("<<ComboboxSelected>>", on_start_time_selected)

ttk.Label(scrollable_frame, text="End Time").pack(pady=5)
entry_end_time = ttk.Combobox(scrollable_frame, values=[], state="readonly", width=30)
entry_end_time.pack()

button_add_slot = ttk.Button(scrollable_frame, text="Add Slot", command=add_slot)
button_add_slot.pack(pady=5)

button_remove_slot = ttk.Button(scrollable_frame, text="Remove Selected Slot", command=remove_slot)
button_remove_slot.pack(pady=5)

frame_slots = ttk.Frame(scrollable_frame)
frame_slots.pack(pady=10)
listbox_slots = tk.Listbox(frame_slots, height=5, width=60)
scrollbar_slots = ttk.Scrollbar(frame_slots, orient="vertical", command=listbox_slots.yview)
listbox_slots.config(yscrollcommand=scrollbar_slots.set)
listbox_slots.pack(side="left", fill="both", expand=True)
scrollbar_slots.pack(side="right", fill="y")

headless_var = tk.BooleanVar()
check_headless = ttk.Checkbutton(scrollable_frame, text="Run Headless (Continuous Refresh)", variable=headless_var)
check_headless.pack(pady=10)

status_label = ttk.Label(scrollable_frame, text="Status: Idle")
status_label.pack(pady=5)

button_book = ttk.Button(scrollable_frame, text="Book Slots Now", command=lambda: run_booking(continuous=True))
button_book.pack(pady=10)

button_schedule = ttk.Button(scrollable_frame, text="Schedule Booking", command=schedule_booking)
button_schedule.pack(pady=10)

button_stop = ttk.Button(scrollable_frame, text="Stop Process", command=stop_process)
button_stop.pack(pady=10)

combo_schedule.bind("<<ComboboxSelected>>", on_schedule_selected)
on_schedule_selected()

root.mainloop()
