
import tkinter as tk
from tkinter import ttk, messagebox
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import StaleElementReferenceException
import time
import threading

def slot_booking(username_input, password_input, day, date, start_time, end_time, scheduler_url):
    driver = webdriver.Chrome()
    driver.get("https://lms2.ai.saveetha.in/course/view.php?id=302")
    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.NAME, 'username'))).send_keys(username_input)
    driver.find_element(By.NAME, 'password').send_keys(password_input)
    driver.find_element(By.ID, 'loginbtn').click()
    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, f"//a[@href='{scheduler_url}']"))).click()
    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, 'slotbookertable')))
    expected_day_date = f"{day}, {date}".strip()
    current_date = ""
    rows = driver.find_elements(By.XPATH, "//table//tr")
    for i in range(len(rows)):
        try:
            rows = driver.find_elements(By.XPATH, "//table//tr")
            row = rows[i]
            row_text = row.text.strip()
            if any(month in row_text for month in [
                "January", "February", "March", "April", "May", "June",
                "July", "August", "September", "October", "November", "December"
            ]):
                current_date = row_text.split("\n")[0].strip()
            if expected_day_date in current_date:
                if start_time in row_text and end_time in row_text:
                    try:
                        book_button = row.find_element(By.XPATH, ".//button[contains(text(), 'Book slot')]")
                        driver.execute_script("arguments[0].scrollIntoView(true);", book_button)
                        time.sleep(1)
                        driver.execute_script("arguments[0].click();", book_button)
                        note_field = WebDriverWait(driver, 10).until(
                            EC.presence_of_element_located((By.ID, "id_studentnote_editoreditable"))
                        )
                        note_field.send_keys('reep')
                        driver.find_element(By.ID, "id_submitbutton").click()
                        messagebox.showinfo("Success", "Slot booked successfully ✅")
                        return
                    except Exception as e:
                        messagebox.showerror("Error", f"❌ Error during booking: {e}")
                else:
                    messagebox.showwarning("Warning", "⚠️ Start and end time do not match.")
            else:
                continue
        except StaleElementReferenceException:
            continue
    messagebox.showerror("Failure", "❌ No matching slot found.")
    driver.quit()

def run_booking():
    username = entry_username.get()
    password = entry_password.get()
    day = entry_day.get()
    date = entry_date.get()
    start_time = entry_start_time.get()
    end_time = entry_end_time.get()
    choice = combo_schedule.get()

    urls = {
        "1731": "https://lms2.ai.saveetha.in/mod/scheduler/view.php?id=36638",
        "1851": "https://lms2.ai.saveetha.in/mod/scheduler/view.php?id=36298",
        "1852": "https://lms2.ai.saveetha.in/mod/scheduler/view.php?id=37641",
        "1611": "https://lms2.ai.saveetha.in/mod/scheduler/view.php?id=36137"
    }

    if choice not in urls:
        messagebox.showerror("Error", "Please select a valid schedule.")
        return

    # Run slot booking in a separate thread to avoid freezing the GUI
    threading.Thread(target=slot_booking, args=(username, password, day, date, start_time, end_time, urls[choice])).start()

# GUI Layout
root = tk.Tk()
root.title("Slot Booking Bot - Saveetha LMS")
root.geometry("400x450")

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
combo_schedule = ttk.Combobox(root, values=["1731", "1851", "1852", "1611"])
combo_schedule.pack()

ttk.Button(root, text="Book Slot", command=run_booking).pack(pady=20)

root.mainloop()
