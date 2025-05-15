# Chat-Bot-for-booking-slots

## Slot Booking Bot - Project Update Report

## Overview:

 The Slot Booking Bot is an automated tool designed to efficiently book slots on the Saveetha LMS platform, even in high-traffic conditions. This report details the updates, new features, and enhancements made 
to improve its performance, usability, and robustness.

### Key Updates and Enhancements:

## 1. Headless Mode Fix and Optimization

Fix: Corrected the "Run Headless" option for Chrome, Firefox, and Edge browsers.

Improvement: Added logging to confirm headless mode activation.

Benefit: Enables faster, UI-free execution with reduced resource usage.

## 2. Cross-Browser Support

Feature: Added support for Chrome, Firefox, and Edge.

Implementation: Included a GUI dropdown for browser selection with specific configurations (e.g., headless mode, proxy support).

Benefit: Increases flexibility across different browser environments.

## 3. GUI Enhancements
Day Selection: Replaced text entry with a dropdown (Combobox) listing all days of the week.

Date Picker: Added a tkcalendar-based calendar picker, supporting both selection and manual typing (e.g., "6 May 2025").

Dropdowns: Converted day, schedule, and browser fields to dropdowns for easier, error-free input.

## 4. Proxy Rotation

Feature: Introduced proxy rotation to prevent IP blocking.

Implementation: Users can input a comma-separated proxy list, cycled per booking attempt.

Benefit: Enhances reliability in high-traffic or restricted scenarios.

## 5. Multi-Slot Booking

Feature: Enabled parallel booking of multiple slots using threading.

Implementation: Users can add slots to a list via the GUI for simultaneous booking.

Benefit: Speeds up the process for users needing multiple slots.

## 6. Sound Notification
Feature: Added a sound alert for successful bookings.
 
Implementation: Uses playsound library to play a success.wav file.

Benefit: Provides instant feedback, especially in headless mode.

## 7. Improved Slot Booking Logic

Enhancement: Optimized retry mechanism and switched to CSS selectors for faster, more reliable element location.

Benefit: Boosts speed and success rate under heavy traffic.

## 8. Error Handling and User Feedback
Enhancement: Improved error handling with GUI popups and detailed logging.
    
Benefit: Offers clear, actionable feedback for troubleshooting.
    
### Technical Improvements

Speed: Reduced wait times and optimized element locators.

Reliability: Enhanced stale element handling with retries.
    
Logging: Added detailed logs for progress tracking and debugging.

### Prerequisites and Setup

## To run the bot, ensure the following:

Libraries: Install selenium, tkcalendar, and playsound via pip.

Browser Drivers: Set up ChromeDriver, GeckoDriver, and EdgeDriver (links in documentation).
    
Sound File: Include a success.wav file in the project directory.
    
Instructions: Detailed setup steps are provided in the repository.

