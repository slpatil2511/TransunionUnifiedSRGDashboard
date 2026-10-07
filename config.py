# config.py

from dotenv import load_dotenv
import os

load_dotenv()

# 🛑 Configuration URLs (Primary and Secondary) 🛑
URLS_CLUSTER_API = [
    "https://d4warden.tlkup.srg.gcp.transu.net/api/v1/monitor/node-summary",
    "https://d5warden.tlkup.srg.gcp.transu.net/api/v1/monitor/node-summary"
]
URLS_CLUSTER_DETAILS_API = [
    "https://d4warden.tlkup.srg.gcp.transu.net/api/v1/monitor/node-details",
    "https://d5warden.tlkup.srg.gcp.transu.net/api/v1/monitor/node-details"
]
URL_CLUSTER_ONCALL = "https://d4warden.tlkup.srg.gcp.transu.net/on-call/"
URLS_CLUSTER_FRONTEND = [
    "https://d4warden.tlkup.srg.gcp.transu.net/monitor/all/",
    "https://d5warden.tlkup.srg.gcp.transu.net/monitor/all/"
]

URLS_BATCH = [
    "http://batchstatusd2.tlo.com/",
    "http://batchstatusd4.tlo.com/",
    "https://batchstatusd5.tlo.com/"
]

URLS_DBA_API = [
    "https://d4dbadminp01.tlkup.srg.gcp.transu.net/webservices/GetNocStatus.php",
    "https://d5dbadminp01.tlkup.srg.gcp.transu.net/webservices/GetNocStatus.php"
]
URLS_DBA_FRONTEND = [
    "https://d4dbadminp01.tlkup.srg.gcp.transu.net/noc_dba.php?calledfromgui",
    "https://d5dbadminp01.tlkup.srg.gcp.transu.net/noc_dba.php?calledfromgui"
]

# 🛑 Outlook Folders 🛑
TARGET_OUTLOOK_FOLDERS = ["Code Blue", "Prove Support", "PMASS", "Zabbix alerts", "Remedy SRG"]



# 🛑 ATLASSIAN SECURE CREDENTIALS 🛑
ATLASSIAN_EMAIL = "suryakant.patil@transunion.com"
ATLASSIAN_API_TOKEN = os.getenv("ATLASSIAN_TOKEN","")
ATLASSIAN_TOKEN_EXPIRY = "2026-10-30"
print(
    "ATLASSIAN TOKEN FOUND:",
    bool(ATLASSIAN_API_TOKEN)
)

# 🛑 TEAMS WEBHOOK 🛑
# Paste the Incoming Webhook URL generated from your Teams Channel here
#TEAMS_WEBHOOK_URL = "https://default0685d76043324f24b2eaffbbc2383f.15.environment.api.powerplatform.com:443/powerautomate/automations/direct/cu/05/workflows/d743554aa6274b5596bad8cad94191d4/triggers/manual/paths/invoke?api-version=1&sp=%2Ftriggers%2Fmanual%2Frun&sv=1.0&sig=ayhHs_CXzar41_RLO_gDNlaHQc6A8p29DetUYooFp8Q"
TEAMS_WEBHOOK_URL = "https://default0685d76043324f24b2eaffbbc2383f.15.environment.api.powerplatform.com:443/powerautomate/automations/direct/cu/15/workflows/c0316e1d0a3e4a39acfb1cc035160642/triggers/manual/paths/invoke?api-version=1&sp=%2Ftriggers%2Fmanual%2Frun&sv=1.0&sig=a1joo6X0u3-THNwL9CYDvNLPH0Y8PqqIWOA0xaBRRQg"
# --- Confluence REST API URLs ---
CONFLUENCE_BATCH_API = "https://transunion.atlassian.net/wiki/rest/api/content/4204593515?expand=body.view"
CONFLUENCE_DEVOPS_API = "https://transunion.atlassian.net/wiki/rest/api/content/4204070322?expand=body.view"

# 🛑 TEAMS CHANNEL ID (For tagging the Public SRG_IT Chat) 🛑
#TEAMS_CHANNEL_ID = "19%3A029486ac57cf4c5490f04bdff4c736e6%40thread.tacv2"
TEAMS_CHANNEL_ID = "19%3A6c3b53-9WPg9sxkYvZL30FoEsVm5QxRECWxOw0vijBo1%40thread.tacv2"

# 🛑 PMASS Excel Mapping 🛑
# Using 'r' before the string ensures Windows backslashes are read correctly
#PMASS_EXCEL_PATH = r"C:\Users\slpatil\OneDrive - TransUnion LLC\NOC_Dashboard_Master\GCP-Inventory-Teams-April28 1.xlsx"

# 🛑 REMEDY PAGING SYSTEM 🛑
REMEDY_PAGING_URL = "https://transunion-smartit.onbmc.com/smartit/app/#/incidentPV/IDGE6M80C0ZJHAT9OZO5T9OZO5FQY9"

# 🔴 AI AGENT CONFIGURATION 🔴
# Example URL from the doc: "https://onetru-genai-llmops-api-demo-cl1.ipaas.neustar.com"
AURA_API_KEY = "paste-your-onetru-key-here"
AURA_BASE_URL = "https://genai-fdev-indmns1.ipaas.neustar.com/api/v2/chat"