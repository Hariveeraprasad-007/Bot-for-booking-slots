
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
driver.find_element(By.XPATH, "//a[@href='https://lms2.ai.saveetha.in/mod/scheduler/view.php?id=36638']").click()
