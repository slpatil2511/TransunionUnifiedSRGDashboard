# noc_pager.py

import re
import traceback

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
from selenium.webdriver.edge.options import Options

# ==========================================================
# GLOBAL DRIVER
# ==========================================================

selenium_driver = None


# ==========================================================
# DRIVER MANAGEMENT
# ==========================================================

def switch_to_smartit_tab(driver):

    for handle in driver.window_handles:

        driver.switch_to.window(handle)

        if "transunion-smartit.onbmc.com" in driver.current_url:
            return True

    return False

def get_driver():
    global selenium_driver

    try:
        if selenium_driver is not None:

            # Validate existing session
            _ = selenium_driver.title

            return selenium_driver

    except Exception:

        #print("Existing browser session is invalid.")

        try:
            selenium_driver.quit()
        except:
            pass

        selenium_driver = None

    #print("Attaching to SmartIT browser...")

    options = webdriver.EdgeOptions()

    options.add_experimental_option(
        "debuggerAddress",
        "127.0.0.1:9222"
    )

    selenium_driver = webdriver.Edge(
        options=options
    )

    return selenium_driver


def reset_browser():

    global selenium_driver

    try:
        if selenium_driver:
            selenium_driver.quit()
    except:
        pass

    selenium_driver = None


def close_browser():
    reset_browser()


# ==========================================================
# MAIN AUTOMATION
# ==========================================================

def automate_remedy_paging(
    group_name,
    notification_text,
    dynamic_url,
    auto_submit=True
):

    global selenium_driver

    try:

        # -----------------------------------------
        # CLEAN MARKDOWN
        # -----------------------------------------

        notification_text = re.sub(
            r'^#+\s*',
            '',
            notification_text,
            flags=re.MULTILINE
        )

        notification_text = re.sub(
            r'\*+',
            '',
            notification_text
        ).strip()

        # -----------------------------------------
        # GET DRIVER
        # -----------------------------------------

        start = time.time()
        driver = get_driver()

        #print("\n================================================")
        #print("AUTOMATION STARTED")
        #print("================================================")
        #print("Driver ID:", id(driver))
        #print("Target URL:", dynamic_url)

        wait = WebDriverWait(driver, 180)

        # -----------------------------------------
        # OPEN TICKET
        # -----------------------------------------
        
        driver = get_driver()

        switch_to_smartit_tab(driver)

        driver.get(dynamic_url)
        #print(
            #"Driver ready:",
            #round(time.time() - start, 1),
            #"sec"
        #)

        #print("Waiting for Remedy page...")

        # -----------------------------------------
        # SWITCH TO PWA FRAME
        # -----------------------------------------

        wait.until(
            EC.frame_to_be_available_and_switch_to_it(
                (By.ID, "pwa-frame")
            )
        )

        #print("Inside pwa-frame")
        #print(
            #"Frame ready:",
            #round(time.time() - start, 1),
            #"sec"
        #)

        # -----------------------------------------
        # OPEN ESCALATE PANEL
        # -----------------------------------------

        #print("Opening Escalate panel...")

        escalate_btn = wait.until(
            EC.presence_of_element_located(
                (
                    By.CSS_SELECTOR,
                    '[aria-label="Escalate"]'
                )
            )
        )

        driver.execute_script(
            "arguments[0].click();",
            escalate_btn
        )

        #print("Escalate panel opened")

        # -----------------------------------------
        # NOTIFICATION TYPE
        # -----------------------------------------

        notification_type = wait.until(
            EC.presence_of_element_located(
                (
                    By.XPATH,
                    "//*[contains(text(),'Notification Type')]"
                )
            )
        )

        driver.execute_script(
            "arguments[0].click();",
            notification_type
        )

        # -----------------------------------------
        # SELECT GROUP
        # -----------------------------------------

        group_option = wait.until(
            EC.presence_of_element_located(
                (
                    By.XPATH,
                    "//span[text()='Group']"
                )
            )
        )

        driver.execute_script(
            "arguments[0].click();",
            group_option
        )

        #print("Notification Type = Group")

        # -----------------------------------------
        # GROUP NAME
        # -----------------------------------------

        group_field = wait.until(
            EC.presence_of_element_located(
                (
                    By.CSS_SELECTOR,
                    '[aria-label="Group Name"]'
                )
            )
        )

        group_field.clear()

        group_field.send_keys(group_name)

        #print(
            #f"Typed Group Name: {group_name}"
        #)

        group_match = wait.until(
            EC.presence_of_element_located(
                (
                    By.XPATH,
                    f"//*[@title='{group_name}']"
                )
            )
        )

        driver.execute_script(
            "arguments[0].click();",
            group_match
        )

        #print("Group selected")

        # -----------------------------------------
        # NOTIFICATION TEXT
        # -----------------------------------------

        text_field = wait.until(
            EC.presence_of_element_located(
                (
                    By.CSS_SELECTOR,
                    '[aria-label="Notification Text"]'
                )
            )
        )

        text_field.clear()

        text_field.send_keys(notification_text)

        #print("Notification Text entered")

        # -----------------------------------------
        # FINAL ESCALATE
        # -----------------------------------------

        if auto_submit:

            #print("Submitting escalation...")

            final_escalate = wait.until(
                EC.element_to_be_clickable(
                    (
                        By.ID,
                        "710001133"
                    )
                )
            )

            driver.execute_script(
                "arguments[0].click();",
                final_escalate
            )

            #print("ESCALATION SUBMITTED")
            #print(
                #"Total paging time:",
                #round(time.time() - start, 1),
                #"sec"
            #)

            return (
                True,
                f"Escalation submitted successfully to '{group_name}'."
            )

        else:

            #print("FORM FILLED")

            return (
                True,
                "Form filled successfully. Please review and manually click Escalate."
            )

    except Exception as e:

        error_text = str(e)

        if "no such window" in error_text.lower():
            error_text = (
                "Message: no such window: "
                "target window already closed by user."
            )

        elif "invalid session id" in error_text.lower():
            error_text = (
                "Message: browser session expired."
            )

        return (
            False,
            error_text
        )