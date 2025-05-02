
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
def slot_booking_1731(username_input,password_input,day,date,start_time,end_time):
    driver=webdriver.Firefox()
    driver.get("https://lms2.ai.saveetha.in/course/view.php?id=302")
    username=driver.find_element(By.NAME,'username')
    password=driver.find_element(By.NAME,'password')
    username.send_keys(username_input)
    password.send_keys(password_input)
    logbtn=driver.find_element(By.ID,'loginbtn').click()
    driver.find_element(By.XPATH, "//a[@href='https://lms2.ai.saveetha.in/mod/scheduler/view.php?id=36638']").click()
    WebDriverWait(driver,10).until(EC.presence_of_element_located((By.ID,'slotbookertable')))
    rows=driver.find_elements(By.XPATH, "//table//tr")
    expected_day_date = f"{day}, {date}".strip()
    current_date = ""
    for row in rows:
        row_text = row.text.strip()
        if any(month in row_text for month in [
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December"
        ]):
            current_date = row_text.split("\n")[0].strip() 
        if expected_day_date in current_date:
            if start_time in row_text and end_time in row_text:

                book_button = row.find_element(By.XPATH, ".//button[contains(text(), 'Book slot')]")
                driver.execute_script("arguments[0].scrollIntoView(true);", book_button)
                time.sleep(1)  # small pause to ensure visibility
                driver.execute_script("arguments[0].click();", book_button)
                note_field = WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.ID, "id_studentnote_editoreditable"))
                    )
                note_field.send_keys('reep')
                driver.find_element(By.ID,"id_submitbutton").click()
            else:
                print("start time and end time is incorrect")
        else:
            print("day is incorrect")
username=input("enter user name: ")
password=input("enter password: ")
day=input("Enter day: ")
date=input("Enter data: ")
start_time=input("Enter start time: ")
end_time=input("Enter end time: ")
slot_booking_1731(username,password,day,date,start_time,end_time)
