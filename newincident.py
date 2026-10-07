# newincident.py

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
from selenium.webdriver.common.keys import Keys
import json
import os

CREATE_INCIDENT_URL = (
    "https://transunion-smartit.onbmc.com/smartit/app/#/create/incidentPV"
)

CUSTOMER = "Suryakant L Patil"
SUMMARY = "SRG_NOC_Support_Incident- For paging teams"
DESCRIPTION = "SRG_NOC_Support_Incident- For paging teams"
SUPPORT_GROUP = "SRG NOC Support"
PERSON = "Suryakant L Patil"


def switch_to_smartit_tab(driver):

    for handle in driver.window_handles:

        driver.switch_to.window(handle)

        if "transunion-smartit.onbmc.com" in driver.current_url:
            print(
                "SmartIT Tab Found:",
                driver.current_url
            )
            return True

    return False


def automate_incident_creation(test_mode=False):
    
    start = time.time()

    driver = None

    try:

        options = webdriver.EdgeOptions()

        options.add_experimental_option(
            "debuggerAddress",
            "127.0.0.1:9222"
        )

        driver = webdriver.Edge(
            options=options
        )

        wait = WebDriverWait(driver, 180)

        switch_to_smartit_tab(driver)

        driver.execute_script(
            f"window.location.href='{CREATE_INCIDENT_URL}'"
        )
        
        WebDriverWait(driver, 30).until(
            lambda d: "create/incidentPV" in d.current_url
        )

        time.sleep(3) 

        # =====================================================
        # SWITCH TO REMEDY FRAME
        # =====================================================

        wait.until(
            EC.frame_to_be_available_and_switch_to_it(
                (By.ID, "pwa-frame")
            )
        )


        # =====================================================
        # CUSTOMER
        # =====================================================

        customer = wait.until(
            EC.element_to_be_clickable(
                (
                    By.CSS_SELECTOR,
                    '[aria-label="Customer"]'
                )
            )
        )


        driver.execute_script(
            "arguments[0].scrollIntoView({block:'center'});",
            customer
        )

        time.sleep(1)

        driver.execute_script(
            "arguments[0].focus();",
            customer
        )

        time.sleep(1)

        customer.send_keys(CUSTOMER)

        WebDriverWait(driver, 15).until(
            lambda d: customer.get_attribute("aria-expanded") == "true"
        )

        customer.send_keys(Keys.ARROW_DOWN)

        customer.send_keys(Keys.ENTER)

        time.sleep(2)

        options = driver.find_elements(
            By.XPATH,
            "//*[contains(@title,'Suryakant')]"
        )

        if options:

            driver.execute_script(
                "arguments[0].click();",
                options[0]
            )

        # =====================================================
        # INCIDENT TYPE
        # =====================================================

        incident_type = wait.until(
            EC.element_to_be_clickable(
                (
                    By.CSS_SELECTOR,
                    '[aria-label="Incident type"]'
                )
            )
        )

        driver.execute_script(
            "arguments[0].click();",
            incident_type
        )

        usr_option = wait.until(
            EC.presence_of_element_located(
                (
                    By.XPATH,
                    "//span[text()='User Service Request']"
                )
            )
        )

        driver.execute_script(
            "arguments[0].click();",
            usr_option
        )

        # =====================================================
        # REPORTED SOURCE
        # =====================================================

        reported_source = wait.until(
            EC.element_to_be_clickable(
                (
                    By.CSS_SELECTOR,
                    '[aria-label="Reported Source"]'
                )
            )
        )

        driver.execute_script(
            "arguments[0].click();",
            reported_source
        )

        email_option = wait.until(
            EC.presence_of_element_located(
                (
                    By.XPATH,
                    "//span[text()='Email']"
                )
            )
        )

        driver.execute_script(
            "arguments[0].click();",
            email_option
        )

        # =====================================================
        # SUMMARY
        # =====================================================

        summary = wait.until(
            EC.element_to_be_clickable(
                (
                    By.CSS_SELECTOR,
                    '[aria-label="Summary"]'
                )
            )
        )

        summary.clear()
        summary.send_keys(SUMMARY)

        # =====================================================
        # DESCRIPTION
        # =====================================================

        description = wait.until(
            EC.presence_of_element_located(
                (
                    By.CSS_SELECTOR,
                    '[aria-label="Description"]'
                )
            )
        )

        description.clear()
        description.send_keys(DESCRIPTION)

        # =====================================================
        # OPERATIONAL CATEGORY
        # =====================================================

        operational_browse = wait.until(
            EC.presence_of_element_located(
                (
                    By.ID,
                    "304420061"
                )
            )
        )

        driver.execute_script(
            "arguments[0].click();",
            operational_browse
        )

        software_option = wait.until(
            EC.presence_of_element_located(
                (
                    By.XPATH,
                    "//span[text()='Software']"
                )
            )
        )

        driver.execute_script(
            "arguments[0].click();",
            software_option
        )

        time.sleep(2)

        tier2 = wait.until(
            EC.element_to_be_clickable(
                (
                    By.ID,
                    "ar1000000064"
                )
            )
        )

        tier2.click()
        tier2.clear()
        tier2.send_keys("New")

        time.sleep(2)

        new_items = driver.find_elements(
            By.XPATH,
            "//*[contains(@title,'New')]"
        )

        if new_items:

            driver.execute_script(
                "arguments[0].click();",
                new_items[0]
            )

        # =====================================================
        # PRODUCT CATEGORY
        # =====================================================

        product_browse = wait.until(
            EC.presence_of_element_located(
                (
                    By.ID,
                    "304420051"
                )
            )
        )

        driver.execute_script(
            "arguments[0].click();",
            product_browse
        )

        hardware_option = wait.until(
            EC.presence_of_element_located(
                (
                    By.XPATH,
                    "//span[text()='Hardware']"
                )
            )
        )

        driver.execute_script(
            "arguments[0].click();",
            hardware_option
        )

        # =====================================================
        # SUPPORT GROUP
        # =====================================================

        support_group = wait.until(
            EC.presence_of_element_located(
                (
                    By.CSS_SELECTOR,
                    '[aria-label="Support group"]'
                )
            )
        )

        support_group.clear()

        support_group.send_keys(
            SUPPORT_GROUP
        )

        time.sleep(2)

        support_group.send_keys(
            Keys.ARROW_DOWN
        )

        time.sleep(1)

        support_group.send_keys(
            Keys.ENTER
        )

        # =====================================================
        # PERSON
        # =====================================================

        person = wait.until(
            EC.element_to_be_clickable(
                (
                    By.CSS_SELECTOR,
                    '[aria-label="Person"]'
                )
            )
        )

        person.clear()
        person.send_keys(PERSON)
        
        time.sleep(2)
        
        person.send_keys(Keys.ARROW_DOWN)
        
        time.sleep(1)
        person.send_keys(Keys.ENTER)
        
        time.sleep(2)
        
        '''person_option = wait.until(
            EC.element_to_be_clickable(
                (
                    By.XPATH,
                    "//*[contains(@title,'Suryakant L Patil')]"
                )
            )
        )

        driver.execute_script(
            "arguments[0].click();",
            person_option
        )'''


        # =====================================================
        # SAVE
        # =====================================================


        save_buttons = driver.find_elements(
            By.CSS_SELECTOR,
            '[title="Save ticket"]'
        )

        if not save_buttons:
            return False, "Save button not found."

        save_button = save_buttons[0]

        driver.execute_script(
            "arguments[0].scrollIntoView({block:'center'});",
            save_button
        )

        time.sleep(1)
        
        print(
            "TEST MODE:",
            test_mode
        )

        print(
            "PERSON VALUE:",
            person.get_attribute("value")
        )

        print(
            "CURRENT URL:",
            driver.current_url
        )

        if test_mode:

            return False, "Form filled successfully. Save skipped."

        driver.execute_script(
            "arguments[0].click();",
            save_button
        )

        # =====================================================
        # WAIT FOR INCIDENT CREATION
        # =====================================================

        WebDriverWait(driver, 30).until(
            lambda d: "/incidentPV/" in d.current_url
        )

        current_url = driver.current_url

        # =====================================================
        # TOKEN EXTRACTION
        # =====================================================

        new_token = current_url.split("/")[-1]

        incident_element = driver.find_element(
            By.ID,
            "ar100000161_data"
        )

        incident_number = incident_element.get_attribute(
            "title"
        ).strip()
            
        try:

            sla_element = WebDriverWait(
                driver,
                10
            ).until(
                EC.presence_of_element_located(
                    (
                        By.ID,
                        "ar304434661_data"
                    )
                )
            )

            sla_date = sla_element.get_attribute(
                "title"
            ).strip()

            
            incident_data = {
                "incident": incident_number,
                "token": new_token,
                "sla": sla_date
            }

            file_name = "paging_incidents.json"

            if os.path.exists(file_name):

                with open(
                    file_name,
                    "r",
                    encoding="utf-8"
                ) as f:

                    incidents = json.load(f)

            else:

                incidents = []

            existing = {
                item["incident"]
                for item in incidents
            }

            if incident_number not in existing:

                incidents.append(
                    incident_data
                )

            with open(
                file_name,
                "w",
                encoding="utf-8"
            ) as f:

                json.dump(
                    incidents,
                    f,
                    indent=4
                )    
                

        except Exception as e:

            print(
                "SLA DATE EXTRACTION FAILED:",
                e
            )

            sla_date = ""                           

        success_msg = (
            f"New incident created successfully. "
            f"Token updated: {new_token}"
        )

        return True, success_msg

    except Exception as e:

        error_text = str(e)

        if "no such window" in error_text.lower():
            error_text = (
                "Window closed by user."
            )

        elif "invalid session id" in error_text.lower():
            error_text = (
                "Message: browser session expired."
            )

        elif not error_text.strip():
            error_text = "Unexpected automation error occurred."

        return False, error_text
        

                