# noc_data.py

from config import *
import streamlit as st
import requests
from bs4 import BeautifulSoup
import urllib3
try:
    from requests_negotiate_sspi import HttpNegotiateAuth
except ImportError:
    HttpNegotiateAuth = None
import urllib.request
import os
import socket
import requests.packages.urllib3.util.connection as urllib3_cn
import time
import base64
import pandas as pd
import win32com.client
import pythoncom
import concurrent.futures
import re
import threading
import io
from datetime import datetime
from streamlit.runtime.scriptrunner import add_script_run_ctx
from io import StringIO
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

ENABLE_AUTO_READ = False

def allowed_gai_family(): return socket.AF_INET
urllib3_cn.allowed_gai_family = allowed_gai_family
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
os.environ['NO_PROXY'] = '*'
os.environ['no_proxy'] = '*'

def fast_robust_fetch(url, state_key, is_json=False, is_dba=False):
    combos = []

    if HttpNegotiateAuth:
        combos.extend([
            {
                "proxies": urllib.request.getproxies(),
                "auth": HttpNegotiateAuth()
            },
            {
                "proxies": {"http": None, "https": None},
                "auth": HttpNegotiateAuth()
            }
        ])

    combos.extend([
        {
            "proxies": urllib.request.getproxies(),
            "auth": None
        },
        {
            "proxies": {"http": None, "https": None},
            "auth": None
        }
    ])
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept": "application/json, text/javascript, */*; q=0.01" if is_json else "text/html,application/xhtml+xml"
    }
    if is_dba:
        headers.update({
            "X-Requested-With": "XMLHttpRequest", 
            "Referer": URLS_DBA_FRONTEND[0],
            "sec-ch-ua": '"Not;A=Brand";v="8", "Chromium";v="150", "Google Chrome";v="150"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"'
        })

    def attempt(i, combo):
        try:
            if is_dba: requests.get(URLS_DBA_FRONTEND[0], headers=headers, proxies=combo["proxies"], auth=combo["auth"], verify=False, timeout=5)
            resp = requests.get(url, headers=headers, proxies=combo["proxies"], auth=combo["auth"], verify=False, timeout=5)
            if resp.status_code == 200: return (resp.json() if is_json else resp.text), i
        except: pass
        return None, None

    if state_key in st.session_state:
        idx = st.session_state[state_key]
        res, _ = attempt(idx, combos[idx])
        if res is not None: return res

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(attempt, i, c) for i, c in enumerate(combos)]
        for future in concurrent.futures.as_completed(futures):
            res, idx = future.result()
            if res is not None:
                st.session_state[state_key] = idx
                return res
                
    return "Error: Timeout or Blocked"
    
@st.cache_data(ttl=120)
def get_cluster_node_alerts(hostname):

    alerts = []

    for api_url_base in URLS_CLUSTER_DETAILS_API:

        try:

            api_url = (
                f"{api_url_base}"
                f"?hostname={urllib.parse.quote(hostname)}"
            )

            resp = requests.get(
                api_url,
                proxies={"http": None, "https": None},
                verify=False,
                timeout=5
            )

            if resp.status_code != 200:
                continue

            data = resp.json()

            for check in data.get("checkresults", []):

                if check.get("status", 0) not in [1, 2, -1]:
                    continue

                desc = str(
                    check.get("description", "")
                ).strip()

                output = str(
                    check.get("output", "")
                ).strip()

                alerts.append(
                    f"{desc} {output}"
                )

            break

        except Exception:
            pass

    return alerts

def get_cluster_issues():
    issues = {} 
    has_errors = False
    errors = []
    lock = threading.Lock()
    
    
    def fetch_api(api_url):
        nonlocal has_errors
        try:
            url_with_time = f"{api_url}?_={int(time.time())}"
            headers = {"Cache-Control": "no-cache", "Pragma": "no-cache", "Referer": URLS_CLUSTER_FRONTEND[0], "User-Agent": "Mozilla/5.0"}
            response = requests.get(url_with_time, headers=headers, proxies={"http": None, "https": None}, verify=False, timeout=5)
            if response.status_code != 200:
                response = requests.get(url_with_time, headers=headers, proxies=urllib.request.getproxies(), verify=False, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                with lock:
                    for group in data.get('results', []):
                        host_name = group.get('name', 'Unknown')
                        for cluster in group.get('clusters', []):
                            cluster_abbrv = cluster.get('abbrv', '')
                            for node in cluster.get('nodes', []):
                                status = str(node.get('status', '0'))
                                if status != '0': 
                                    has_errors = True
                                    node_id = str(node.get('nodeid', '0')).zfill(2)
                                    full_hostname = node.get('hostname', '') 
                                    
                                    if host_name not in issues: issues[host_name] = {}
                                    if cluster_abbrv not in issues[host_name]: issues[host_name][cluster_abbrv] = {}
                                    issues[host_name][cluster_abbrv][node_id] = {
                                        "id": node_id,
                                        "status": status,
                                        "hostname": full_hostname,
                                        #"alerts": get_node_alerts(full_hostname)
                                    }
            else:
                with lock: errors.append(f"HTTP {response.status_code}")
        except Exception as e:
            with lock: errors.append(str(e))

    threads = []
    for url in URLS_CLUSTER_API:
        t = threading.Thread(target=fetch_api, args=(url,))
        add_script_run_ctx(t)
        threads.append(t)
        t.start()
    for t in threads: t.join()
            
    if not has_errors and errors and len(errors) == len(URLS_CLUSTER_API):
        return {"_error": f"Failed to fetch from both Cluster APIs."}
        
    final_issues = {}
    for host, clusters in issues.items():
        final_issues[host] = {}
        for abbrv, nodes_dict in clusters.items():
            final_issues[host][abbrv] = list(nodes_dict.values())
            
    return final_issues if has_errors else {}

def get_batch_issues():
    issues_set = set()
    display_issues = []
    lock = threading.Lock()
    
    def fetch_api(i, url):
        html_data = fast_robust_fetch(url, f'batch_idx_{i}', is_json=False)
        if isinstance(html_data, str) and html_data.startswith("Error:"):
            html_data = fast_robust_fetch(url.replace("http://", "https://"), f'batch_idx_{i}', is_json=False)
            
        if not isinstance(html_data, str) or html_data.startswith("Error:"):
            return

        try:
            soup = BeautifulSoup(html_data, 'html.parser')
            datacenters = soup.find_all('div', class_='datacenter')
            for dc in datacenters:
                dc_name_elem = dc.find('h1')
                dc_name = dc_name_elem.text.strip() if dc_name_elem else "Unknown DC"
                img = dc.find('img')
                
                local_issues = []
                if img and 'OK.jpg' not in img.get('src', ''):
                    local_issues.append(f"Batch Service {dc_name} is down")
                
                for service in dc.find_all('p'):
                    classes = service.get('class', [])
                    text = service.text.strip()
                    if text and 'active' not in classes and 'width_limit' not in classes:
                        local_issues.append(f"{dc_name}: {text}")
                        
                with lock:
                    for err_msg in local_issues:
                        if err_msg not in issues_set:
                            issues_set.add(err_msg)
                            display_issues.append(err_msg)
        except: pass

    threads = []
    for i, url in enumerate(URLS_BATCH):
        t = threading.Thread(target=fetch_api, args=(i, url))
        add_script_run_ctx(t)
        threads.append(t)
        t.start()
    for t in threads: t.join()
        
    return display_issues

def get_dba_issues():
    issues_set = set()
    display_issues = []
    lock = threading.Lock()
    
    def fetch_api(i, url):
        json_data = fast_robust_fetch(url, f'dba_idx_{i}', is_json=True, is_dba=True)
        if isinstance(json_data, str) and json_data.startswith("Error:"): return

        try:
            data_obj = json_data.get('data', {})
            local_issues = []
            
            for item in data_obj.get('status_info', []):
                if item.get('msg', ''):
                    clean_text = BeautifulSoup(item['msg'], "html.parser").text.strip()
                    if clean_text: local_issues.append(clean_text)
                    
            for err in data_obj.get('errmsg', []):
                if isinstance(err, str) and err.strip():
                    clean_err = BeautifulSoup(err, "html.parser").text.strip()
                    if clean_err: local_issues.append(clean_err)
                    
            with lock:
                for text in local_issues:
                    norm_issue = re.sub(r'\b\d+\s*(?:second|sec|minute|min|hour|hr)(?:s|\(s\))?(?!\w)', '{TIME}', text, flags=re.IGNORECASE)
                    if norm_issue not in issues_set:
                        issues_set.add(norm_issue)
                        display_issues.append(text)
        except: pass

    threads = []
    for i, url in enumerate(URLS_DBA_API):
        t = threading.Thread(target=fetch_api, args=(i, url))
        add_script_run_ctx(t)
        threads.append(t)
        t.start()
    for t in threads: t.join()
        
    return display_issues

def fetch_outlook_background():
    email_data = {}
    try:
        pythoncom.CoInitialize()
        outlook = win32com.client.Dispatch("Outlook.Application").GetNamespace("MAPI")
        inbox = outlook.GetDefaultFolder(6) 
        root_folder = inbox.Parent 
        
        for folder_name in TARGET_OUTLOOK_FOLDERS:
            try:
                folder = None
                try: folder = root_folder.Folders.Item(folder_name)
                except: pass
                
                if not folder:
                    try: folder = inbox.Folders.Item(folder_name)
                    except: pass
                
                if not folder:
                    for subfolder in inbox.Folders:
                        try: 
                            folder = subfolder.Folders.Item(folder_name)
                            if folder: break
                        except: pass
                
                if not folder:
                    raise Exception("Folder not found. Ensure it is placed under your Inbox.")

                unread_items = folder.Items.Restrict("[Unread] = True")
                unread_items.Sort("[ReceivedTime]", True) 
                
                count = unread_items.Count
                emails = []

                # Cleanup entire folder
                if ENABLE_AUTO_READ:

                    msgs_to_process = []

                    for i in range(
                        1,
                        unread_items.Count + 1
                    ):

                        try:

                            msgs_to_process.append(
                                unread_items.Item(i)
                            )

                        except Exception as e:

                            print(
                                f"Collect Error: {e}"
                            )

                    for msg in msgs_to_process:

                        try:

                            received_time = (
                                msg.ReceivedTime
                                .replace(tzinfo=None)
                            )

                            age_seconds = (
                                datetime.now()
                                - received_time
                            ).total_seconds()

                            print(
                                "CLEANUP FOLDER:",
                                folder_name
                            )

                            print(
                                "CLEANUP SUBJECT:",
                                msg.Subject
                            )

                            print(
                                "AGE:",
                                age_seconds
                            )

                            print(
                                "UNREAD BEFORE:",
                                msg.UnRead
                            )

                            if age_seconds >= 7200:

                                print(
                                    "MARKING READ (2 HOURS):",
                                    msg.Subject
                                )

                                msg.UnRead = False
                                msg.Save()

                                print(
                                    "UNREAD AFTER:",
                                    msg.UnRead
                                )

                            elif age_seconds >= 600:

                                print(
                                    "MARKING READ (6 MIN):",
                                    msg.Subject
                                )

                                msg.UnRead = False
                                msg.Save()

                                print(
                                    "UNREAD AFTER:",
                                    msg.UnRead
                                )

                        except Exception as e:

                            print(
                                f"Cleanup Error: {e}"
                            )
            
                # Refresh unread collection after cleanup
                unread_items = folder.Items.Restrict(
                    "[Unread] = True"
                )

                unread_items.Sort(
                    "[ReceivedTime]",
                    True
                )

                count = unread_items.Count
                emails = []
                
                for i in range(1, min(count, 10) + 1):

                    try:

                        msg = unread_items.Item(i)

                        subj = getattr(
                            msg,
                            'Subject',
                            'No Subject'
                        )

                        recv_time = str(
                            getattr(
                                msg,
                                'ReceivedTime',
                                ''
                            )
                        )[:16]

                        emails.append(
                            {
                                "subject": subj,
                                "time": recv_time
                            }
                        )

                    except:
                        pass
                    
                email_data[folder_name] = {"count": count, "emails": emails}
            except Exception as e:
                email_data[folder_name] = {"count": 0, "emails": [{"subject": f"Error: {e}", "time": ""}]}
    except Exception as e:
        email_data["Outlook Error"] = {"count": 0, "emails": [{"subject": f"Ensure Classic Outlook is open. ({e})", "time": ""}]}
    
    st.session_state.cached_email_data = email_data
    
def fetch_confluence_secure(page_id):
    url = f"https://transunion.atlassian.net/wiki/rest/api/content/{page_id}?expand=body.view"
    auth_string = f"{ATLASSIAN_EMAIL}:{ATLASSIAN_API_TOKEN}"
    encoded_auth = base64.b64encode(auth_string.encode('ascii')).decode('ascii')
    headers = {"Accept": "application/json", "Authorization": f"Basic {encoded_auth}", "User-Agent": "Mozilla/5.0"}
    proxies = urllib.request.getproxies()
    try:
        resp = requests.get(url, headers=headers, proxies=proxies, verify=False, timeout=10)
       
        if resp.status_code != 200:
            print("RESPONSE:")
            print(resp.text[:1000])
        if resp.status_code == 200:
            html_content = resp.json().get("body", {}).get("view", {}).get("value", "")
            if html_content:
                soup = BeautifulSoup(html_content, 'html.parser')
                tables = soup.find_all('table')
                if tables:
                    combined_html = ""
                    for table in tables:
                        table['class'] = 'oncall-table'
                        for tag in table.find_all(['table', 'th', 'td', 'colgroup', 'col']):
                            tag.attrs = {k: v for k, v in tag.attrs.items() if k == 'class'}
                        combined_html += str(table) + "<br><br>"
                    return combined_html
                return html_content 
        raise Exception(f"HTTP {resp.status_code}: {resp.text[:100]}")
    except Exception as e:
        raise Exception(f"API Fetch Error: {e}")

# --- CACHED ON-CALL FETCHERS ---

@st.cache_data(ttl=300)
def load_pmass_mapping():

    page_id = "4297097259"

    html = fetch_confluence_secure(
        page_id
    )

    tables = pd.read_html(
        StringIO(html),
        header=0
    )

    if tables:

        df = tables[0]

        print(
            "PMASS COLUMNS:",
            list(df.columns)
        )

        print(
            "PMASS SAMPLE:"
        )

        print(
            df.head(3)
        )

        return df

    return pd.DataFrame()


def find_email_for_name(target_name, dfs):
    """Helper to scan all Confluence tables for a name and extract their email."""
    target_clean = str(target_name).lower().strip()
    if not target_clean or target_clean == 'nan': return ""
    
    for df in dfs:
        for _, row in df.iterrows():
            row_str = " ".join([str(x) for x in row.values]).lower()
            emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', row_str)
            if emails:
                # Check if the target name is in the first column (usually the Name column)
                name_col_val = str(row.iloc[0]).lower()
                if target_clean in name_col_val or name_col_val in target_clean:
                    return emails[0]
                # Fallback: check if any part of the name > 3 chars matches
                for part in target_clean.replace(',', ' ').split():
                    if len(part) > 3 and part in name_col_val:
                        return emails[0]
    return ""

@st.cache_data(ttl=3600)
def _fetch_cluster_oncall_cached():
    html = fetch_confluence_secure("4205052152")
    if not html: raise Exception("Confluence fetch returned empty data")
    try:
        dfs = pd.read_html(io.StringIO(html))
        if dfs: 
            combined_df = pd.concat(dfs, ignore_index=True)
            return combined_df
    except: pass
    return html

def get_cluster_oncall():
    try: return _fetch_cluster_oncall_cached()
    except Exception as e: return pd.DataFrame([{"Status": f"?? Confluence Error: {e}"}])

@st.cache_data(ttl=3600)
def _fetch_batch_oncall_cached():
    html = fetch_confluence_secure("4204593515")
    if not html: raise Exception("Confluence fetch returned empty data")
    try:
        dfs = pd.read_html(io.StringIO(html))
        # Find the schedule table
        schedule_df = next((df for df in dfs if any('ist' in str(c).lower() or 'shift' in str(c).lower() for c in df.columns)), None)
        if schedule_df is not None:
            clean_data = []
            for _, row in schedule_df.iterrows():
                name = str(row.iloc[0])
                est = str(row.iloc[1]) if len(row) > 1 else ""
                ist = str(row.iloc[2]) if len(row) > 2 else ""
                email = find_email_for_name(name, dfs)
                clean_data.append({"Name": name, "Shift Time (EST)": est, "Shift Time (IST)": ist, "Email": email})
            return pd.DataFrame(clean_data)
    except Exception as e:
        print(f"Batch Merge Error: {e}")
    return html

def get_batch_oncall():
    try: return _fetch_batch_oncall_cached()
    except Exception as e: return pd.DataFrame([{"Status": f"?? Confluence Error: {e}"}])

@st.cache_data(ttl=3600)
def _fetch_dba_oncall_cached():
    df_or_html = fetch_confluence_secure("4155540591")
    if df_or_html is not None: return df_or_html
    raise Exception("Confluence fetch returned empty data")

def get_dba_oncall():
    try: return _fetch_dba_oncall_cached()
    except Exception as e: return pd.DataFrame([{"Status": f"?? Confluence Error: {e}"}])

@st.cache_data(ttl=3600)
def _fetch_devops_oncall_cached():
    html = fetch_confluence_secure("4204070322")
    if not html: raise Exception("Confluence fetch returned empty data")
    try:
        dfs = pd.read_html(io.StringIO(html))
        # Find the schedule table
        schedule_df = next((df for df in dfs if any('start' in str(c).lower() for c in df.columns)), None)
        if schedule_df is not None:
            clean_data = []
            for _, row in schedule_df.iterrows():
                start, end = str(row.iloc[0]), str(row.iloc[1])
                pri = str(row.iloc[2]) if len(row) > 2 else ""
                sec = str(row.iloc[3]) if len(row) > 3 else ""
                
                pri_email = find_email_for_name(pri, dfs)
                sec_email = find_email_for_name(sec, dfs)
                
                clean_data.append({
                    "Start Date": start, "End Date": end,
                    "Primary": pri, "Primary Email": pri_email,
                    "Secondary": sec, "Secondary Email": sec_email
                })
            return pd.DataFrame(clean_data)
    except Exception as e:
        print(f"DevOps Merge Error: {e}")
    return html

def get_devops_oncall():
    try: return _fetch_devops_oncall_cached()
    except Exception as e: return pd.DataFrame([{"Status": f"?? Confluence Error: {e}"}])

# --- NEW: Real Estate Fetcher (Merged Tables) ---
@st.cache_data(ttl=3600)
def _fetch_real_estate_oncall_cached():
    # Using the new Page ID
    html = fetch_confluence_secure("4221042690")
    if not html: raise Exception("Confluence fetch returned empty data")
    try:
        dfs = pd.read_html(io.StringIO(html))
        if dfs:
            # Find the schedule table (usually contains 'time' or 'shift')
            schedule_df = next((df for df in dfs if any('time' in str(c).lower() or 'shift' in str(c).lower() for c in df.columns)), dfs[0])
            
            clean_data = []
            for _, row in schedule_df.iterrows():
                row_dict = row.to_dict()
                # Find the name column to cross-reference
                name_col = next((c for c in schedule_df.columns if 'name' in str(c).lower()), schedule_df.columns[0])
                name = str(row[name_col])
                
                # Cross-reference the other tables to find their email
                row_dict["Email"] = find_email_for_name(name, dfs)
                clean_data.append(row_dict)
                
            return pd.DataFrame(clean_data)
    except Exception as e:
        print(f"Real Estate Merge Error: {e}")
    return html

def get_real_estate_oncall():
    try: return _fetch_real_estate_oncall_cached()
    except Exception as e: return pd.DataFrame([{"Status": f"?? Confluence Error: {e}"}])

def get_crisis_connect_data():
    return pd.DataFrame({
        "Remedy Group Names": [
            "SRG BobNet", "SRG Batch", "SRG Data", "SRG Infra", "SRG Lego", 
            "SRG QA", "SRG Database", "SRG Eternals", "SRG Mutants", "SRG Defenders", 
            "SRG Reporting", "SRG Avengers", "SRG Guardians", "SRG Prefill", "SRG OpsExcel", 
            "SRG Devops Support"
        ],
        "Crisis Connect Group Names": [
            "SRG BobNet On-Call", "SRG Batch On-Call", "SRG Data On-Call", "SRG Infra On-Call", 
            "SRG Lego On-Call", "SRG QA On-Call", "SRG Database On-Call", "SRG Eternals On-Call", 
            "SRG Mutants On-Call", "SRG Defenders On-Call", "SRG Reporting On-Call", "SRG Avengers On-Call", 
            "SRG Guardians On-Call", "SRG Prefill On-Call", "SRG OpsExcel On-Call", 
            "SRG Devops Support On-Call"
        ],
        "Group Admin Names": [
            "Tsybulski, Dmitry", "Sahu, Vivek", "Gollapudi, Sreelatha", "Vitthalingalkar, Pavan", 
            "Chauhan, Nitisha", "Tonge, Nikhil", "Gupta, Nikita", "Rajput, Jitendra", "Thorat, Gautam", 
            "K, Narasimha", "PradipShete, Manoj", "Karden, Jacob", "Karden, Jacob", "Kore, Ravindra", 
            "Madhumitha, kotturi", "DevOps Admin"
        ]
    })

def perform_data_fetch():
    email_thread = threading.Thread(target=fetch_outlook_background)
    add_script_run_ctx(email_thread)
    email_thread.start()

    cluster_data = {}
    batch_data = []
    dba_data = []
    
    def fetch_c(): nonlocal cluster_data; cluster_data = get_cluster_issues()
    def fetch_b(): nonlocal batch_data; batch_data = get_batch_issues()
    def fetch_d(): nonlocal dba_data; dba_data = get_dba_issues()

    t1 = threading.Thread(target=fetch_c)
    t2 = threading.Thread(target=fetch_b)
    t3 = threading.Thread(target=fetch_d)
    
    add_script_run_ctx(t1); add_script_run_ctx(t2); add_script_run_ctx(t3)
    t1.start(); t2.start(); t3.start()
    t1.join(); t2.join(); t3.join()
    email_thread.join()
    
    st.session_state.last_cluster_data = cluster_data
    st.session_state.last_batch_data = batch_data
    st.session_state.last_dba_data = dba_data

def post_to_teams(message_text, auto_mentions=None, image_base64=None):
    if not TEAMS_WEBHOOK_URL:
        return False, "Webhook URL is missing in config.py"
    
    entities = []
    formatted_message = message_text.replace('\r\n', '\n')
    formatted_message = re.sub(r'\n+', '\n\n', formatted_message)
    
    if auto_mentions:
        for m in auto_mentions:
            name = m['name']
            email = m['email']
            if name in formatted_message:
                formatted_message = formatted_message.replace(name, f"<at>{name}</at>")
                entities.append({
                    "type": "mention",
                    "text": f"<at>{name}</at>",
                    "mentioned": {"id": email, "name": name}
                })
                
    manual_emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', formatted_message)
    for email in manual_emails:
        name_part = email.split('@')[0]
        if '.' in name_part:
            parts = name_part.split('.')
            display_name = f"{parts[0].capitalize()} {parts[1].capitalize()}"
        else:
            display_name = name_part.capitalize()
            
        formatted_message = formatted_message.replace(email, f"<at>{display_name}</at>")
        entities.append({
            "type": "mention",
            "text": f"<at>{display_name}</at>",
            "mentioned": {"id": email, "name": display_name}
        })

    if "Public SRG_IT Chat" in formatted_message and "<at>Public SRG_IT Chat</at>" not in formatted_message:
        formatted_message = formatted_message.replace("Public SRG_IT Chat", "<at>Public SRG_IT Chat</at>")
        
        import urllib.parse as uparse 
        channel_id = globals().get('TEAMS_CHANNEL_ID', '')
        
        if channel_id:
            clean_channel_id = uparse.unquote(channel_id)
            entities.append({
                "type": "mention",
                "text": "<at>Public SRG_IT Chat</at>",
                "mentionType": "channel",
                "mentioned": {
                    "id": clean_channel_id,
                    "name": "Public SRG_IT Chat"
                }
            })
        else:
            entities.append({
                "type": "mention",
                "text": "<at>Public SRG_IT Chat</at>",
                "mentioned": {"id": "Public SRG_IT Chat", "name": "Public SRG_IT Chat"}
            })

    if image_base64:
        formatted_message = f"?? **CRITICAL ALERT** ??\n\n{formatted_message}"

    card_body = [
        {
            "type": "TextBlock",
            "text": formatted_message,
            "wrap": True
        }
    ]
            
    payload = {
        "type": "message",
        "attachments": [
            {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": {
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "type": "AdaptiveCard",
                    "version": "1.2",
                    "body": card_body,
                    "msteams": {
                        "entities": entities
                    }
                }
            }
        ]
    }
    
    proxies = urllib.request.getproxies()
    try:
        resp = requests.post(TEAMS_WEBHOOK_URL, json=payload, proxies=proxies, verify=False, timeout=10)
        if resp.status_code in [200, 201, 202]:
            return True, "Success"
        else:
            return False, f"HTTP {resp.status_code}: {resp.text}"
    except Exception as e:
        return False, str(e)
