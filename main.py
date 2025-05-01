
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
driver=webdriver.Firefox()
driver.get("https://lms2.ai.saveetha.in/mod/scheduler/view.php?id=36298")
username=driver.find_element(By.NAME,'username')
password=driver.find_element(By.NAME,'password')
username.send_keys('23003977')
password.send_keys('e35734')
logbtn=driver.find_element(By.ID,'loginbtn').click()