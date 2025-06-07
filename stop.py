from tkinter import messagebox
import schedule
from components import root, status_label
from globals import active_drivers, active_threads, scheduled_time

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
            active_drivers.remove(driver)

    global active_threads
    active_threads = []
    print("Cleared tracked threads.")

    root.after(0, lambda: messagebox.showinfo("Stopped", "All booking processes and schedules have been stopped."))
    root.after(0, lambda: status_label.config(text="Status: Stopped"))