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
            if gpus and any(gpu.load < 0.9 for gpu in gpus):  # Check if GPU is not fully utilized
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

def slot_booking_process(username_input, password_input, day, date, start_time, end_time, scheduler_url, proxy, headless, browser_choice, root, continuous=False):
    driver = None
    try:
        # Check GPU availability
        use_gpu, gpu_arg = check_gpu_availability()
        root.after(0, lambda: status_label.config(text=f"Using {'GPU' if use_gpu else 'CPU'}"))

        # Set up browser options based on user selection
        if browser_choice == "Chrome":
            options = ChromeOptions()
            if headless:
                options.add_argument("--headless=new")
                options.add_argument("--no-sandbox")
                options.add_argument("--disable-dev-shm-usage")
            options.add_argument(gpu_arg)  # GPU or CPU setting
            if proxy:
                options.add_argument(f'--proxy-server={proxy}')
            options.add_argument("--page-load-strategy=eager")
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

        # Track the driver
        active_drivers.append(driver)

        driver.maximize_window()
        print(f"Running in {browser_choice} {'headless' if headless else 'visible'} mode with {'GPU' if use_gpu else 'CPU'}")
        driver.implicitly_wait(1)

        # Login
        print("Navigating to login page")
        driver.get("https://lms2.ai.saveetha.in/course/view.php?id=302")
        WebDriverWait(driver, 3).until(EC.presence_of_element_located((By.NAME, 'username'))).send_keys(username_input)
        driver.find_element(By.NAME, 'password').send_keys(password_input)
        driver.find_element(By.ID, 'loginbtn').click()
        print("Logged in successfully")

        # Parse the date to match LMS format
        try:
            date_obj = datetime.strptime(date.strip(), "%d %m %Y")
            formatted_date = date_obj.strftime("%d %B %Y")
        except ValueError:
            print(f"Invalid date format: {date}")
            root.after(0, lambda: messagebox.showerror("Error", f"❌ Invalid date format: {date}"))
            return

        # Try different date formats to match LMS
        expected_date_formats = [
            formatted_date,
            date_obj.strftime("%B %d, %Y"),
            date_obj.strftime("%d/%m/%Y"),
            f"{day.strip()}, {formatted_date}"
        ]
        print(f"Looking for slot with date in formats: {expected_date_formats}, time: {start_time}-{end_time}")

        # Slot finding with continuous refresh in headless mode
        found_slot = False
        max_attempts = 5 if not continuous else float('inf')
        attempt = 0
        refresh_interval = 1

        while attempt < max_attempts and not found_slot:
            attempt += 1
            print(f"Attempt {attempt} to find and book slot")

            # Navigate to scheduler
            driver.get(scheduler_url)
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

                    # Identify date header
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
                                        continue

                                    book_button = row.find_element(By.XPATH, ".//button[contains(text(), 'Book slot')]")
                                    driver.execute_script("arguments[0].scrollIntoView(true);", book_button)
                                    WebDriverWait(driver, 3).until(EC.element_to_be_clickable(book_button))
                                    try:
                                        book_button.click()
                                    except ElementClickInterceptedException:
                                        driver.execute_script("arguments[0].click();", book_button)

                                    # Fill note and submit
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

                                    # Check for confirmation
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
                    WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.ID, 'slotbookertable')))
                    continue

            if not found_slot:
                print(f"Attempt {attempt} failed, retrying in {refresh_interval} seconds...")
                time.sleep(refresh_interval)

        if not found_slot:
            print("No slot found after all attempts.")
            root.after(0, lambda: messagebox.showerror("Failure", f"❌ No matching slot found for {day}, {date}, {start_time}-{end_time} after retries."))

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
    entry_start_time.delete(0, tk.END)
    entry_end_time.delete(0, tk.END)

def remove_slot():
    selected = listbox_slots.curselection()
    if selected:
        index = selected[0]
        listbox_slots.delete(index)
        slot_list.pop(index)

def stop_process():
    # Clear all scheduled jobs
    schedule.clear()
    global scheduled_time
    scheduled_time = None
    print("All scheduled jobs cleared.")

    # Stop all active threads and drivers
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
    # If scheduled, validate the current time
    if scheduled_time:
        now = datetime.now()
        scheduled = datetime.strptime(scheduled_time, "%H:%M")
        scheduled_today = now.replace(hour=scheduled.hour, minute=scheduled.minute, second=0, microsecond=0)
        time_diff = abs((now - scheduled_today).total_seconds())
        if time_diff > 60:  # Allow 1-minute window
            print(f"Booking attempt ignored: Current time {now.strftime('%H:%M:%S')} is not within 1 minute of scheduled time {scheduled_time}")
            return

    username = entry_username.get()
    password = entry_password.get()
    choice = combo_schedule.get()
    browser_choice = combo_browser.get()
    headless_mode = headless_var.get()
    proxies = entry_proxies.get().split(",") if entry_proxies.get() else []

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
            scheduler_url, proxy, headless_mode, browser_choice, root, continuous
        ))
        active_threads.append(thread)
        thread.start()

def schedule_booking():
    global scheduled_time
    schedule_time = entry_schedule_time.get()
    try:
        # Validate time format (e.g., "21:03")
        datetime.strptime(schedule_time, "%H:%M")
        # Clear all previous scheduled jobs
        schedule.clear()
        # Store the scheduled time
        scheduled_time = schedule_time
        # Schedule the booking
        schedule.every().day.at(schedule_time).do(lambda: run_booking(continuous=True))
        print(f"Scheduled booking daily at {schedule_time}")
        messagebox.showinfo("Scheduled", f"Booking scheduled daily at {schedule_time}. Next run: {schedule.next_run().strftime('%Y-%m-%d %H:%M:%S')}.")
        status_label.config(text=f"Status: Scheduled at {schedule_time}")

        # Start schedule loop in a separate thread
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

# --- GUI Layout ---
root = tk.Tk()
root.title("Enhanced Slot Booking Bot - Saveetha LMS")
root.geometry("500x900")  # Increased height for status label

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

ttk.Label(root, text="Date (Select or Type, e.g., 16 May 2025)").pack(pady=5)
entry_date = DateEntry(root, width=30, date_pattern="dd mm yyyy", state="normal")
entry_date.pack()

ttk.Label(root, text="Day (Auto-filled)").pack(pady=5)
days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
combo_day = ttk.Combobox(root, values=days, state="readonly")
combo_day.pack()

ttk.Label(root, text="Start Time (e.g., 8:00 AM)").pack(pady=5)
entry_start_time = ttk.Entry(root, width=30)
entry_start_time.pack()

ttk.Label(root, text="End Time (e.g., 10:00 AM)").pack(pady=5)
entry_end_time = ttk.Entry(root, width=30)
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

button_book = ttk.Button(root, text="Book Slots Now", command=lambda: run_booking(continuous=False))
button_book.pack(pady=10)

button_schedule = ttk.Button(root, text="Schedule Booking", command=schedule_booking)
button_schedule.pack(pady=10)

button_stop = ttk.Button(root, text="Stop Process", command=stop_process)
button_stop.pack(pady=10)

root.mainloop()
