import time
from datetime import datetime, timedelta

def _generate_interval_start_times(overall_start_dt, overall_end_dt, interval_m, break_start_dt, break_end_dt):
    """
    Generates a list of start times at fixed intervals, skipping any time within a break.
    This is for venues like 1611 where all granular 15-min slots are available.
    """
    times = []
    current_time = overall_start_dt
    
    while current_time < overall_end_dt: 
        is_during_break = False
        if break_start_dt and break_end_dt:
            if break_start_dt <= current_time < break_end_dt:
                is_during_break = True

        if not is_during_break:
            formatted_time = current_time.strftime("%I:%M %p").lstrip('0').replace(' 0', ' ').replace(':00 ', ':00').replace('AM',' AM').replace('PM',' PM')
            times.append(formatted_time)
        
        current_time += timedelta(minutes=interval_m)

        if break_start_dt and break_end_dt and break_start_dt <= current_time < break_end_dt:
            current_time = break_end_dt
            
    return times