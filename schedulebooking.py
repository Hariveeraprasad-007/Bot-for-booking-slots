import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta
import threading
import time
import schedule
from config import venue_details
from components import root, entry_schedule_time, combo_schedule, entry_start_time, entry_end_time, combo_day, entry_date, status_label
from gti import _generate_interval_start_times
from runbooking import run_booking

def schedule_booking():
    global scheduled_time
    schedule_time = entry_schedule_time.get().strip()
    if not schedule_time:
        root.after(0, lambda: messagebox.showerror("Error", "Schedule time cannot be empty."))
        return
    try:
        datetime.strptime(schedule_time, "%H:%M")
        schedule.clear()
        scheduled_time = schedule_time
        schedule.every().day.at(schedule_time).do(lambda: run_booking(continuous=True))
        print(f"Scheduled booking daily at {schedule_time}")
        root.after(0, lambda: messagebox.showinfo("Scheduled", f"Booking scheduled daily at {schedule.next_run().strftime('%Y-%m-%d %H:%M:%S')}."))
        root.after(0, lambda: status_label.config(text=f"Status: Scheduled at {schedule_time}"))

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
        root.after(0, lambda: messagebox.showerror("Error", "Invalid time format. Use HH:MM (e.g., 21:03)."))

def on_date_selected(event=None):
    date = entry_date.get()
    try:
        date_obj = datetime.strptime(date.strip(), "%d %m %Y")
        day = date_obj.strftime("%A")
        combo_day.set(day)
    except ValueError:
        combo_day.set("")

def on_schedule_selected(event=None):
    selected_venue_id = combo_schedule.get()
    if selected_venue_id in venue_details:
        config = venue_details[selected_venue_id]
        
        overall_start_dt = datetime.strptime(config["overall_start_time_str"], "%I:%M %p")
        overall_end_dt = datetime.strptime(config["overall_end_time_str"], "%I:%M %p")
        
        break_start_dt = None
        break_end_dt = None
        if config["break_time_str"]:
            break_start_dt = datetime.strptime(config["break_time_str"][0], "%I:%M %p")
            break_end_dt = datetime.strptime(config["break_time_str"][1], "%I:%M %p")

        start_time_options = []
        if "fixed_start_times_str" in config:
            start_time_options = config["fixed_start_times_str"]
        elif "generate_all_intervals" in config and config["generate_all_intervals"]:
            start_time_options = _generate_interval_start_times(
                overall_start_dt, overall_end_dt, config["slot_duration_minutes"],
                break_start_dt, break_end_dt
            )
        
        entry_start_time['values'] = start_time_options
        
        if start_time_options:
            entry_start_time.set(start_time_options[0])
            on_start_time_selected()
        else:
            entry_start_time.set("")
            entry_end_time.set("")
    else:
        entry_start_time['values'] = []
        entry_start_time.set("")
        entry_end_time.set("")

def on_start_time_selected(event=None):
    selected_start_time_str = entry_start_time.get()
    selected_venue_id = combo_schedule.get()

    if selected_start_time_str and selected_venue_id in venue_details:
        config = venue_details[selected_venue_id]
        try:
            start_dt_obj = datetime.strptime(selected_start_time_str.strip(), "%I:%M %p")
            overall_end_dt = datetime.strptime(config["overall_end_time_str"], "%I:%M %p")

            potential_end_dt_obj = start_dt_obj + timedelta(minutes=config["slot_duration_minutes"])
            actual_end_dt_obj = min(potential_end_dt_obj, overall_end_dt)
            
            end_time_str = actual_end_dt_obj.strftime("%I:%M %p").lstrip('0').replace(' 0', ' ').replace(':00 ', ':00').replace('AM',' AM').replace('PM',' PM')
            entry_end_time.set(end_time_str)
        except ValueError:
            entry_end_time.set("Invalid Time")
    else:
        entry_end_time.set("")