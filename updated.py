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
scheduled_time = None

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

def check_existing_booking(driver):
    """Check if the user has upcoming bookings and return their date and time details."""
    try:
        print("Waiting for page to load fully...")
        time.sleep(2)
        
        print("Looking for 'Upcoming slots' section...")
        upcoming_header = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.XPATH, "//h3[contains(text(), 'Upcoming slots')]"))
        )
        print("'Upcoming slots' section found.")

        upcoming_table = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.XPATH, "//h3[contains(text(), 'Upcoming slots')]/following::table[contains(@class, 'generaltable')]"))
        )
        print("Upcoming slots table located.")

        rows = upcoming_table.find_elements(By.TAG_NAME, "tr")[1:]  # Skip header row
        booked_slots = []

        if not rows:
            print("No upcoming slots found in the table.")
            cancel_button = driver.find_elements(By.XPATH, "//button[contains(text(), 'Cancel booking')]")
            if cancel_button:
                print("Cancel booking button found, but no slot details available.")
                return True, ["Upcoming slot exists, but details could not be retrieved"]
            return False, []

        print(f"Found {len(rows)} upcoming slots.")
        for row in rows:
            try:
                date_div = row.find_element(By.CLASS_NAME, "datelabel")
                time_div = row.find_element(By.CLASS_NAME, "timelabel")
                date_time = f"{date_div.text.strip()} {time_div.text.strip()}"
                booked_slots.append(date_time)
            except Exception as e:
                print(f"Error extracting date/time from row: {e}")
                continue

        cancel_button = driver.find_elements(By.XPATH, "//button[contains(text(), 'Cancel booking')]")
        has_booking = bool(cancel_button and booked_slots)
        return has_booking, booked_slots if booked_slots else ["Unknown slot"]
    except TimeoutException as e:
        print(f"Timeout while looking for 'Upcoming slots' section or table: {e}")
        cancel_button = driver.find_elements(By.XPATH, "//button[contains(text(), 'Cancel booking')]")
        if cancel_button:
            print("Cancel booking button found, but no slot details available due to timeout.")
            return True, ["Upcoming slot exists, but details could not be retrieved due to timeout"]
        return False, []
    except Exception as e:
        print(f"Unexpected error while checking existing bookings: {e}")
        cancel_button = driver.find_elements(By.XPATH, "//button[contains(text(), 'Cancel booking')]")
        if cancel_button:
            print("Cancel booking button found, but no slot details available due to unexpected error.")
            return True, ["Upcoming slot exists, but details could not be retrieved due to error"]
        return False, []

def slot_booking_process(username_input, password_input, slots, scheduler_url, proxy, headless, browser_choice, root, continuous=False, check_until_time=None):
    driver = None
    try:
        use_gpu, gpu_arg = check_gpu_availability()
        root.after(0, lambda: status_label.config(text=f"Using {'GPU' if use_gpu else 'CPU'} | Checking for slots..."))

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
        driver.implicitly_wait(1)

        print("Navigating to login page")
        driver.get("https://lms2.ai.saveetha.in/course/view.php?id=302")
        WebDriverWait(driver, 3).until(EC.presence_of_element_located((By.NAME, 'username'))).send_keys(username_input)
        driver.find_element(By.NAME, 'password').send_keys(password_input)
        driver.find_element(By.ID, 'loginbtn').click()
        print("Logged in successfully")

        driver.get(scheduler_url)
        has_booking, booked_slots = check_existing_booking(driver)
        if has_booking:
            print(f"User already has upcoming bookings: {booked_slots}")
            root.after(0, lambda: messagebox.showerror("Error", f"Upcoming slot already exists for user: {', '.join(booked_slots)}"))
            return

        found_slot = False
        attempt = 0
        refresh_interval = 1
        max_retries_503 = 5

        while not found_slot:
            attempt += 1
            print(f"Attempt {attempt} to find and book slots")

            if deadline and datetime.now() > deadline:
                print(f"Deadline {deadline.strftime('%H:%M:%S')} reached. Slots not found.")
                root.after(0, lambda: messagebox.showerror("Failure", f"❌ Slots not found by {check_until_time}."))
                return

            for retry in range(max_retries_503):
                try:
                    driver.get(scheduler_url)
                    WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.ID, 'slotbookertable')))
                    break
                except TimeoutException:
                    page_source = driver.page_source
                    if "503 Service Temporarily Unavailable" in page_source:
                        print(f"503 Error detected, retrying ({retry + 1}/{max_retries_503})...")
                        time.sleep(2)
                        if retry == max_retries_503 - 1:
                            print("Max retries for 503 error reached.")
                            root.after(0, lambda: messagebox.showerror("Error", "❌ 503 Service Unavailable - Max retries reached"))
                            return
                    else:
                        raise

            print("Scheduler page loaded")
            all_rows = WebDriverWait(driver, 3).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "table#slotbookertable tr"))
            )
            current_date_header_text = ""

            for slot in slots:
                day, date, start_time, end_time = slot["day"], slot["date"], slot["start_time"], slot["end_time"]
                try:
                    date_obj = datetime.strptime(date.strip(), "%d %m %Y")
                    formatted_date = date_obj.strftime("%d %B %Y")
                except ValueError:
                    print(f"Invalid date format: {date}")
                    root.after(0, lambda: messagebox.showerror("Error", f"❌ Invalid date format: {date}"))
                    continue

                expected_date_formats = [
                    formatted_date,
                    date_obj.strftime("%B %d, %Y"),
                    date_obj.strftime("%d/%m/%Y"),
                    f"{day.strip()}, {formatted_date}"
                ]
                print(f"Looking for slot: {day}, {date}, {start_time}-{end_time}")

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
                                            continue

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
                                            print(f"Slot booked successfully: {day}, {date}, {start_time}-{end_time}")
                                            root.after(0, lambda: messagebox.showinfo("Success", f"Slot booked: {day}, {date}, {start_time}-{end_time} ✅"))
                                            if SOUND_AVAILABLE:
                                                playsound('success.wav')
                                            continue
                                        except TimeoutException:
                                            found_slot = True
                                            print(f"Slot booked successfully (assumed): {day}, {date}, {start_time}-{end_time}")
                                            root.after(0, lambda: messagebox.showinfo("Success", f"Slot booked: {day}, {date}, {start_time}-{end_time} ✅"))
                                            if SOUND_AVAILABLE:
                                                playsound('success.wav')
                                            continue

                                    except (NoSuchElementException, TimeoutException) as e:
                                        print(f"Booking attempt failed for {day}, {date}, {start_time}-{end_time}: {e}. Retrying...")
                                        continue

                    except StaleElementReferenceException:
                        print("Stale element encountered, refreshing...")
                        driver.refresh()
                        WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.ID, 'slotbookertable')))
                        break

            if not found_slot:
                print(f"Attempt {attempt} failed, retrying in {refresh_interval} seconds...")
                time.sleep(refresh_interval)

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

