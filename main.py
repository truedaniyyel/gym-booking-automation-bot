import os
import time
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as ec
from selenium.common.exceptions import NoSuchElementException, TimeoutException, StaleElementReferenceException

load_dotenv()

ACCOUNT_EMAIL = os.getenv("ACCOUNT_EMAIL")
ACCOUNT_PASSWORD = os.getenv("ACCOUNT_PASSWORD")
GYM_URL = os.getenv("GYM_URL")
BROWSER_TYPE = os.getenv("BROWSER", "chrome").lower()

# --- Driver Setup Function ---

def setup_driver():
    print(f"Initializing {BROWSER_TYPE}...")

    if BROWSER_TYPE == "firefox":
        options = webdriver.FirefoxOptions()

        # Firefox doesn't need 'detach' in the same way Chrome does
        # Selenium Manager automatically handles geckodriver installation
        driver = webdriver.Firefox(options=options)

    else:
        options = webdriver.ChromeOptions()
        options.add_experimental_option("detach", True)

        # Chrome Profile
        user_data_dir = os.path.join(os.getcwd(), "chrome_profile")
        options.add_argument(f"--user-data-dir={user_data_dir}")

        driver = webdriver.Chrome(options=options)

    driver.get(GYM_URL)
    return driver

try:
    driver = setup_driver()
    wait = WebDriverWait(driver, 3)
except Exception as e:
    print(f"Failed to initialize driver: {e}")
    exit(1)

# --- Helper Functions ---

def retry(func, retries=5, description=None):
    for i in range(retries):
        try:
            return func()
        except (TimeoutException, StaleElementReferenceException):
            if description:
                # Optional: print(f"Retrying {description}...")
                pass
            if i == retries - 1:
                raise
            time.sleep(0.5)
    return None


def login():
    try:
        driver.find_element(By.ID, "schedule-page")
        print("✓ Already logged in.")
        return
    except NoSuchElementException:
        pass

    print("Logging in...")
    wait.until(ec.element_to_be_clickable((By.ID, "login-button"))).click()

    email_input = wait.until(ec.presence_of_element_located((By.ID, "email-input")))
    email_input.clear()
    email_input.send_keys(ACCOUNT_EMAIL)

    password_input = driver.find_element(By.ID, "password-input")
    password_input.clear()
    password_input.send_keys(ACCOUNT_PASSWORD)

    driver.find_element(By.ID, "submit-button").click()
    wait.until(ec.presence_of_element_located((By.ID, "schedule-page")))
    print("✓ Login successful.")


def ensure_on_schedule_page():
    """Navigates back to schedule page if we aren't there"""
    try:
        driver.find_element(By.ID, "schedule-page")
    except NoSuchElementException:
        print("\nReturning to Schedule Page...")
        try:
            driver.find_element(By.ID, "schedule-link").click()
        except NoSuchElementException:
            try:
                driver.find_element(By.LINK_TEXT, "Class Schedule").click()
            except NoSuchElementException:
                driver.get(GYM_URL)

        wait.until(ec.presence_of_element_located((By.ID, "schedule-page")))


def get_available_days():
    day_groups = driver.find_elements(By.CSS_SELECTOR, "div[id^='day-group-']")
    days_map = {}
    print("\n----------------------------")
    print("      AVAILABLE DAYS      ")
    print("----------------------------")
    for index, group in enumerate(day_groups, 1):
        try:
            day_title = group.find_element(By.TAG_NAME, "h2").text
            days_map[index] = {"title": day_title, "element": group}
            print(f"{index} - {day_title}")
        except StaleElementReferenceException:
            continue
    return days_map


def get_classes_for_day(day_element):
    cards = day_element.find_elements(By.CSS_SELECTOR, "div[id^='class-card-']")
    classes_map = {}
    print(f"\n--- CLASSES ---")
    for index, card in enumerate(cards, 1):
        class_name = card.find_element(By.CSS_SELECTOR, "h3[id^='class-name-']").text
        time_text = card.find_element(By.CSS_SELECTOR, "p[id^='class-time-']").text
        button = card.find_element(By.CSS_SELECTOR, "button[id^='book-button-']")
        status = button.text

        classes_map[index] = {
            "name": class_name,
            "time": time_text,
            "status": status,
            "button": button
        }
        print(f"{index} - {class_name} ({time_text}) -> [{status}]")
    return classes_map


def check_my_bookings(target_class_name):
    print("\n--- VERIFYING BOOKING ---")
    driver.find_element(By.ID, "my-bookings-link").click()
    wait.until(ec.presence_of_element_located((By.ID, "my-bookings-page")))

    my_cards = driver.find_elements(By.CSS_SELECTOR, "div[id*='card-']")
    found = False
    for card in my_cards:
        booked_name = card.find_element(By.TAG_NAME, "h3").text
        if target_class_name in booked_name:
            print(f"✓ Verified: {booked_name} is in your list.")
            found = True
            break
    if not found:
        print("❌ Warning: Class not found in 'My Bookings'.")


# --- MAIN LOOP ---

# Login
retry(login, description="Login")

while True:
    # Reset location to Schedule Page
    ensure_on_schedule_page()

    # Show Days
    days = get_available_days()

    user_input = input("\nSelect a day # (or 'q' to quit): ").lower()
    if user_input == 'q':
        print("Goodbye!")
        break

    # Validate Day Input
    selected_day = None
    try:
        day_idx = int(user_input)
        if day_idx in days:
            selected_day = days[day_idx]
        else:
            print("⚠ Invalid day number.")
            continue  # Restart loop
    except ValueError:
        print("⚠ Please enter a number or 'q'.")
        continue

    # Show Classes for that Day
    print(f"\nViewing: {selected_day['title']}")
    classes = get_classes_for_day(selected_day['element'])

    if not classes:
        print("No classes found.")
        continue

    # Select Class
    class_input = input("\nSelect class # to book/waitlist (or 'b' to go back): ").lower()
    if class_input == 'b':
        continue

    target_class = None
    try:
        class_idx = int(class_input)
        if class_idx in classes:
            target_class = classes[class_idx]
        else:
            print("⚠ Invalid class number.")
            continue
    except ValueError:
        print("⚠ Invalid input.")
        continue

    # Start Booking
    btn = target_class['button']
    status = target_class['status']

    if status in ["Booked", "Waitlisted", "Full"]:
        print(f"⚠ Cannot action this class. Status is: {status}")
        time.sleep(1.5)
    else:
        print(f"Attempting to: {status}...")
        btn.click()

        # Wait for button status to change
        try:
            wait.until(lambda d: btn.text in ["Booked", "Waitlisted"])
            print(f"✅ Success! Status changed to: {btn.text}")

            # Verify (only if action was taken)
            retry(lambda: check_my_bookings(target_class['name']), description="Verification")

            input("\nPress Enter to continue booking...")

        except TimeoutException:
            print("❌ Timeout: Status didn't update.")

driver.quit()