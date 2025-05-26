import streamlit as st
import time
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import re
from datetime import datetime
import uuid

# Streamlit configuration
st.set_page_config(page_title="Moodle Quiz Automator", layout="centered")
st.markdown("""
    <style>
    .main { background-color: #f5f5f5; padding: 20px; border-radius: 10px; }
    .stButton>button { background-color: #4CAF50; color: white; border-radius: 5px; }
    .stTextInput>div>input, .stTextArea>div>textarea { border-radius: 5px; }
    .error { color: #d32f2f; font-weight: bold; }
    .success { color: #388e3c; font-weight: bold; }
    .progress { color: #0288d1; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

# Interface
st.title("📚 Moodle Quiz Automator")
st.write("Automate your Moodle quizzes and view your marks instantly!")

# Load Gemini API key from secrets
gemini_api_key = st.secrets.get("GEMINI_API_KEY", None)

with st.form("quiz_form"):
    st.subheader("Enter Quiz Details")
    col1, col2 = st.columns(2)
    with col1:
        login_url = st.text_input("Moodle Login URL", value="https://lms2.ai.saveetha.in/login/index.php")
        username = st.text_input("Username", value="23009466")
        password = st.text_input("Password", type="password")
    with col2:
        quiz_urls = st.text_area("Quiz URLs (comma-separated)", value="https://lms2.ai.saveetha.in/mod/quiz/view.php?id=1790")
        if not gemini_api_key:
            gemini_api_key = st.text_input("Gemini API Key", type="password")
    
    submit_button = st.form_submit_button("Start Automation 🚀")

# Instructions
with st.expander("ℹ How to Get a Gemini API Key"):
    st.markdown("""
    1. Visit [Google AI Studio](https://aistudio.google.com/app/apikey) and sign in.
    2. Click *Create API Key* and copy the key.
    3. For higher usage, enable billing in [Google Cloud Console](https://console.cloud.google.com/) and enable the *Generative Language API*.
    4. Paste the key above or add it to `.streamlit/secrets.toml`. The free tier allows ~1,500 requests/day.
    """)

# Gemini function with enhanced error handling
def ask_gemini(question, options, gemini_api_key):
    start_time = time.time()
    option_letters = ['a', 'b', 'c', 'd']
    formatted_options = "\n".join([f"{letter}. {opt}" for letter, opt in zip(option_letters, options[:len(option_letters)])])
    prompt = (
        f"Question: {question}\n\nOptions:\n{formatted_options}\n\nAnswer with ONLY the letter of the correct option ({', '.join(option_letters[:len(options)])}):"
    )
    headers = {"Content-Type": "application/json"}
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    try:
        response = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={gemini_api_key}",
            json=payload,
            headers=headers,
            timeout=15
        )
        response.raise_for_status()
        generated_text = response.json().get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip().lower()
        match = re.match(r"^\s*([a-d])", generated_text)
        return match.group(1) if match and match.group(1) in option_letters[:len(options)] else "", time.time() - start_time
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 429:
            return "", time.time() - start_time, "Rate limit exceeded for Gemini API"
        return "", time.time() - start_time, f"Gemini API error: {e}"
    except Exception as e:
        return "", time.time() - start_time, f"Gemini API request failed: {e}"

# Check for HTTP errors
def check_http_error(driver):
    try:
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        return bool(soup.find(string=re.compile(r'(503|429|500)\s*(Service Unavailable|Too Many Requests|Internal Server Error)', re.I)))
    except:
        return False

# Main logic
if submit_button:
    if not all([login_url, quiz_urls, username, password, gemini_api_key]):
        st.markdown('<p class="error">Please fill in all fields.</p>', unsafe_allow_html=True)
    else:
        quiz_url_list = [url.strip() for url in quiz_urls.split(",") if url.strip()]
        if not quiz_url_list:
            st.markdown('<p class="error">No valid quiz URLs provided.</p>', unsafe_allow_html=True)
        else:
            quiz_results = []
            progress_bar = st.progress(0)
            status_text = st.empty()
            progress_log = st.empty()

            # Initialize progress log
            progress_messages = []

            def update_progress(message, quiz_index=None, total_quizzes=None, duration=None):
                if quiz_index is not None and total_quizzes is not None:
                    prefix = f"[Quiz {quiz_index}/{total_quizzes}] "
                else:
                    prefix = ""
                if duration is not None:
                    message = f"{message} ({duration:.2f}s)"
                progress_messages.append(f"{prefix}{message}")
                # Limit to last 5 messages
                progress_log.markdown('<p class="progress">' + "<br>".join(progress_messages[-5:]) + '</p>', unsafe_allow_html=True)

            # Selenium setup
            driver = None
            try:
                chrome_options = webdriver.ChromeOptions()
                chrome_options.add_argument("--headless")
                chrome_options.add_argument("--no-sandbox")
                chrome_options.add_argument("--disable-dev-shm-usage")
                chrome_options.add_argument("--disable-gpu")
                driver = webdriver.Chrome(
                    service=ChromeService(ChromeDriverManager().install()),
                    options=chrome_options
                )
                wait = WebDriverWait(driver, 20)  # Increased timeout
                update_progress("WebDriver initialized successfully")
            except Exception as e:
                st.markdown(f'<p class="error">Failed to initialize WebDriver: {e}</p>', unsafe_allow_html=True)
                st.stop()

            try:
                # Login
                start_time = time.time()
                update_progress("Logging in...")
                driver.get(login_url)
                max_retries = 3
                for attempt in range(max_retries):
                    if check_http_error(driver):
                        update_progress(f"HTTP error detected during login, retrying (attempt {attempt + 1}/{max_retries})")
                        time.sleep(2 ** attempt)  # Exponential backoff
                        driver.refresh()
                        continue
                    break
                else:
                    st.markdown('<p class="error">Failed to bypass HTTP error during login</p>', unsafe_allow_html=True)
                    st.stop()
                wait.until(EC.visibility_of_element_located((By.ID, 'username'))).send_keys(username)
                wait.until(EC.visibility_of_element_located((By.ID, 'password'))).send_keys(password)
                wait.until(EC.element_to_be_clickable((By.ID, 'loginbtn'))).click()
                time.sleep(2)
                update_progress("Login successful", duration=time.time() - start_time)

                # Process quizzes
                for quiz_index, quiz_url in enumerate(quiz_url_list, 1):
                    status_text.text(f"Processing Quiz {quiz_index}/{len(quiz_url_list)}: {quiz_url}")
                    progress_bar.progress(quiz_index / len(quiz_url_list))
                    result = {"url": quiz_url, "status": "Failed", "marks": "N/A", "error": None}

                    try:
                        start_time = time.time()
                        update_progress(f"Navigating to quiz", quiz_index, len(quiz_url_list))
                        driver.get(quiz_url)
                        for attempt in range(max_retries):
                            if check_http_error(driver):
                                update_progress(f"HTTP error detected for quiz page, retrying (attempt {attempt + 1}/{max_retries})", quiz_index, len(quiz_url_list))
                                time.sleep(2 ** attempt)
                                driver.refresh()
                                continue
                            break
                        else:
                            result["error"] = "Failed to bypass HTTP error for quiz page"
                            quiz_results.append(result)
                            continue
                        wait.until(EC.presence_of_element_located((By.CLASS_NAME, "page-header-headings")))
                        update_progress("Quiz page loaded", quiz_index, len(quiz_url_list), duration=time.time() - start_time)
                    except Exception as e:
                        result["error"] = f"Failed to navigate to quiz: {e}"
                        quiz_results.append(result)
                        continue

                    # Start quiz
                    try:
                        start_time = time.time()
                        update_progress(f"Attempting to start quiz", quiz_index, len(quiz_url_list))
                        quiz_button_xpath = "//button[contains(text(),'Attempt quiz') or contains(text(),'Re-attempt quiz') or contains(text(),'Continue your attempt')] | //input[contains(@value,'Attempt quiz') or contains(@value,'Re-attempt quiz') or contains(@value,'Continue your attempt')]"
                        quiz_button = wait.until(EC.element_to_be_clickable((By.XPATH, quiz_button_xpath)))
                        driver.execute_script("arguments[0].click();", quiz_button)
                        time.sleep(2)
                        wait.until(EC.presence_of_element_located((By.CLASS_NAME, "qtext")))
                        update_progress("Quiz started", quiz_index, len(quiz_url_list), duration=time.time() - start_time)
                    except:
                        try:
                            start_attempt_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(),'Start attempt')] | //input[contains(@value,'Start attempt')]")))
                            driver.execute_script("arguments[0].click();", start_attempt_button)
                            time.sleep(2)
                            wait.until(EC.presence_of_element_located((By.CLASS_NAME, "qtext")))
                            update_progress("Quiz started after confirmation", quiz_index, len(quiz_url_list), duration=time.time() - start_time)
                        except Exception as e:
                            result["error"] = f"Could not start quiz: {e}"
                            page_source = driver.page_source
                            st.download_button(
                                label=f"Download Quiz {quiz_index} Start Page Source",
                                data=page_source,
                                file_name=f"quiz_start_page_source_{quiz_index}.html",
                                mime="text/html"
                            )
                            quiz_results.append(result)
                            continue

                    # Process questions
                    page_count = 0
                    finish_attempt_xpath = "//input[@value='Finish attempt ...' and @name='next' and @id='mod_quiz-next-nav']"
                    while True:
                        page_count += 1
                        start_time = time.time()
                        update_progress(f"Processing question page {page_count}", quiz_index, len(quiz_url_list))
                        for attempt in range(max_retries):
                            if check_http_error(driver):
                                update_progress(f"HTTP error detected on question page {page_count}, retrying (attempt {attempt + 1}/{max_retries})", quiz_index, len(quiz_url_list))
                                time.sleep(2 ** attempt)
                                driver.refresh()
                                continue
                            break
                        else:
                            update_progress(f"Failed to bypass HTTP error on question page {page_count}", quiz_index, len(quiz_url_list))
                            st.markdown(f'<p class="error">Failed to bypass HTTP error for question {page_count} in quiz {quiz_index}</p>', unsafe_allow_html=True)
                            break

                        try:
                            question_element = wait.until(EC.visibility_of_element_located((By.CLASS_NAME, "qtext")))
                            question_text = question_element.text.strip()
                            update_progress(f"Found question: {question_text[:50]}...", quiz_index, len(quiz_url_list), duration=time.time() - start_time)
                            start_time = time.time()
                            answer_block = wait.until(EC.visibility_of_element_located((By.CLASS_NAME, "answer")))
                            soup = BeautifulSoup(answer_block.get_attribute('outerHTML'), 'html.parser')
                            option_texts, radio_elements = [], []
                            for inp in soup.find_all('input', {'type': 'radio'}):
                                option_id = inp.get('id')
                                if option_id:
                                    label_text = ""
                                    if label_id := inp.get('aria-labelledby'):
                                        if label_div := soup.find(id=label_id):
                                            label_text = label_div.get_text(strip=True)
                                    elif soup.find('label', {'for': option_id}):
                                        label_text = soup.find('label', {'for': option_id}).get_text(strip=True)
                                    elif inp.find_next_sibling('label'):
                                        label_text = " ".join(inp.find_next_sibling('label').get_text(strip=True).split())
                                    if label_text:
                                        option_texts.append(label_text)
                                        try:
                                            radio_elements.append(driver.find_element(By.ID, option_id))
                                        except:
                                            option_texts.pop()
                                            continue
                            update_progress(f"Parsed options", quiz_index, len(quiz_url_list), duration=time.time() - start_time)
                            if option_texts and len(option_texts) == len(radio_elements):
                                update_progress(f"Found {len(option_texts)} options: {', '.join(option_texts[:2])}...", quiz_index, len(quiz_url_list))
                                start_time = time.time()
                                model_answer_letter, gemini_duration, gemini_error = ask_gemini(question_text, option_texts, gemini_api_key)
                                if gemini_error:
                                    update_progress(f"Gemini error: {gemini_error}", quiz_index, len(quiz_url_list))
                                    st.markdown(f'<p class="error">Gemini error for question {page_count} in quiz {quiz_index}: {gemini_error}</p>', unsafe_allow_html=True)
                                update_progress(f"Gemini responded", quiz_index, len(quiz_url_list), duration=gemini_duration)
                                if model_answer_letter in 'abcd'[:len(option_texts)]:
                                    answer_index = ord(model_answer_letter) - ord('a')
                                    if 0 <= answer_index < len(radio_elements):
                                        start_time = time.time()
                                        wait.until(EC.element_to_be_clickable(radio_elements[answer_index]))
                                        driver.execute_script("arguments[0].click();", radio_elements[answer_index])
                                        update_progress(f"Selected option {model_answer_letter}: {option_texts[answer_index][:50]}...", quiz_index, len(quiz_url_list), duration=time.time() - start_time)
                                    else:
                                        update_progress(f"Invalid Gemini response: {model_answer_letter} out of bounds", quiz_index, len(quiz_url_list))
                                        st.markdown(f'<p class="error">Failed to select option for question {page_count} in quiz {quiz_index}: Invalid Gemini response</p>', unsafe_allow_html=True)
                                else:
                                    update_progress(f"Gemini returned invalid/no response: {model_answer_letter}", quiz_index, len(quiz_url_list))
                                    st.markdown(f'<p class="error">Failed to select option for question {page_count} in quiz {quiz_index}: Invalid Gemini response</p>', unsafe_allow_html=True)
                            else:
                                update_progress("No valid options found for question", quiz_index, len(quiz_url_list))
                                st.markdown(f'<p class="error">No valid options found for question {page_count} in quiz {quiz_index}</p>', unsafe_allow_html=True)
                        except Exception as e:
                            update_progress(f"No question found on page {page_count}: {e}", quiz_index, len(quiz_url_list), duration=time.time() - start_time)

                        try:
                            start_time = time.time()
                            finish_btn = wait.until(EC.element_to_be_clickable((By.XPATH, finish_attempt_xpath)))
                            update_progress("Found 'Finish attempt ...' button", quiz_index, len(quiz_url_list))
                            driver.execute_script("arguments[0].click();", finish_btn)
                            time.sleep(2)
                            update_progress("Clicked 'Finish attempt ...'", quiz_index, len(quiz_url_list), duration=time.time() - start_time)
                            start_time = time.time()
                            submit_all_btn1 = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[@type='submit' and contains(text(), 'Submit all and finish')]")))
                            driver.execute_script("arguments[0].click();", submit_all_btn1)
                            time.sleep(2)
                            update_progress("Clicked first 'Submit all and finish'", quiz_index, len(quiz_url_list), duration=time.time() - start_time)
                            start_time = time.time()
                            submit_all_btn2 = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[@type='button' and @data-action='save' and contains(text(), 'Submit all and finish')]")))
                            driver.execute_script("arguments[0].click();", submit_all_btn2)
                            time.sleep(2)
                            update_progress("Clicked second 'Submit all and finish'", quiz_index, len(quiz_url_list), duration=time.time() - start_time)
                            start_time = time.time()
                            finish_review_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//a[@class='mod_quiz-next-nav' and contains(text(), 'Finish review')]")))
                            driver.execute_script("arguments[0].click();", finish_review_btn)
                            time.sleep(2)
                            update_progress("Clicked 'Finish review'", quiz_index, len(quiz_url_list), duration=time.time() - start_time)

                            # Extract marks
                            try:
                                start_time = time.time()
                                update_progress("Extracting marks...", quiz_index, len(quiz_url_list))
                                for attempt in range(max_retries):
                                    if check_http_error(driver):
                                        update_progress(f"HTTP error detected during marks extraction, retrying (attempt {attempt + 1}/{max_retries})", quiz_index, len(quiz_url_list))
                                        time.sleep(2 ** attempt)
                                        driver.refresh()
                                        continue
                                    break
                                else:
                                    result["error"] = "Failed to bypass HTTP error during marks extraction"
                                    quiz_results.append(result)
                                    break
                                table = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "table.quizattemptsummary")))
                                soup = BeautifulSoup(table.get_attribute('outerHTML'), 'html.parser')
                                rows = soup.find_all('tr', class_='lastrow')
                                current_time = datetime.now()
                                latest_marks = "N/A"
                                latest_timestamp = None
                                for row in rows:
                                    try:
                                        timestamp_cell = row.find('td', class_='c1')
                                        marks_cell = row.find('td', class_='c2')
                                        if timestamp_cell and marks_cell:
                                            timestamp_text = timestamp_cell.find('span', class_='statedetails').get_text(strip=True)
                                            marks = marks_cell.get_text(strip=True)
                                            timestamp_match = re.search(r"Submitted\s+\w+,\s+(\d+\s+\w+\s+\d{4},\s+\d+:\d+\s+[AP]M)", timestamp_text)
                                            if timestamp_match:
                                                timestamp = datetime.strptime(timestamp_match.group(1), "%d %B %Y, %I:%M %p")
                                                time_diff = (current_time - timestamp).total_seconds() / 60
                                                if time_diff < 10 and (latest_timestamp is None or timestamp > latest_timestamp):
                                                    latest_marks = marks
                                                    latest_timestamp = timestamp
                                    except:
                                        continue
                                update_progress(f"Marks extracted: {latest_marks}", quiz_index, len(quiz_url_list), duration=time.time() - start_time)
                                result["status"] = "Completed"
                                result["marks"] = latest_marks
                                quiz_results.append(result)
                                break
                            except Exception as e:
                                result["error"] = f"Failed to extract marks: {e}"
                                page_source = driver.page_source
                                st.download_button(
                                    label=f"Download Quiz {quiz_index} Marks Page Source",
                                    data=page_source,
                                    file_name=f"marks_page_source_{quiz_index}.html",
                                    mime="text/html"
                                )
                                quiz_results.append(result)
                                break
                        except:
                            start_time = time.time()
                            update_progress("No 'Finish attempt ...' button found, checking for next page", quiz_index, len(quiz_url_list))
                            try:
                                next_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//input[@value='Next page']")))
                                driver.execute_script("arguments[0].click();", next_btn)
                                for attempt in range(max_retries):
                                    if check_http_error(driver):
                                        update_progress(f"HTTP error detected after next page click, retrying (attempt {attempt + 1}/{max_retries})", quiz_index, len(quiz_url_list))
                                        time.sleep(2 ** attempt)
                                        driver.refresh()
                                        continue
                                    break
                                else:
                                    update_progress(f"Failed to bypass HTTP error after next page click", quiz_index, len(quiz_url_list))
                                    st.markdown(f'<p class="error">Failed to bypass HTTP error for question {page_count} in quiz {quiz_index}</p>', unsafe_allow_html=True)
                                    break
                                wait.until(EC.presence_of_element_located((By.CLASS_NAME, "qtext")))
                                update_progress("Clicked 'Next page'", quiz_index, len(quiz_url_list), duration=time.time() - start_time)
                            except Exception as e:
                                result["error"] = f"Failed to navigate to next page: {e}"
                                page_source = driver.page_source
                                st.download_button(
                                    label=f"Download Quiz {quiz_index} Page {page_count} Source",
                                    data=page_source,
                                    file_name=f"question_page_{quiz_index}_{page_count}_source.html",
                                    mime="text/html"
                                )
                                quiz_results.append(result)
                                break

                # Display results
                status_text.text("All quizzes processed!")
                progress_bar.empty()
                st.markdown('<p class="success">Processing complete!</p>', unsafe_allow_html=True)
                with st.expander("📊 Quiz Results", expanded=True):
                    for result in quiz_results:
                        st.markdown(f"*Quiz URL*: {result['url']}")
                        st.markdown(f"- *Status*: <span class='{'success' if result['status'] == 'Completed' else 'error'}'>{result['status']}</span>", unsafe_allow_html=True)
                        st.markdown(f"- *Marks*: {result['marks']}")
                        if result['error']:
                            st.markdown(f"- *Error*: <span class='error'>{result['error']}</span>", unsafe_allow_html=True)
                        st.markdown("---")

            finally:
                if driver:
                    driver.quit()
                    update_progress("WebDriver closed")
