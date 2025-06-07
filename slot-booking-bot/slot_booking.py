from selenium.webdriver.common.action_chains import ActionChains
import tkinter as tk
from tkinter import ttk, messagebox
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    StaleElementReferenceException,
    NoSuchElementException,
    TimeoutException,
    ElementClickInterceptedException,
    WebDriverException
)
import threading
import re
import time
import os
from datetime import datetime, timedelta
import schedule
from gpu import check_gpu_availability, SOUND_AVAILABLE
from gti import _generate_interval_start_times
from globals import active_drivers
from components import root, status_label
try:
    from playsound import playsound
except ImportError:
    playsound = None

def slot_booking_process(username_input, password_input, day, date, start_time, end_time, scheduler_url, proxy, headless, browser_choice, root, continuous=False, check_until_time=None):
    driver = None
    try:
        # Check GPU availability
        use_gpu, gpu_arg = check_gpu_availability()
        root.after(0, lambda: status_label.config(text=f"Using {'GPU' if use_gpu else 'CPU'} | Initializing..."))

        # Validate proxy
        if proxy:
            if not re.match(r'^http://[a-zA-Z0-9.-]+:[0-9]+$', proxy):
                print(f"Invalid proxy format: {proxy}")
                root.after(0, lambda: messagebox.showerror("Error", f"Invalid proxy format: {proxy}. Use http://host:port"))
                return

        # Parse deadline
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

        # Browser setup
        if browser_choice == "Chrome":
            options = ChromeOptions()
            if headless:
                options.add_argument("--headless=new")
            else:
                options.add_argument("--start-maximized")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument(gpu_arg)
            options.add_argument("--window-size=1280,720")
            options.add_argument("--disable-extensions")
            options.add_argument("--blink-settings=imagesEnabled=false")
            options.add_argument("--page-load-strategy=eager")
            if proxy:
                options.add_argument(f"--proxy-server={proxy}")
            options.add_experimental_option("prefs", {"profile.managed_default_content_settings.images": 2})
            driver = webdriver.Chrome(options=options)
        elif browser_choice == "Firefox":
            options = FirefoxOptions()
            if headless:
                options.add_argument("--headless")
            if proxy:
                host, port = proxy.replace("http://", "").split(":")
                options.set_preference("network.proxy.type", 1)
                options.set_preference("network.proxy.http", host)
                options.set_preference("network.proxy.http_port", int(port))
            options.set_preference("permissions.default.image", 2)
            options.set_preference("dom.ipc.processCount", 8)
            driver = webdriver.Firefox(options=options)
        elif browser_choice == "Edge":
            options = EdgeOptions()
            if headless:
                options.add_argument("--headless")
            else:
                options.add_argument("--start-maximized")
            options.add_argument("--disable-gpu")
            options.add_argument("--window-size=1280,720")
            options.add_argument("--blink-settings=imagesEnabled=false")
            options.add_argument("--page-load-strategy=eager")
            if proxy:
                options.add_argument(f"--proxy-server={proxy}")
            driver = webdriver.Edge(options=options)
        else:
            raise ValueError("Unsupported browser")

        active_drivers.append(driver)
        print(f"Running in {browser_choice} {'headless' if headless else 'visible'} mode")
        driver.implicitly_wait(0.2)

        # Login
        root.after(0, lambda: status_label.config(text="Logging in..."))
        driver.get("https://lms2.ai.saveetha.in/course/view.php?id=302")
        try:
            username_field = WebDriverWait(driver, 5, poll_frequency=0.1).until(EC.presence_of_element_located((By.NAME, 'username')))
            username_field.send_keys(username_input)
            driver.find_element(By.NAME, 'password').send_keys(password_input)
            driver.find_element(By.ID, 'loginbtn').click()
            print(f"Logged in. Current URL: {driver.current_url}, Title: {driver.title}")
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

            if deadline and datetime.now() > deadline:
                print(f"Deadline {deadline.strftime('%H:%M:%S')} reached.")
                root.after(0, lambda: messagebox.showerror("Failure", f"❌ Slot not found for {day}, {date}, {start_time}-{end_time}."))
                return

            try:
                driver.get(scheduler_url)
                print(f"Navigated to scheduler URL: {scheduler_url}, Current URL: {driver.current_url}, Title: {driver.title}")
                page_source = driver.page_source
                if "503 Service Unavailable" in page_source or "Service Temporarily Unavailable" in page_source or "ERR_CONNECTION_REFUSED" in page_source:
                    print(f"Detected 503/Connection error on attempt {attempt}. Retrying...")
                    root.after(0, lambda: status_label.config(text=f"503 Error detected. Retrying... (Attempt {attempt})"))
                    time.sleep(min(refresh_interval * (2 ** (attempt % 5)), 5))
                    continue

                WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.CSS_SELECTOR, "table#slotbookertable, table.generaltable")))
            except TimeoutException as e:
                print(f"Timeout waiting for slot table: {e}")
                root.after(0, lambda: messagebox.showerror("Error", f"❌ Timeout loading slot table: {str(e)}"))
                return
            except WebDriverException as e:
                print(f"WebDriver error navigating to scheduler: {e}")
                root.after(0, lambda: messagebox.showerror("Error", f"❌ WebDriver error: {str(e)}"))
                return

            try:
                WebDriverWait(driver, 0.5).until(
                    EC.presence_of_element_located((By.XPATH, "//button[contains(@class, 'btn') and contains(text(), 'Cancel booking')]"))
                )
                print("Existing booking found. Stopping process.")
                root.after(0, lambda: messagebox.showwarning("Booking Exists", "You already have an upcoming slot booked. Please cancel it to book a new slot."))
                return
            except TimeoutException:
                pass

            try:
                WebDriverWait(driver, 0.5).until(
                    EC.presence_of_element_located((By.XPATH, "//th[contains(text(), 'Other participants')]"))
                )
                print("Frozen slot detected. Stopping process.")
                root.after(0, lambda: messagebox.showwarning("Slot Frozen", "Your slot is frozen. Please resolve this to book a new slot."))
                return
            except TimeoutException:
                pass

            for _ in range(3):
                try:
                    all_rows = WebDriverWait(driver, 1, poll_frequency=0.1).until(
                        EC.presence_of_all_elements_located((By.CSS_SELECTOR, "table#slotbookertable tbody tr"))
                    )
                    current_date_in_table = ""
                    for row in all_rows:
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
                                        try:
                                            note_field = WebDriverWait(driver, 3, poll_frequency=0.1).until(EC.visibility_of_element_located((By.ID, "id_studentnote_editoreditable")))
                                            note_field.send_keys("Booking for project work (automated)")
                                            submit_button = WebDriverWait(driver, 1, poll_frequency=0.1).until(EC.element_to_be_clickable((By.ID, "id_submitbutton")))
                                            submit_button.click()
                                            try:
                                                WebDriverWait(driver, 2, poll_frequency=0.1).until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'confirmed') or contains(text(), 'success')]")))
                                                print("Booking confirmed.")
                                            except TimeoutException:
                                                print("No confirmation text, checking booked slot...")
                                                WebDriverWait(driver, 2, poll_frequency=0.1).until(EC.presence_of_element_located((By.XPATH, f"//tr[td[contains(text(), '{formatted_date_for_comparison}')]][td[contains(text(), '{start_time}')]][td[contains(text(), '{end_time}')]]")))
                                                print("Slot found in booked section.")
                                            root.after(0, lambda: messagebox.showinfo("Success", f"Slot booked: {day}, {date}, {start_time}-{end_time} ✅"))
                                            if SOUND_AVAILABLE and playsound:
                                                try:
                                                    if os.path.exists('success.wav'):
                                                        playsound('success.wav')
                                                    else:
                                                        print("Sound file 'success.wav' not found.")
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
                    break
                except StaleElementReferenceException:
                    print("Stale element detected, retrying...")
                    time.sleep(0.1)
                    continue
                except Exception as e:
                    print(f"Row processing error: {e}")
                    continue

            if not continuous:
                print("Slot not found in single attempt.")
                root.after(0, lambda: messagebox.showerror("Failure", f"❌ Slot not found for {day}, {date}, {start_time}-{end_time}."))
                return
            time.sleep(refresh_interval)

    except Exception as e:
        print(f"Unexpected error: {type(e).__name__}: {str(e)}")
        root.after(0, lambda: messagebox.showerror("Error", f"❌ {type(e).__name__}: {str(e)}"))
    finally:
        if driver:
            print("Closing browser")
            if driver in active_drivers:
                active_drivers.remove(driver)
            try:
                driver.quit()
            except Exception as e:
                print(f"Error closing driver: {e}")