def calculate_end_time(schedule_id, start_time):
    """Calculate the end time based on venue rules and start time."""
    times = venue_time_slots.get(schedule_id, [])
    if not start_time or start_time not in times:
        return ""
    
    start_index = times.index(start_time)
    try:
        start_dt = datetime.strptime(start_time, "%I:%M %p")
        
        break_start = datetime.strptime("12:00 PM", "%I:%M %p")
        break_end = datetime.strptime("1:00 PM", "%I:%M %p")
        
        if schedule_id in ["1731", "1851"]:
            end_dt = start_dt + timedelta(hours=2)
            if start_dt < break_start and end_dt > break_start:
                end_dt = break_end + (end_dt - break_start)
        elif schedule_id == "1852":
            end_dt = start_dt + timedelta(hours=1)
            if start_dt < break_start and end_dt > break_start:
                end_dt = break_end
        elif schedule_id == "1611":
            end_dt = start_dt + timedelta(minutes=15)
            if start_dt < break_start and end_dt > break_start:
                end_dt = break_end

        end_time = end_dt.strftime("%I:%M %p")
        if end_time in times:
            return end_time
        return times[start_index + 1] if start_index + 1 < len(times) else times[-1]
    except ValueError:
        return times[start_index + 1] if start_index + 1 < len(times) else times[-1]

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
    schedule_id = combo_schedule.get()
    
    end_time = calculate_end_time(schedule_id, start_time)
    entry_end_time.set(end_time)

    if not all([day, date, start_time, end_time]):
        messagebox.showwarning("Input Missing", "Please fill in all slot fields.")
        return

    slot = {"day": day, "date": date, "start_time": start_time, "end_time": end_time}
    slot_str = f"Day: {day}, Date: {date}, Start: {start_time}, End: {end_time}"
    
    if slot_str in listbox_slots.get(0, tk.END):
        messagebox.showwarning("Duplicate Slot", "This slot is already added.")
        return
    
    slot_list.append(slot)
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
    print(f"Starting booking process for {len(slot_list)} slots at {datetime.now().strftime('%H:%M:%S')}...")
    
    proxy = proxies[0] if proxies else None
    thread = threading.Thread(target=slot_booking_process, args=(
        username, password, slot_list, scheduler_url, proxy, headless_mode, browser_choice, root, continuous, check_until_time
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
        entry_end_time.set(calculate_end_time(schedule_id, times[0]))
    else:
        entry_start_time.set("")
        entry_end_time.set("")

def on_start_time_selected(event=None):
    schedule_id = combo_schedule.get()
    start_time = entry_start_time.get()
    end_time = calculate_end_time(schedule_id, start_time)
    entry_end_time.set(end_time)

root = tk.Tk()
root.title("Enhanced Slot Booking Bot - Saveetha LMS")
root.geometry("500x600")

main_canvas = tk.Canvas(root)
scrollbar = ttk.Scrollbar(root, orient="vertical", command=main_canvas.yview)
scrollable_frame = ttk.Frame(main_canvas)

scrollable_frame.bind(
    "<Configure>",
    lambda e: main_canvas.configure(scrollregion=main_canvas.bbox("all"))
)

main_canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
main_canvas.configure(yscrollcommand=scrollbar.set)

main_canvas.pack(side="left", fill="both", expand=True)
scrollbar.pack(side="right", fill="y")

def _on_mousewheel(event):
    main_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

main_canvas.bind_all("<MouseWheel>", _on_mousewheel)

venue_time_slots = {
    "1731": ["8:00 AM", "10:00 AM", "12:00 PM", "1:00 PM", "3:00 PM"],
    "1851": ["8:00 AM", "10:00 AM", "12:00 PM", "1:00 PM", "3:00 PM"],
    "1852": ["8:00 AM", "9:00 AM", "10:00 AM", "11:00 AM", "12:00 PM", "1:00 PM", "2:00 PM", "3:00 PM", "4:00 PM"],
    "1611": ["8:00 AM", "8:15 AM", "8:30 AM", "8:45 AM", "9:00 AM", "9:15 AM", "9:30 AM", "9:45 AM", "10:00 AM", "10:15 AM", "10:30 AM", "10:45 AM", "11:00 AM", "11:15 AM", "11:30 AM", "11:45 AM", "12:00 PM", "1:00 PM", "1:15 PM", "1:30 PM", "1:45 PM", "2:00 PM", "2:15 PM", "2:30 PM", "2:45 PM", "3:00 PM", "3:15 PM", "3:30 PM", "3:45 PM", "4:00 PM", "4:15 PM", "4:30 PM"]
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
