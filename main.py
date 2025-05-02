
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
driver=webdriver.Firefox()
driver.get("https://lms2.ai.saveetha.in/course/view.php?id=302")
username=driver.find_element(By.NAME,'username')
password=driver.find_element(By.NAME,'password')
username.send_keys('23003977')
password.send_keys('e35734')
logbtn=driver.find_element(By.ID,'loginbtn').click()
driver.find_element(By.XPATH, "//a[@href='https://lms2.ai.saveetha.in/mod/scheduler/view.php?id=36298']").click()
WebDriverWait(driver,10).until(EC.presence_of_element_located((By.ID,'slotbookertable')))
rows=driver.find_elements(By.XPATH, "//table//tr")
target='10:00'
for row in rows:
    if target in row.text:
        row.find_element(By.XPATH, ".//button[contains(text(), 'Book slot')]").click()
        driver.find_element(By.ID,"id_studentnote_editoreditable").send_keys('reep')
        driver.find_element(By.ID,"id_submitbutton").click()
