import tkinter as tk
from tkinter import ttk
from tkcalendar import DateEntry
from config import venue_details

# Initialize Tkinter root
root = tk.Tk()
root.title("Enhanced Slot Booking Bot - Saveetha LMS")
root.geometry("500x950")

# GUI components
ttk.Label(root, text="Username").pack(pady=5)
entry_username = ttk.Entry(root, width=30)
entry_username.pack()

ttk.Label(root, text="Password").pack(pady=5)
entry_password = ttk.Entry(root, width=30, show="*")
entry_password.pack()

ttk.Label(root, text="Select Schedule").pack(pady=5)
combo_schedule = ttk.Combobox(root, values=list(venue_details.keys()), state="readonly")
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

ttk.Label(root, text="Check Until Time (HH:MM, e.g., 21:30, optional)").pack(pady=5)
entry_check_until = ttk.Entry(root, width=30)
entry_check_until.pack()

ttk.Label(root, text="Date (Select or Type, e.g., 16 May 2025)").pack(pady=5)
entry_date = DateEntry(root, width=30, date_pattern="dd mm Y", state="normal")
entry_date.pack()

ttk.Label(root, text="Day (Auto-filled)").pack(pady=5)
days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
combo_day = ttk.Combobox(root, values=days, state="readonly")
combo_day.pack()

ttk.Label(root, text="Start Time").pack(pady=5)
entry_start_time = ttk.Combobox(root, values=[], state="readonly", width=30)
entry_start_time.pack()

ttk.Label(root, text="End Time").pack(pady=5)
entry_end_time = ttk.Combobox(root, values=[], state="readonly", width=30)
entry_end_time.pack()

button_add_slot = ttk.Button(root, text="Add Slot")
button_add_slot.pack(pady=5)

button_remove_slot = ttk.Button(root, text="Remove Selected Slot")
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

button_book = ttk.Button(root, text="Book Slots Now")
button_book.pack(pady=10)

button_schedule = ttk.Button(root, text="Schedule Booking")
button_schedule.pack(pady=10)

button_stop = ttk.Button(root, text="Stop Process")
button_stop.pack(pady=10)