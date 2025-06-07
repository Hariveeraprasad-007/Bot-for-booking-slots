import threading
from datetime import datetime
from tkinter import messagebox
from components import entry_username, entry_password, combo_schedule, combo_browser, headless_var, entry_proxies, entry_check_until, root
from globals import slot_list, active_threads, scheduled_time
from slot_booking import slot_booking_process

# Thread lock for safety
thread_lock = threading.Lock()

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
        root.after(0, lambda: messagebox.showerror("Error", "Invalid schedule selected."))
        return
    if not slot_list:
        root.after(0, lambda: messagebox.showwarning("No Slots", "Please add at least one slot to book."))
        return

    scheduler_url = urls[choice]

    print(f"Starting booking process at {datetime.now().strftime('%H:%M:%S')}...")
    for i, slot in enumerate(slot_list):
        proxy = proxies[i % len(proxies)] if proxies else None
        thread = threading.Thread(target=slot_booking_process, args=(
            username, password, slot["day"], slot["date"], slot["start_time"], slot["end_time"],
            scheduler_url, proxy, headless_mode, browser_choice, root, continuous, check_until_time
        ))
        with thread_lock:
            active_threads.append(thread)
        thread.start()