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
from datetime import datetime
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

def slot_booking_process(username_input, password_input, day, date, start_time, end_time, scheduler_url, proxy, headless, browser_choice, root, continuous=False, check_until_time=None):
    driver = None
    try:
        # Check GPU availability
        use_gpu, gpu_arg = check_gpu_availability()
        root.after(0, lambda: status_label.config(text=f"Using {'GPU' if use_gpu else 'CPU'} | Checking for slot..."))

        # Parse check_until_time if provided
        deadline = None
        if check_until_time:
            try:
                deadline = datetime.strptime(check_until_time, "%H:%M")
                deadline = datetime.now().replace(hour=deadline.hour, minute=deadline.minute, second=0, microsecond=0)
                if deadline < datetime.now():
                    deadline = deadline.replace(day=deadline.day + 1)  # Assume next day if time has passed
                print(f"Will check until {deadline.strftime('%H:%M:%S')}")
            except ValueError:
                print(f"Invalid check until time format: {check_until_time}")
                root.after(0, lambda: messagebox.showerror("Error", "Invalid check until time format. Use HH:MM (e.g., 21:30)."))
                return

        # Set up browser options
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
            options.add_argument("--disable-extensions")
            options.add_argument("--disable-images")
            driver = webdriver.Chrome(options=options)
        elif browser_choice == "Firefox":
            options = FirefoxOptions()
            if headless:
                options.add_argument("--headless")
            if proxy:
                options.set_preference("network.proxy.type", 1)
                options.set_preference("network.proxy.http", proxy.split(":")[0])
                options.set_preference("network.proxy.http_port", int(proxy.split(":")[1]))
            driver = webdriver.Firefox(options=options)
        elif browser_choice == "Edge":
            options = EdgeOptions()
            if headless:
                options.add_argument("--headless")
            if proxy:
                options.add_argument(f'--proxy-server={proxy}')
            driver = webdriver.Edge(options=options)
        else:
            raise ValueError("Unsupported browser selected")

        active_drivers.append(driver)
        driver.maximize_window()
        print(f"Running in {browser_choice} {'headless' if headless else 'visible'} mode with {'GPU' if use_gpu else 'CPU'}")
        driver.implicitly_wait(2)  # Increased for reliability

        # Login
        print("Navigating to login page")
        driver.get("https://lms2.ai.saveetha.in/course/view.php?id=302")
        start_time_login = time.time()
        WebDriverWait(driver, 2).until(EC.presence_of_element_located((By.NAME, 'username'))).send_keys(username_input)
        driver.find_element(By.NAME, 'password').send_keys(password_input)
        driver.find_element(By.ID, 'loginbtn').click()
        print(f"Logged in successfully in {time.time() - start_time_login:.2f} seconds")

        # Parse the date
        try:
            date_obj = datetime.strptime(date.strip(), "%d %m %Y")
            formatted_date = date_obj.strftime("%d %B %Y")
            formatted_date_with_day = f"{day.strip()}, {formatted_date}"
        except ValueError:
            print(f"Invalid date format: {date}")
            root.after(0, lambda: messagebox.showerror("Error", f"❌ Invalid date format: {date}"))
            return

        expected_date_formats = [
            formatted_date,
            date_obj.strftime("%B %d, %Y"),
            date_obj.strftime("%d/%m/%Y"),
            formatted_date_with_day
        ]
        print(f"Looking for slot with date in formats: {expected_date_formats}, time: {start_time}-{end_time}")

        # Main loop for page checking
        attempt = 0
        refresh_interval = 0.1  # Reduced for faster retries

        while True:
            attempt += 1
            loop_start_time = time.time()
            print(f"Attempt {attempt} started at {datetime.now().strftime('%H:%M:%S')}")

            try:
                # Check deadline
                if deadline and datetime.now() > deadline:
                    print(f"Deadline {deadline.strftime('%H:%M:%S')} reached. Slot not found.")
                    root.after(0, lambda: messagebox.showerror("Failure", f"❌ Slot not found for {day}, {date}, {start_time}-{end_time} by {check_until_time}."))
                    return

                # Verify WebDriver session
                try:
                    driver.title
                except Exception as e:
                    print(f"WebDriver session invalid: {e}")
                    root.after(0, lambda: messagebox.showerror("Error", "WebDriver session failed."))
                    return

                # Navigate to scheduler
                print("Navigating to scheduler URL")
                driver.get(scheduler_url)
                WebDriverWait(driver, 1).until(EC.presence_of_element_located((By.TAG_NAME, 'body')))
                print("Scheduler page loaded successfully")

                # Check for specific messages
                page_text = driver.find_element(By.TAG_NAME, 'body').text

                # Case 1: Cannot book further appointments
                if "You cannot book further appointments in this scheduler." in page_text:
                    print("Cannot book further appointments, indicating booked or frozen slot.")
                    root.after(0, lambda: messagebox.showwarning("Warning", "There is a booked or frozen slot. Cannot proceed with booking."))
                    return

                # Case 2 & 3: Booking is possible
                if "No slots are available for booking at this time." in page_text or \
                   "You can book additional slots by clicking on the corresponding 'Book slot' button below." in page_text:
                    found_slot = False
                    while not found_slot:
                        attempt += 1
                        print(f"Inner attempt {attempt} at {datetime.now().strftime('%H:%M:%S')}")

                        # Check deadline
                        if deadline and datetime.now() > deadline:
                            print(f"Deadline {deadline.strftime('%H:%M:%S')} reached. Slot not found.")
                            root.after(0, lambda: messagebox.showerror("Failure", f"❌ Slot not found for {day}, {date}, {start_time}-{end_time} by {check_until_time}."))
                            return

                        # Refresh page and get updated text
                        driver.get(scheduler_url)
                        WebDriverWait(driver, 1).until(EC.presence_of_element_located((By.TAG_NAME, 'body')))
                        page_text = driver.find_element(By.TAG_NAME, 'body').text

                        # Recheck messages
                        if "You cannot book further appointments in this scheduler." in page_text:
                            print("Cannot book further appointments, indicating booked or frozen slot.")
                            root.after(0, lambda: messagebox.showwarning("Warning", "There is a booked or frozen slot. Cannot proceed with booking."))
                            return

                        if "No slots are available for booking at this time." in page_text:
                            print("No slots available, refreshing page...")
                            time.sleep(refresh_interval)
                            continue

                        if "You can book additional slots by clicking on the corresponding 'Book slot' button below." in page_text:
                            print("Booking permission found, checking for preferred slot...")
                            try:
                                all_rows = WebDriverWait(driver, 1).until(
                                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, "table.generaltable tbody tr"))
                                )
                                print(f"Found {len(all_rows)} rows in slot table")
                            except TimeoutException:
                                print("No slot table found, refreshing page...")
                                time.sleep(refresh_interval)
                                continue

                            for row in all_rows:
                                try:
                                    # Extract cells for Date (c0), Start (c1), End (c2), and booking button (c7)
                                    cells = row.find_elements(By.TAG_NAME, 'td')
                                    if len(cells) < 8:  # Ensure row has enough cells
                                        print(f"Skipping row with insufficient cells: {len(cells)}")
                                        continue

                                    date_text = cells[0].text.strip()  # Date (c0)
                                    start_text = cells[1].text.strip()  # Start time (c1)
                                    end_text = cells[2].text.strip()  # End time (c2)
                                    row_text = row.text.strip()
                                    print(f"Row data: Date={date_text}, Start={start_text}, End={end_text}")

                                    # Check if date matches any expected format
                                    date_matches = any(date_text == fmt for fmt in expected_date_formats)
                                    if not date_matches:
                                        print(f"Date {date_text} does not match expected formats: {expected_date_formats}")
                                        continue

                                    # Check if start and end times match
                                    if start_time.strip() == start_text and end_time.strip() == end_text:
                                        print(f"Found matching slot: {date_text}, {start_text} to {end_text}")
                                        booking_start_time = time.time()
                                        try:
                                            if "Booked" in row_text:
                                                print("Slot already booked, skipping...")
                                                root.after(0, lambda: messagebox.showerror("Failure", f"❌ Slot already booked for {day}, {date}, {start_time}-{end_time}."))
                                                return

                                            # Locate booking button in the last column (c7)
                                            book_button = row.find_element(By.XPATH, ".//button[contains(text(), 'Book slot')]")
                                            driver.execute_script("arguments[0].scrollIntoView(true);", book_button)
                                            WebDriverWait(driver, 1).until(EC.element_to_be_clickable(book_button))
                                            driver.execute_script("arguments[0].click();", book_button)

                                            note_field = WebDriverWait(driver, 1).until(
                                                EC.visibility_of_element_located((By.ID, "id_studentnote_editoreditable"))
                                            )
                                            note_field.send_keys("Booking for project work")
                                            submit_button = WebDriverWait(driver, 1).until(
                                                EC.element_to_be_clickable((By.ID, "id_submitbutton"))
                                            )
                                            driver.execute_script("arguments[0].click();", submit_button)

                                            try:
                                                WebDriverWait(driver, 2).until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Booking confirmed')]")))
                                                found_slot = True
                                                print(f"Slot booked successfully in {time.time() - booking_start_time:.2f} seconds!")
                                                root.after(0, lambda: messagebox.showinfo("Success", f"Slot booked: {day}, {date}, {start_time}-{end_time} ✅"))
                                                if SOUND_AVAILABLE:
                                                    playsound('success.wav')
                                                return
                                            except TimeoutException:
                                                found_slot = True
                                                print(f"Slot booked successfully (assumed) in {time.time() - booking_start_time:.2f} seconds!")
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
                                    WebDriverWait(driver, 1).until(EC.presence_of_element_located((By.TAG_NAME, 'body')))
                                    page_text = driver.find_element(By.TAG_NAME, 'body').text
                                    continue
                                except Exception as e:
                                    print(f"Error processing row: {e}")
                                    continue

                            print(f"Preferred slot not found in attempt {attempt}. Retrying in {refresh_interval} seconds...")
                            time.sleep(refresh_interval)
                            continue

                # If none of the expected messages are found, refresh the page
                print(f"No recognized booking status message found in attempt {attempt}. Retrying in {refresh_interval} seconds...")
                time.sleep(refresh_interval)

            except Exception as e:
                print(f"Main loop error: {e}")
                root.after(0, lambda: status_label.config(text=f"Error: {str(e)}"))
                time.sleep(refresh_interval)
                continue

    except TimeoutException as e:
        print(f"Timeout error: {e}")
        root.after(0, lambda: messagebox.showerror("Error", f"❌ Timeout error"))
    except NoSuchElementException as e:
        print(f"Element not found: {e}")
        root.after(0, lambda: messagebox.showerror("Error", f"❌ Element not found"))
    except Exception as e:
        print(f"Unexpected error: {e}")
        root.after(0, lambda: messagebox.showerror("Error", f"❌ Unexpected error"))
    finally:
        if driver:
            print("Closing browser gracefully")
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