## code:
```py
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
from selenium.common.exceptions import StaleElementReferenceException, NoSuchElementException, TimeoutException
import threading
import re
import time
try:
    from playsound import playsound
    SOUND_AVAILABLE = True
except ImportError:
    SOUND_AVAILABLE = False

# Global list to hold slot details
slot_list = []

def slot_booking_process(username_input, password_input, day, date, start_time, end_time, scheduler_url, proxy, headless, browser_choice, root):
    driver = None
    try:
        # Set up browser options based on user selection
        if browser_choice == "Chrome":
            options = ChromeOptions()
            if headless:
                options.add_argument("--headless")
                options.add_argument("--disable-gpu")
                options.add_argument("--no-sandbox")
                options.add_argument("--disable-dev-shm-usage")
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

        print(f"Running in {browser_choice} {'headless' if headless else 'visible'} mode")
        driver.implicitly_wait(2)

        # Login
        driver.get("https://lms2.ai.saveetha.in/course/view.php?id=302")
        WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.NAME, 'username'))).send_keys(username_input)
        driver.find_element(By.NAME, 'password').send_keys(password_input)
        driver.find_element(By.ID, 'loginbtn').click()

        # Direct navigation to scheduler
        driver.get(scheduler_url)
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, 'slotbookertable')))

        # Slot finding with retry mechanism
        found_slot = False
        max_attempts = 5
        attempt = 0

        while attempt < max_attempts and not found_slot:
            attempt += 1
            print(f"Attempt {attempt}/{max_attempts} to find and book slot")
            
            all_rows = WebDriverWait(driver, 5).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "table#slotbookertable tr"))
            )
            current_date_header_text = ""
            expected_day_date_str = f"{day.strip()}, {date.strip()}"

            for i in range(len(all_rows)):
                try:
                    all_rows = WebDriverWait(driver, 5).until(
                        EC.presence_of_all_elements_located((By.CSS_SELECTOR, "table#slotbookertable tr"))
                    )
                    row = all_rows[i]
                    row_text = row.text.strip()

                    # Identify date header
                    date_header_match = re.search(r'\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}\b', row_text)
                    if date_header_match:
                        current_date_header_text = date_header_match.group(0).strip()
                        if expected_day_date_str in current_date_header_text:
                            print(f"Matched date header: {current_date_header_text}")
                        else:
                            current_date_header_text = ""
                            continue

                    # Check slots under the correct date
                    if expected_day_date_str in current_date_header_text:
                        time_cells = row.find_elements(By.TAG_NAME, 'td')
                        for cell in time_cells:
                            cell_text = cell.text.strip()
                            if start_time.strip() in cell_text and end_time.strip() in cell_text:
                                try:
                                    book_button = row.find_element(By.XPATH, ".//button[contains(text(), 'Book slot')]")
                                    driver.execute_script("arguments[0].scrollIntoView(true);", book_button)
                                    WebDriverWait(driver, 5).until(EC.element_to_be_clickable(book_button))
                                    book_button.click()

                                    # Fill note and submit
                                    note_field = WebDriverWait(driver, 5).until(
                                        EC.visibility_of_element_located((By.ID, "id_studentnote_editoreditable"))
                                    )
                                    note_field.send_keys('reep')
                                    submit_button = WebDriverWait(driver, 5).until(
                                        EC.element_to_be_clickable((By.ID, "id_submitbutton"))
                                    )
                                    submit_button.click()

                                    found_slot = True
                                    print("Slot booked successfully!")
                                    root.after(0, lambda: messagebox.showinfo("Success", f"Slot booked: {day}, {date}, {start_time}-{end_time} ✅"))
                                    if SOUND_AVAILABLE:
                                        playsound('success.wav')
                                    return

                                except (NoSuchElementException, TimeoutException):
                                    print("Book button not found or not clickable, retrying...")
                                    continue

                except StaleElementReferenceException:
                    print("Stale element encountered, refreshing rows...")
                    continue

            if not found_slot:
                print(f"Attempt {attempt} failed, retrying in 1 second...")
                time.sleep(1)

        if not found_slot:
            print("No slot found after all attempts.")
            root.after(0, lambda: messagebox.showerror("Failure", f"❌ No matching slot found for {day}, {date}, {start_time}-{end_time} after retries."))

    except TimeoutException as e:
        print(f"Timeout error: {e}")
        root.after(0, lambda: messagebox.showerror("Error", f"❌ Timeout error: {e}"))
    except NoSuchElementException as e:
        print(f"Element not found: {e}")
        root.after(0, lambda: messagebox.showerror("Error", f"❌ Element not found: {e}"))
    except Exception as e:
        print(f"Unexpected error: {e}")
        root.after(0, lambda: messagebox.showerror("Error", f"❌ Unexpected error: {e}"))
    finally:
        if driver:
            print("Closing browser.")
            driver.quit()

def add_slot():
    day = combo_day.get()
    date = entry_date.get()
    start_time = entry_start_time.get()
    end_time = entry_end_time.get()
    if not all([day, date, start_time, end_time]):
        messagebox.showwarning("Input Missing", "Please fill in all slot fields.")
        return
    slot = {"day": day, "date": date, "start_time": start_time, "end_time": end_time}
    slot_list.append(slot)
    slot_str = f"Day: {day}, Date: {date}, Start: {start_time}, End: {end_time}"
    listbox_slots.insert(tk.END, slot_str)
    # Clear the fields
    combo_day.set("")
    entry_date.set_date("")
    entry_start_time.delete(0, tk.END)
    entry_end_time.delete(0, tk.END)

def remove_slot():
    selected = listbox_slots.curselection()
    if selected:
        index = selected[0]
        listbox_slots.delete(index)
        slot_list.pop(index)

def run_booking():
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

    # Assign proxies to slots
    for i, slot in enumerate(slot_list):
        proxy = proxies[i % len(proxies)] if proxies else None
        thread = threading.Thread(target=slot_booking_process, args=(username, password, slot["day"], slot["date"], slot["start_time"], slot["end_time"], scheduler_url, proxy, headless_mode, browser_choice, root))
        thread.start()

# --- GUI Layout ---
root = tk.Tk()
root.title("Enhanced Slot Booking Bot - Saveetha LMS")
root.geometry("500x750")

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

# Day dropdown
ttk.Label(root, text="Day").pack(pady=5)
days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
combo_day = ttk.Combobox(root, values=days, state="readonly")
combo_day.pack()

# Date picker with typing enabled
ttk.Label(root, text="Date (Select or Type, e.g., 6 May 2025)").pack(pady=5)
entry_date = DateEntry(root, width=30, date_pattern="dd mm yyyy", state="normal")
entry_date.pack()

ttk.Label(root, text="Start Time (e.g., 10:00 AM)").pack(pady=5)
entry_start_time = ttk.Entry(root, width=30)
entry_start_time.pack()

ttk.Label(root, text="End Time (e.g., 12:00 PM)").pack(pady=5)
entry_end_time = ttk.Entry(root, width=30)
entry_end_time.pack()

# Buttons to add and remove slots
button_add_slot = ttk.Button(root, text="Add Slot", command=add_slot)
button_add_slot.pack(pady=5)

button_remove_slot = ttk.Button(root, text="Remove Selected Slot", command=remove_slot)
button_remove_slot.pack(pady=5)

# Listbox to display added slots
frame_slots = ttk.Frame(root)
frame_slots.pack(pady=10)
listbox_slots = tk.Listbox(frame_slots, height=5, width=60)
scrollbar = ttk.Scrollbar(frame_slots, orient="vertical", command=listbox_slots.yview)
listbox_slots.config(yscrollcommand=scrollbar.set)
listbox_slots.pack(side="left", fill="both", expand=True)
scrollbar.pack(side="right", fill="y")

# Headless mode checkbox
headless_var = tk.BooleanVar()
check_headless = ttk.Checkbutton(root, text="Run Headless (Faster, No Browser UI)", variable=headless_var)
check_headless.pack(pady=10)

# Book slots button
button_book = ttk.Button(root, text="Book Slots Now", command=run_booking)
button_book.pack(pady=20)

root.mainloop()

```



### Summary of Benefits
Reliability: Proxy rotation and retry logic improve performance in tough conditions.
    
Speed: Faster execution through optimized logic and selectors.
    
 Usability: GUI enhancements reduce errors and improve interaction.
    
Flexibility: Cross-browser and multi-slot features meet diverse needs.
    
Feedback: Sound alerts and error messages keep users informed.

### Conclusion
   
The Slot Booking Bot is now faster, more reliable, and user-friendly, with added flexibility for various use cases. These updates make it ready for GitHub upload, supported by clear documentation and well- 
commented code.

