import tkinter as tk
from tkinter import ttk, messagebox
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options as ChromeOptions # Use Chrome options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import StaleElementReferenceException, NoSuchElementException, TimeoutException
import threading
import re # Import regex for more flexible date parsing

# Function to run the slot booking process
def slot_booking_process(username_input, password_input, day, date, start_time, end_time, scheduler_url, headless, root):
    driver = None
    try:
        # Set up Chrome options
        chrome_options = ChromeOptions()
        if headless:
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--disable-gpu") # Recommended for headless on some OS
            chrome_options.add_argument("--no-sandbox") # Recommended for headless
            chrome_options.add_argument("--disable-dev-shm-usage") # Recommended for headless

        # Initialize WebDriver
        driver = webdriver.Chrome(options=chrome_options)
        driver.implicitly_wait(5) # Implicit wait for elements to appear

        # Navigate to login page
        driver.get("https://lms2.ai.saveetha.in/course/view.php?id=302")

        # Login
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.NAME, 'username'))).send_keys(username_input)
        driver.find_element(By.NAME, 'password').send_keys(password_input)
        driver.find_element(By.ID, 'loginbtn').click()

        # Navigate to Scheduler page
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, f"//a[@href='{scheduler_url}']"))).click()

        # Wait for the scheduler table to load
        WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.ID, 'slotbookertable')))
        # Use a more specific locator if the table has a unique class or data attribute
        # table_element = driver.find_element(By.ID, 'slotbookertable')

        # Refined Slot Finding Logic
        found_slot = False
        # Get all rows that are not header rows (assuming header rows have 'header' class or similar)
        # You might need to inspect the actual page HTML to get a better locator for data rows vs header rows
        # Example: assuming data rows don't have class 'header'
        rows = WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.XPATH, "//table[@id='slotbookertable']//tr[not(contains(@class, 'header'))]"))
        )

        # Let's refine this further: Iterate through ALL rows and identify context
        all_rows = WebDriverWait(driver, 10).until(
             EC.presence_of_all_elements_located((By.XPATH, "//table[@id='slotbookertable']//tr"))
        )

        current_date_header_text = ""
        expected_day_date_str = f"{day.strip()}, {date.strip()}" # Format expected string

        print(f"Searching for slot: {expected_day_date_str} from {start_time.strip()} to {end_time.strip()}")

        for i in range(len(all_rows)):
            try:
                # Re-find rows inside loop to reduce StaleElementReferenceException risk
                all_rows = WebDriverWait(driver, 10).until(
                     EC.presence_of_all_elements_located((By.XPATH, "//table[@id='slotbookertable']//tr"))
                )
                row = all_rows[i]
                row_text = row.text.strip()

                # Check if this row is a date header row (usually contains month name)
                # This pattern might need adjustment based on the actual site's date format
                date_header_match = re.search(r'\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}\b', row_text)

                if date_header_match:
                    current_date_header_text = date_header_match.group(0).strip()
                    print(f"Found date header: {current_date_header_text}")
                    # Check if this header matches our target date
                    if expected_day_date_str in current_date_header_text:
                         print(f"Matching date header found: {current_date_header_text}")
                    else:
                         # Reset context if it's a new date header that doesn't match
                         current_date_header_text = ""
                         continue # Move to the next row

                # If we are currently under the correct date header context
                if expected_day_date_str in current_date_header_text:
                    print(f"Checking row under date header {current_date_header_text}: {row_text}")
                    # Now check if this *data* row contains the correct start and end times
                    # Look for td elements containing the start and end times
                    # Assuming time is in a specific cell. Adjust locator as needed.
                    # Example: Find a cell that contains the start time and another that contains the end time in the same row
                    try:
                        # Try finding elements with specific text within the row
                        start_time_element = row.find_element(By.XPATH, f".//*[contains(text(), '{start_time.strip()}')]")
                        end_time_element = row.find_element(By.XPATH, f".//*[contains(text(), '{end_time.strip()}')]")

                        print(f"Found elements for times: {start_time.strip()} and {end_time.strip()} in this row.")

                        # Now, find the 'Book slot' button specifically within this row
                        # Look for a button with text 'Book slot' or a similar locator
                        book_button = row.find_element(By.XPATH, ".//button[contains(text(), 'Book slot')]")

                        # Scroll to the button and click it
                        driver.execute_script("arguments[0].scrollIntoView(true);", book_button)
                        WebDriverWait(driver, 10).until(EC.element_to_be_clickable(book_button)) # Wait for button to be clickable
                        book_button.click() # Try standard click first

                        # Wait for the booking confirmation/note field page to load
                        note_field_locator = (By.ID, "id_studentnote_editoreditable") # Adjust locator if ID changes
                        WebDriverWait(driver, 10).until(EC.visibility_of_element_located(note_field_locator))
                        note_field = driver.find_element(*note_field_locator)
                        note_field.send_keys('reep') # Fill the note

                        # Click the submit button
                        submit_button_locator = (By.ID, "id_submitbutton") # Adjust locator if ID changes
                        WebDriverWait(driver, 10).until(EC.element_to_be_clickable(submit_button_locator))
                        driver.find_element(*submit_button_locator).click()

                        found_slot = True
                        print("Slot booked successfully.")
                        # Use root.after to show success message on the main thread
                        root.after(0, lambda: messagebox.showinfo("Success", "Slot booked successfully ✅"))
                        return # Exit the function after booking

                    except NoSuchElementException:
                        # This row is under the correct date header but doesn't contain the specific start/end times or the button
                        # Continue to the next row to check for the time slot
                        print("Row does not contain the specific times or book button.")
                        continue # Check the next row

            except StaleElementReferenceException:
                print("StaleElementReferenceException encountered. Re-finding elements and continuing...")
                # This handles cases where getting `all_rows` or accessing `row` was stale.
                # The loop will re-get `all_rows` in the next iteration.
                continue
            except Exception as e:
                print(f"An unexpected error occurred while processing row {i}: {e}")
                # Log the error but continue trying other rows if possible, or break if error is severe
                # For now, let's break if a serious error occurs within a row
                break # Or continue depending on desired robustness

        # If the loop finishes without finding and booking
        if not found_slot:
            print("No matching slot found.")
            # Use root.after to show failure message on the main thread
            root.after(0, lambda: messagebox.showerror("Failure", "❌ No matching slot found with the specified date, time, and status (like 'Book slot' button available)."))

    except TimeoutException as e:
        print(f"Timeout error: {e}")
        # Use root.after to show error message on the main thread
        root.after(0, lambda: messagebox.showerror("Error", f"❌ Timeout error: Could not find an element within the expected time. The page might not have loaded correctly, or elements have changed."))
    except NoSuchElementException as e:
        print(f"Element not found error: {e}")
        # Use root.after to show error message on the main thread
        root.after(0, lambda: messagebox.showerror("Error", f"❌ Element not found error: Could not locate a required element on the page. The website structure might have changed."))
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        # Use root.after to show error message on the main thread
        root.after(0, lambda: messagebox.showerror("Error", f"❌ An unexpected error occurred: {e}"))

    finally:
        # Ensure the driver is closed even if errors occur
        if driver:
            # Optional: Keep browser open on success for verification (remove driver.quit())
            # For now, let's keep quit for cleanup, but inform the user it will close
            print("Closing browser.")
            driver.quit()
            # Use root.after to inform user browser is closing if needed
            # root.after(0, lambda: messagebox.showinfo("Info", "Browser will close now."))