def on_schedule_selected(event=None):
    schedule_id = combo_schedule.get()
    times = venue_time_slots.get(schedule_id, [])
    entry_start_time['values'] = times
    entry_end_time['values'] = times
    if times:
        entry_start_time.set(times[0])
        entry_end_time.set(times[-1])
    else:
        entry_start_time.set("")
        entry_end_time.set("")

# --- GUI Layout ---
root = tk.Tk()
root.title("Enhanced Slot Booking Bot - Saveetha LMS")
root.geometry("500x950")  # Increased height for new field

# Time slots for each venue
venue_time_slots = {
    "1731": ["8:00 AM", "10:00 AM", "12:00 PM", "1:00 PM", "3:00 PM", "4:30 PM"],
    "1851": ["8:00 AM", "10:00 AM", "12:00 PM", "1:00 PM", "3:00 PM", "4:30 PM"],
    "1852": ["8:00 AM", "9:00 AM", "10:00 AM", "11:00 AM", "12:00 PM", "1:00 PM", "2:00 PM", "3:00 PM", "4:00 PM"],
    "1611": ["8:00 AM", "8:15 AM", "8:30 AM", "8:45 AM", "9:00 AM", "9:15 AM", "9:30 AM", "9:45 AM", "10:00 AM", "10:15 AM", "10:30 AM", "10:45 AM", "11:00 AM", "11:15 AM", "11:30 AM", "11:45 AM", "12:00 PM", "1:00 PM", "1:15 PM", "1:30 PM", "1:45 PM", "2:00 PM", "2:15 PM", "2:30 PM", "2:45 PM", "3:00 PM", "3:15 PM", "3:30 PM", "3:45 PM", "4:00 PM", "4:15 PM", "4:30 PM"]
}

ttk.Label(root, text="Username").pack(pady=5)
entry_username = ttk.Entry(root, width=30)
entry_username.pack()

ttk.Label(root, text="Password").pack(pady=5)
entry_password = ttk.Entry(root, width=30, show="*")
entry_password.pack()

ttk.Label(root, text="Select Schedule").pack(pady=5)
combo_schedule = ttk.Combobox(root, values=["1731", "1851", "1852", "1611"], state="readonly")
combo_schedule.pack()
combo_schedule.set("1731")

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
entry_date = DateEntry(root, width=30, date_pattern="dd mm yyyy", state="normal")
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

combo_schedule.bind("<<ComboboxSelected>>", on_schedule_selected)
on_schedule_selected()

root.mainloop()
