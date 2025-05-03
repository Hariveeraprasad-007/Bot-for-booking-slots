from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import StaleElementReferenceException
import time

def slot_booking(username_input, password_input, day, date, start_time, end_time, scheduler_url):
    driver = webdriver.Firefox()
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
                        print("Slot booked successfully ✅")
                        return
                    except Exception as e:
                        print(f"❌ Error during booking: {e}")
                else:
                    print("⚠️ Start and end time do not match.")
            else:
                print("⚠️ Day or date does not match.")
        except StaleElementReferenceException:
            print("♻️ DOM updated — retrying row fetch...")
            continue
    print("❌ No matching slot found.")
    driver.quit()
def main():
    username=input("Please enter you user name: ")
    password=input("Please enter your Password: ")
    day=input("please enter the day:(make sure the first letter need to be captail): ")
    date=input("please enter the date eg=6 May 2025.,: ")
    start_time=input("Please enter the start time of the slot eg:10:00 PM: ")
    end_time=input("Please enter the end time of the slot eg:12:00 PM: ")
    while True:
        print("1-1731 Booking")
        print("2-1851 Booking")
        print("3-1852 Booking")
        print("4-1611 Booking")
        print("5-Exit")
        num=int(input("Please enter the choice: "))
        if num==1:
            slot_booking(username,password,day,date,start_time,end_time,scheduler_url="https://lms2.ai.saveetha.in/mod/scheduler/view.php?id=36638")
        elif num==2:
            slot_booking(username,password,day,date,start_time,end_time,scheduler_url="https://lms2.ai.saveetha.in/mod/scheduler/view.php?id=36298")
        elif num==3:
            slot_booking(username,password,day,date,start_time,end_time,scheduler_url="https://lms2.ai.saveetha.in/mod/scheduler/view.php?id=37641")
        elif num==4:
            slot_booking(username,password,day,date,start_time,end_time,scheduler_url="https://lms2.ai.saveetha.in/mod/scheduler/view.php?id=36137")
        elif num==5:
            print("exiting")
            break
        else:
            print("Enter correct choice(1-5)")
main()