# Function called by the GUI button
def run_booking():
    username = entry_username.get()
    password = entry_password.get()
    day = entry_day.get()
    date = entry_date.get() # Expected format e.g., "6 May 2025"
    start_time = entry_start_time.get() # Expected format e.g., "10:00 AM"
    end_time = entry_end_time.get()     # Expected format e.g., "12:00 PM"
    choice = combo_schedule.get()
    headless_mode = headless_var.get() # Get state of the headless checkbox

    urls = {
        "1731": "https://lms2.ai.saveetha.in/mod/scheduler/view.php?id=36638", # Adjust URLs if needed
        "1851": "https://lms2.ai.saveetha.in/mod/scheduler/view.php?id=36298",
        "1852": "https://lms2.ai.saveetha.in/mod/scheduler/view.php?id=37641",
        "1611": "https://lms2.ai.saveetha.in/mod/scheduler/view.php?id=36137"
    }

    if choice not in urls:
        messagebox.showerror("Error", "Please select a valid schedule.")
        return
    if not all([username, password, day, date, start_time, end_time]):
         messagebox.showwarning("Input Missing", "Please fill in all fields.")
         return

    scheduler_url = urls[choice]

    # Run slot booking in a separate thread to avoid freezing the GUI
    # Pass the root window to the thread function for thread-safe GUI updates
    thread = threading.Thread(target=slot_booking_process, args=(username, password, day, date, start_time, end_time, scheduler_url, headless_mode, root))
    thread.start()
    # Optionally, disable the button while booking is in progress
    # button_book.config(state=tk.DISABLED)
    # You would need another root.after call at the end of slot_booking_process to re-enable it


# --- GUI Layout ---
root = tk.Tk()
root.title("Slot Booking Bot - Saveetha LMS")
root.geometry("400x550") # Adjusted size

ttk.Label(root, text="Username").pack(pady=5)
entry_username = ttk.Entry(root, width=30)
entry_username.pack()

ttk.Label(root, text="Password").pack(pady=5)
entry_password = ttk.Entry(root, width=30, show="*")
entry_password.pack()

ttk.Label(root, text="Day (e.g., Tuesday)").pack(pady=5)
entry_day = ttk.Entry(root, width=30)
entry_day.pack()

ttk.Label(root, text="Date (e.g., 6 May 2025)").pack(pady=5)
entry_date = ttk.Entry(root, width=30)
entry_date.pack()

ttk.Label(root, text="Start Time (e.g., 10:00 AM)").pack(pady=5)
entry_start_time = ttk.Entry(root, width=30)
entry_start_time.pack()

ttk.Label(root, text="End Time (e.g., 12:00 PM)").pack(pady=5)
entry_end_time = ttk.Entry(root, width=30)
entry_end_time.pack()

ttk.Label(root, text="Select Schedule").pack(pady=5)
combo_schedule = ttk.Combobox(root, values=["1731", "1851", "1852", "1611"], state="readonly") # make combobox readonly
combo_schedule.pack()
combo_schedule.set("1731") # Set a default value

# Headless mode checkbox
headless_var = tk.BooleanVar()
check_headless = ttk.Checkbutton(root, text="Run Headless (No browser window)", variable=headless_var)
check_headless.pack(pady=10)


button_book = ttk.Button(root, text="Book Slot", command=run_booking)
button_book.pack(pady=20)

root.mainloop()
