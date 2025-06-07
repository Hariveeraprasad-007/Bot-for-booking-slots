import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta
from config import venue_details
from components import entry_date, combo_day, entry_start_time, entry_end_time, combo_schedule, listbox_slots
from globals import slot_list
from gti import _generate_interval_start_times

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

        expected_start_times = []
        if "fixed_start_times_str" in config:
            expected_start_times = config["fixed_start_times_str"]
        elif "generate_all_intervals" in config and config["generate_all_intervals"]:
            expected_start_times = _generate_interval_start_times(
                overall_start_dt, overall_end_dt, config["slot_duration_minutes"],
                break_start_dt, break_end_dt
            )
        
        if start_time not in expected_start_times:
            messagebox.showwarning("Invalid Start Time", f"The selected start time '{start_time}' is not a valid start time for venue {selected_venue_id}.")
            return
            
    slot = {"day": day, "date": date, "start_time": start_time, "end_time": end_time}
    slot_list.append(slot)
    slot_str = f"Day: {day}, Date: {date}, Start: {start_time}, End: {end_time}"
    listbox_slots.insert(tk.END, slot_str)
    entry_start_time.set("")
    entry_end_time.set("")