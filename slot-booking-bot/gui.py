from tkinter import ttk, messagebox
from components import root, combo_schedule, entry_start_time, listbox_slots, button_add_slot, button_remove_slot, button_book, button_schedule, button_stop
from schedulebooking import on_date_selected, on_schedule_selected, on_start_time_selected
from runbooking import run_booking
from schedulebooking import schedule_booking
from addslot import add_slot
from remove import remove_slot
from stop import stop_process

def setup_gui():
    button_add_slot.configure(command=add_slot)
    button_remove_slot.configure(command=remove_slot)
    button_book.configure(command=lambda: run_booking(continuous=True))
    button_schedule.configure(command=schedule_booking)
    button_stop.configure(command=stop_process)

    combo_schedule.bind("<<ComboboxSelected>>", on_schedule_selected)
    entry_start_time.bind("<<ComboboxSelected>>", on_start_time_selected)
    listbox_slots.bind("<Double-1>", lambda event: remove_slot())

    root.mainloop()