#noc_ui.py

from config import *
from noc_tags import *
from noc_teams import *
from noc_data import *
import streamlit as st
import time
from datetime import datetime
from datetime import date
import base64
import os
import urllib.parse
import requests
import re
import threading
from plyer import notification
try:
    import winsound
except ImportError:
    winsound = None
import pandas as pd
from bs4 import BeautifulSoup
from streamlit.runtime.scriptrunner import add_script_run_ctx
import io
import streamlit.components.v1 as components
import asyncio
import sys
import json

if sys.platform == 'win32':
    try:
        loop = asyncio.get_running_loop()
        def handle_asyncio_exception(loop, context):
            exc = context.get("exception")
            if isinstance(exc, ConnectionResetError):
                pass  
            else:
                loop.default_exception_handler(context)
        loop.set_exception_handler(handle_asyncio_exception)
    except RuntimeError:
        pass  
@st.cache_data(ttl=600)
def check_roster_expiry(
    team_name,
    last_date,
    notification_id
):

    try:

        if isinstance(last_date, str):

            # DevOps format: 10/08/26
            if "/" in last_date:

                expiry_date = datetime.strptime(
                    last_date,
                    "%m/%d/%y"
                ).date()

            # Cluster/Batch/DBA format: 31-Oct-26
            else:

                expiry_date = datetime.strptime(
                    last_date,
                    "%d-%b-%y"
                ).date()

        else:

            expiry_date = last_date

        days_left = (
            expiry_date - date.today()
        ).days


        if days_left < 0:

            add_notification(
                notification_id,
                "critical",
                f"{team_name} Roster Expired",
                (
                    f"Please reach {team_name} team "
                    f"to update their roster schedule "
                    f"on Confluence."
                )
            )

        elif days_left <= 3:

            add_notification(
                notification_id,
                "warning",
                f"{team_name} Roster Expiring",
                (
                    f"{team_name} roster expires in "
                    f"{days_left} day(s). "
                    f"Please reach {team_name} team "
                    f"to update their roster schedule "
                    f"on Confluence."
                )
            )

        else:

            remove_notification(
                notification_id
            )

    except Exception as e: 
        print(e)

def add_notification(
    notif_id,
    severity,
    title,
    message
):

    notifications = st.session_state.get(
        "notifications",
        []
    )

    existing_ids = {
        n["id"]
        for n in notifications
    }

    if notif_id in existing_ids:
        return

    notifications.append(
        {
            "id": notif_id,
            "severity": severity,
            "title": title,
            "message": message,
            "created": datetime.now().strftime(
                "%d-%b-%Y %H:%M"
            )
        }
    )

    st.session_state[
        "notifications"
    ] = notifications


def remove_notification(
    notif_id
):

    st.session_state[
        "notifications"
    ] = [
        n
        for n in st.session_state.get(
            "notifications",
            []
        )
        if n["id"] != notif_id
    ]        
@st.cache_data(ttl=10)
def get_saved_token():

    try:

        if os.path.exists(
            "paging_incidents.json"
        ):

            with open(
                "paging_incidents.json",
                "r",
                encoding="utf-8"
            ) as f:

                incidents = json.load(f)

            if incidents:

                return incidents[-1]["token"]

    except Exception as e:

        print(
            "TOKEN LOAD ERROR:",
            e
        )

    return "" 

def time_ago(epoch):
    if not epoch: return ""
    diff = time.time() - epoch
    if diff < 60: return "a few seconds ago"
    elif diff < 3600: return f"{int(diff//60)} minutes ago"
    elif diff < 86400: return f"{int(diff//3600)} hours ago"
    else: return f"{int(diff//86400)} days ago"

def render_oncall_data(data):
    if isinstance(data, pd.DataFrame):
        st.markdown(data.to_html(index=False, classes='oncall-table', escape=False), unsafe_allow_html=True)
    elif isinstance(data, str):
        st.markdown(data, unsafe_allow_html=True)

def get_status_ui(status_val):
    s = str(status_val)
    if s == '1': return "#fff3cd", "#ffeeba", "Warning", "🟡"
    elif s == '-1': return "#ffc0cb", "#ffb6c1", "Stale", "🔴"
    elif s != '0': return "#f8d7da", "#f5c6cb", "Critical", "🔴"
    else: return "#f8f9fa", "#ddd", "OK", "🟢"
   
@st.dialog("🖥️ Node Diagnostics", width="large")
def show_node_details(hostname):
    with st.spinner("Pulling live diagnostics..."):
        st.query_params.clear()
        data = None
        for api_url_base in URLS_CLUSTER_DETAILS_API:
            try:
                api_url = f"{api_url_base}?hostname={urllib.parse.quote(hostname)}"
                resp = requests.get(api_url, proxies={"http": None, "https": None}, verify=False, timeout=5)
                if resp.status_code == 200:
                    data = resp.json()
                    break
            except: pass
            
        if not data:
            st.error("Failed to fetch details from both D4 and D5 servers.")
            if st.button("Close Diagnostics", use_container_width=True):
                st.session_state.active_node = None
                st.rerun()
            return

    cluster_name = data.get("cluster_name", "Unknown")
    ipaddress = data.get("ipaddress", "Unknown")
    location = data.get("location", "Unknown")
    overall_status = data.get("status", 0)
    overall_bg, overall_border, overall_text, overall_dot = get_status_ui(overall_status)

    html = f"""
    <h4 style='margin-top:0; color: #333; border-bottom: 1px solid #eee; padding-bottom: 10px;'>{cluster_name} - {hostname}</h4>
    <div style='border: 1px solid {overall_border}; border-radius: 6px; padding: 8px 12px; margin-bottom: 15px; font-family: sans-serif; font-size: 12px; background-color: {overall_bg};'>
        <div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 5px;'>
            <div><b>Overall</b><br><span style='font-size:11px;'>{overall_text}</span></div>
            <div style='display: flex; align-items: center; gap: 8px;'>
                <span style='color: #0099B9; font-size: 10px;'>{time_ago(data.get('last_updated_epoch'))}</span>
                <span style='font-size: 16px;'>{overall_dot}</span>
            </div>
        </div>
        <div style='font-size: 11px; text-align: center; margin-top: 5px;'>
            <b>Host Name:</b> {hostname} &nbsp;|&nbsp; <b>IP Address:</b> {ipaddress} &nbsp;|&nbsp; <b>Cluster:</b> {cluster_name} &nbsp;|&nbsp; <b>Location:</b> {location}
        </div>
    </div>
    """
    
    procmon_html = ""
    grid_html = "<div style='display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 15px;'>"
    full_width_html = ""
    
    for check in data.get("checkresults", []):
        c_name = check.get("name", "")
        c_desc = check.get("description", c_name)
        c_out = check.get("output", "").replace("\\n", "<br>").replace("\n", "<br>")
        c_stat = check.get("status", 0)
        c_epoch = check.get("last_updated_epoch")
        c_bg, c_border, _, c_dot = get_status_ui(c_stat)
        t_ago = time_ago(c_epoch)
        
        if c_name == "cfunction:procmon":
            procmon_html += f"<div style='border: 1px solid #ddd; border-radius: 6px; padding: 8px 12px; margin-bottom: 10px; font-family: sans-serif; font-size: 12px; background-color: #ffffff;'>"
            procmon_html += f"<div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 5px;'><span style='font-weight: bold; font-size: 13px; color: #333;'>{c_desc}</span>"
            procmon_html += f"<div style='display: flex; align-items: center; gap: 8px;'><span style='color: #0099B9; font-size: 10px;'>{t_ago}</span><span style='font-size: 14px;'>{c_dot}</span></div></div>"
            procmon_html += "<table style='width: 100%; border-collapse: collapse; font-size: 11px; margin-top: 5px;'><tr><th style='border-bottom: 1px solid #eee; padding: 4px; text-align: left; color: #555;'>Service</th><th style='border-bottom: 1px solid #eee; padding: 4px; text-align: left; color: #555;'>Status</th><th style='border-bottom: 1px solid #eee; padding: 4px; text-align: left; color: #555;'>Restart Count</th><th style='border-bottom: 1px solid #eee; padding: 4px; text-align: left; color: #555;'>Monitored</th><th style='border-bottom: 1px solid #eee; padding: 4px; text-align: left; color: #555;'>Last Restart</th></tr>"
            lines = check.get("output", "").split("\\n")
            if len(lines) == 1: lines = check.get("output", "").split("\n")
            for line in lines:
                if not line.strip(): continue
                try:
                    parts = line.split(',')
                    srv_stat = parts[0].split(':')
                    srv = srv_stat[0].strip()
                    stat = srv_stat[1].strip()
                    rst = parts[1].replace('restartcount', '').strip()
                    mon = parts[2].replace('monitored', '').strip()
                    lrst = parts[3].replace('Last Restart Time', '').strip()
                    procmon_html += f"<tr><td style='border-bottom: 1px solid #eee; padding: 4px;'>{srv}</td><td style='border-bottom: 1px solid #eee; padding: 4px;'>{stat}</td><td style='border-bottom: 1px solid #eee; padding: 4px;'>{rst}</td><td style='border-bottom: 1px solid #eee; padding: 4px;'>👁️</td><td style='border-bottom: 1px solid #eee; padding: 4px;'>{lrst}</td></tr>"
                except:
                    procmon_html += f"<tr><td colspan='5' style='border-bottom: 1px solid #eee; padding: 4px;'>{line}</td></tr>"
            procmon_html += "</table></div>"
        else:
            card_width = "100%" if ("Disk Space in Bytes" in c_desc or "get-all-disk-space" in c_name) else "calc(33.333% - 10px)"
            card_html = f"<div style='flex: 1 1 {card_width}; min-width: 200px; box-sizing: border-box; border: 1px solid {c_border}; border-radius: 6px; padding: 8px 12px; background-color: {c_bg}; font-family: sans-serif;'>"
            card_html += f"<div style='display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 4px;'>"
            card_html += f"<div style='font-weight: bold; font-size: 12px; color: #333;'>{c_desc}</div>"
            card_html += f"<div style='display: flex; align-items: center; gap: 6px;'>"
            card_html += f"<span style='font-size: 10px; color: #0099B9;'>{t_ago}</span>"
            card_html += f"<span style='font-size: 12px;'>{c_dot}</span>"
            card_html += f"</div></div>"
            card_html += f"<div style='font-size: 11px; color: #444; word-wrap: break-word; margin-top: 4px;'>{c_out}</div>"
            card_html += f"</div>"
            if "Disk Space in Bytes" in c_desc or "get-all-disk-space" in c_name: full_width_html += card_html
            else: grid_html += card_html
                
    grid_html += "</div>"
    owners = data.get("owners", [])
    owners_html = f"<div style='border: 1px solid {overall_border}; border-radius: 6px; padding: 8px 12px; margin-bottom: 15px; font-family: sans-serif; font-size: 12px; background-color: {overall_bg};'><div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 5px;'><span style='font-weight: bold; font-size: 13px; color: #333;'>Contact Information</span></div>"
    owners_html += "<table style='width: 100%; border-collapse: collapse; font-size: 11px; margin-top: 5px;'><tr><th style='border-bottom: 1px solid #eee; padding: 4px; text-align: left; color: #555;'>Name</th><th style='border-bottom: 1px solid #eee; padding: 4px; text-align: left; color: #555;'>Email</th><th style='border-bottom: 1px solid #eee; padding: 4px; text-align: left; color: #555;'>Responsibility</th></tr>"
    for o in owners:
        resp_for = "<br>".join(o.get("responsible_for", []))
        owners_html += f"<tr><td style='border-bottom: 1px solid #eee; padding: 4px;'>{o.get('name','')}</td><td style='border-bottom: 1px solid #eee; padding: 4px;'>{o.get('email','')}</td><td style='border-bottom: 1px solid #eee; padding: 4px;'>{resp_for}</td></tr>"
    owners_html += "</table></div>"
    
    st.markdown(html + procmon_html + owners_html + grid_html + full_width_html, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("Close Diagnostics", use_container_width=True):
        st.session_state.active_node = None
        st.rerun()

@st.fragment(run_every=10)
def live_dashboard_fragment(sound_enabled):
    process_auto_posts()
    cluster_data = st.session_state.get('last_cluster_data', {})
    batch_data = st.session_state.get('last_batch_data', [])
    dba_data = st.session_state.get('last_dba_data', [])
    email_data = st.session_state.get('cached_email_data', {})

    current_cluster_set = set()
    if "_error" not in cluster_data:
        for host, clusters in cluster_data.items():
            for abbrv, nodes in clusters.items():
                for node in nodes:
                    current_cluster_set.add((host, abbrv, node['id'], node['status']))

    current_batch_set = set(batch_data)

    current_dba_set = set()
    for issue in dba_data:
        norm_issue = re.sub(r'\b\d+\s*(?:second|sec|minute|min|hour|hr)(?:s|\(s\))?(?!\w)', '{TIME}', issue, flags=re.IGNORECASE)
        current_dba_set.add(norm_issue)

    current_email_set = set()
    for folder, info in email_data.items():
        for em in info["emails"]:
            if "Folder not found" not in em['subject'] and "Ensure Outlook" not in em['subject']:
                current_email_set.add(f"[{folder}] {em['subject']}")

    if 'initialized' not in st.session_state:
        st.session_state.prev_cluster = current_cluster_set
        st.session_state.prev_batch = current_batch_set
        st.session_state.prev_dba = current_dba_set
        st.session_state.prev_email = current_email_set
        st.session_state.initialized = True
    else:
        new_cluster = current_cluster_set - st.session_state.prev_cluster
        new_batch = current_batch_set - st.session_state.prev_batch
        new_dba = current_dba_set - st.session_state.prev_dba
        new_email = current_email_set - st.session_state.prev_email

        st.session_state.prev_cluster = current_cluster_set
        st.session_state.prev_batch = current_batch_set
        st.session_state.prev_dba = current_dba_set
        st.session_state.prev_email = current_email_set

        alert_messages = []
        if new_cluster:
            status_counts = {'1': 0, '-1': 0, '2': 0, 'other': 0}
            for item in new_cluster:
                status = item[3]
                if status in status_counts: status_counts[status] += 1
                else: status_counts['other'] += 1
            if status_counts['2'] > 0: alert_messages.append(f"Cluster: {status_counts['2']} Critical (Red)")
            if status_counts['-1'] > 0: alert_messages.append(f"Cluster: {status_counts['-1']} Stale (Pink)")
            if status_counts['1'] > 0: alert_messages.append(f"Cluster: {status_counts['1']} Warning (Yellow)")

        if new_batch: alert_messages.append(f"Batch: {len(new_batch)} New Alert(s)")
        if new_dba: alert_messages.append(f"DBA: {len(new_dba)} New Error(s)")
        if new_email:
            alert_messages.append("📧 New Emails:")
            for i, em in enumerate(new_email):
                if i < 3: alert_messages.append(f"  - {em}")
                elif i == 3:
                    alert_messages.append(f"  ...and {len(new_email) - 3} more.")
                    break

        if alert_messages and sound_enabled:
            summary_text = "\n".join(alert_messages)
            if len(summary_text) > 250:
                summary_text = summary_text[:247] + "..."
            try:
                notification.notify(title="🚨 New Alert Received", message=summary_text, app_name="Unified NOC Dashboard", timeout=10)
                for _ in range(3):
                    if winsound:
                        winsound.Beep(800, 300)
                    time.sleep(0.1)
            except Exception as e:
                print(f"Notification failed: {e}")
                
                
        # --- NEW: ALERT TIME TRACKER ---
        if 'alert_timestamps' not in st.session_state:
            st.session_state.alert_timestamps = {}
            
        # Record the time for any new alerts
        now = datetime.now()
        for alert in alert_messages:
            if alert not in st.session_state.alert_timestamps:
                st.session_state.alert_timestamps[alert] = now
                
        # Remove alerts that have been resolved
        for old_alert in list(st.session_state.alert_timestamps.keys()):
            if old_alert not in alert_messages:
                del st.session_state.alert_timestamps[old_alert]
                
        # Save active alerts for the AI to read
        st.session_state.active_alerts = alert_messages        
                
                

    main_col, email_col = st.columns([9, 1])

    with main_col:
        col1, col2, col3 = st.columns(3)

        with col1:
            st.markdown(f'''
                <div class="col-header-blue">
                    <span>Cluster Monitor</span>
                    <span class="header-links-small">
                        <a href="{URLS_CLUSTER_FRONTEND[0]}" target="_blank">[D4]</a>
                        <a href="{URLS_CLUSTER_FRONTEND[1]}" target="_blank">[D5]</a>
                    </span>
                </div>
            ''', unsafe_allow_html=True)
            with st.popover("📞 Cluster On-Call Details"):
                render_oncall_data(get_cluster_oncall())
            render_cluster_section(cluster_data)
            

        with col2:
            st.markdown(f'''
                <div class="col-header-blue">
                    <span>Batch System</span>
                    <span class="header-links-small">
                        <a href="{URLS_BATCH[0]}" target="_blank">[D2]</a>
                        <a href="{URLS_BATCH[1]}" target="_blank">[D4]</a>
                        <a href="{URLS_BATCH[2]}" target="_blank">[D5]</a>
                    </span>
                </div>
            ''', unsafe_allow_html=True)
            with st.popover("📞 Batch On-Call Details"):
                render_oncall_data(get_batch_oncall())
            render_batch_section(batch_data)
                

        with col3:
            st.markdown(f'''
                <div class="col-header-blue">
                    <span>NOC DBA Monitor</span>
                    <span class="header-links-small">
                        <a href="{URLS_DBA_FRONTEND[0]}" target="_blank">[D4]</a>
                        <a href="{URLS_DBA_FRONTEND[1]}" target="_blank">[D5]</a>
                    </span>
                </div>
            ''', unsafe_allow_html=True)
            dba_raw = get_dba_oncall()

            try:

                dba_tables = pd.read_html(
                    io.StringIO(dba_raw)
                )

                if dba_tables:

                    dba_df = dba_tables[0]


                    last_date = str(
                        dba_df.iloc[-1, 0]
                    )

                    check_roster_expiry(
                        "DBA",
                        last_date,
                        "dba_roster"
                    )

            except Exception as e:
                print(e)

            with st.popover(
                "📞 DBA On-Call Details"
            ):
                render_oncall_data(
                    dba_raw
                )
            render_dba_section(dba_data)

    with email_col:
        st.markdown("<div style='margin-top: 50px;'></div>", unsafe_allow_html=True)
        generate_email_draft(email_data)

    st.markdown(f"<div class='refresh-text'>🔄 Last updated at {datetime.now().strftime('%I:%M:%S %p')}. Auto-refreshing seamlessly...</div>", unsafe_allow_html=True)
    

    if not st.session_state.get('is_fetching', False):
        st.session_state.is_fetching = True
        def bg_task():
            try:
                perform_data_fetch()
            finally:
                st.session_state.is_fetching = False
        t = threading.Thread(target=bg_task)
        add_script_run_ctx(t)
        t.start()

def run_dashboard():
    if "active_node" not in st.session_state: st.session_state.active_node = None
    if "pending_post_text" not in st.session_state: st.session_state.pending_post_text = None
    if "pending_post_mentions" not in st.session_state: st.session_state.pending_post_mentions = None
    if "pending_post_image" not in st.session_state: st.session_state.pending_post_image = None
    if "pending_auto_posts" not in st.session_state: st.session_state.pending_auto_posts = {}
    if "posted_auto_alerts" not in st.session_state: st.session_state.posted_auto_alerts = set()
    st.session_state.setdefault("dba_alert_active", False)
    st.session_state.setdefault("dba_first_seen", None)
    st.session_state.setdefault( "dba_last_signature", None)
    st.session_state.setdefault("batch_first_seen", None)
    st.session_state.setdefault("batch_last_signature", None)
    st.session_state.setdefault("notifications", [])
    

    CONFLUENCE_TOKEN_EXPIRY = datetime.strptime(
        ATLASSIAN_TOKEN_EXPIRY,
        "%Y-%m-%d"
    ).date()

    days_left = (
        CONFLUENCE_TOKEN_EXPIRY
        - date.today()
    ).days

    
    if days_left <= 3:

        add_notification(
            "confluence_token",
            "critical",
            "Confluence Token Expiry",
            f"Token expires in {days_left} day(s)"
        )
    
    elif days_left <= 7:

        add_notification(
            "confluence_token",
            "warning",
            "Confluence Token Expiry",
            f"Token expires in {days_left} day(s)"
        )
        
    else:

        remove_notification(
            "confluence_token"
        )  

    if os.path.exists(
        "paging_incidents.json"
    ):

        with open(
            "paging_incidents.json",
            "r",
            encoding="utf-8"
        ) as f:

            incidents = json.load(f)
                      

        for incident in incidents:
                       

            try:
                

                sla_dt = datetime.strptime(
                    incident["sla"],
                    "%m/%d/%Y %I:%M:%S %p"
                )

                hours_left = (
                    sla_dt - datetime.now()
                ).total_seconds() / 3600

                notif_id = (
                    f"sla_{incident['incident']}"
                )

                if hours_left <= 48:

                    add_notification(
                        notif_id,
                        "warning",
                        "Paging Incident SLA",
                        (
                            f"Paging incident "
                            f"{incident['incident']} "
                            f"is expiring on "
                            f"{sla_dt:} , please create new one."
                            
                        )
                    )

                else:

                    remove_notification(
                        notif_id
                    )

            except Exception as e:

                print(
                    "SLA NOTIFICATION ERROR:",
                    e
                )    

    if 'first_load_done' not in st.session_state:
        with st.spinner("Initializing Dashboard Data..."):
            perform_data_fetch()

        st.session_state.first_load_done = True
        st.session_state.is_fetching = False

        if 'smartit_launched' not in st.session_state:

            import subprocess

            EDGE_PATH = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

            subprocess.Popen([
                EDGE_PATH,
                "--remote-debugging-port=9222",
                "--user-data-dir=C:\\NOC_Profile",
                "--new-window",
                "https://transunion-smartit.onbmc.com"
            ])

            st.session_state.smartit_launched = True

    if "node" in st.query_params:
        st.session_state.active_node = st.query_params["node"]
          

    st.set_page_config(page_title="Unified SRG NOC", layout="wide")

    st.markdown("""
        <style>
            #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}
            .block-container {padding-top: 1rem; padding-bottom: 0rem;}
            *[data-stale="true"] { opacity: 1 !important; filter: none !important; transition: none !important; pointer-events: auto !important; }
            [data-testid="stFragment"] { opacity: 1 !important; transition: none !important; }
            div[role="dialog"] button[aria-label="Close"] { display: none !important; }
            .tu-main-header { background-color: #0099B9; padding: 8px 20px; border-radius: 6px; display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px;}
            .tu-logo { display: flex; align-items: center; }
            .tu-title { color: #FFD700; font-size: 22px; font-weight: bold; margin: 0; font-family: Arial, sans-serif; }
            a.header-link { text-decoration: none; }
            .col-header-blue { background-color: #008CBA; color: #FFD700; padding: 10px; font-weight: bold; font-size: 18px; border-radius: 4px 4px 0 0; display: flex; justify-content: space-between; align-items: center; transition: background-color 0.3s; }
            .col-header-blue:hover { background-color: #006b8f; cursor: pointer; }
            .header-links-small a { color: #FFD700; text-decoration: none; font-size: 14px; font-weight: normal; margin-left: 8px; }
            .header-links-small a:hover { text-decoration: underline; }
            div[data-testid="column"]:nth-child(4) button { background-color: transparent !important; border: none !important; box-shadow: none !important; font-size: 24px !important; padding: 0 !important; margin-top: -5px !important; color: #0099B9 !important; }
            div[data-testid="column"]:nth-child(4) button:hover { transform: scale(1.1); }
            div[data-testid="column"]:last-of-type button { background-color: transparent !important; border: none !important; box-shadow: none !important; padding: 5px 0px !important; font-size: 15px !important; font-weight: 600 !important; color: #333 !important; display: flex !important; justify-content: flex-end !important; margin-bottom: 2px !important; }
            div[data-testid="column"]:last-of-type button:hover { color: #0099B9 !important; background-color: transparent !important;}
            div[data-testid="stPopoverBody"] { width: max-content !important; max-width: 90vw !important; max-height: 60vh !important; overflow-y: scroll !important; overflow-x: hidden !important; padding: 15px; }
            .oncall-table { width: 100%; border-collapse: collapse; font-size: 13px; font-family: Arial, sans-serif; }
            .oncall-table th, .oncall-table td { border: 1px solid #ddd; padding: 8px 12px; text-align: left; white-space: nowrap; }
            .oncall-table th { background-color: #f4f4f4; color: #333; font-weight: bold; }
            .host-details { border: 1px solid #ddd; border-top: none; background-color: white; }
            .host-summary { padding: 8px 12px; cursor: pointer; font-size: 14px; font-weight: bold; color: #0099B9; background-color: #f8f9fa; display: flex; align-items: center; list-style: none; }
            .host-summary::-webkit-details-marker { display: none; }
            .host-summary:hover { background-color: #e9ecef; }
            .host-name-title { flex-grow: 1; }
            .host-badge { font-size: 11px; background: #dc3545; color: white; padding: 2px 8px; border-radius: 12px; font-weight: normal; }
            .clusters-wrapper { padding: 10px 12px; display: flex; flex-direction: column; gap: 8px; border-top: 1px solid #eee; }
            .cluster-row { display: flex; align-items: flex-start; flex-wrap: wrap; gap: 2px; }
            .cluster-abbrv { width: 30px; font-weight: bold; font-size: 12px; color: #333; margin-top: 4px; flex-shrink: 0; }
            .node-link { text-decoration: none; }
            .node-box { width: 18px; height: 24px; border: 1px solid #555; display: flex; align-items: center; justify-content: center; font-size: 10px; font-family: monospace; color: black; transition: transform 0.1s; }
            .node-box:hover { transform: scale(1.2); border: 2px solid black; cursor: pointer; z-index: 100; }
            .node-pink { background-color: #ffc0cb; }  
            .node-yellow { background-color: #ffeb3b; } 
            .node-red { background-color: #dc3545; color: white; } 
            .batch-error { color: #dc3545; text-align: center; font-size: 14px; margin-top: 5px; }
            .dba-error { color: red; font-weight: bold; font-size: 12px; font-family: monospace; margin-top: 8px; line-height: 1.4; }
            .email-item { border-bottom: 1px solid #eee; padding-bottom: 8px; margin-bottom: 8px; font-size: 13px; }
            .email-time { color: #6f42c1; font-weight: bold; font-size: 11px; }
            .all-clear { color: #28a745; font-weight: bold; text-align: center; padding: 20px; font-size: 16px; border: 1px solid #ddd; border-top: none; background-color: white; }
            .refresh-text { text-align: center; color: #888; font-size: 12px; margin-top: 30px; font-family: Arial, sans-serif; }
            .streamlit-expanderHeader { font-size: 14px !important; font-weight: bold !important; color: #0099B9 !important; }
            
            
        </style>
    """, unsafe_allow_html=True)

    col_head, col_devops, col_crisis, col_refresh, col_toggle = st.columns([4.5, 1.5, 1.5, 0.5, 1.5])
    
    with col_head:
        st.markdown(f"""
            <div class="tu-main-header">
                <div class="tu-logo">{get_transunion_html()}</div>
                <div class="tu-title">Unified SRG Dashboard</div>
            </div>
        """, unsafe_allow_html=True)
        
    with col_devops:

        devops_df = get_devops_oncall()

        if (
            isinstance(devops_df, pd.DataFrame)
            and not devops_df.empty
            and "End Date" in devops_df.columns
        ):

            last_end_date = (
                devops_df.iloc[-1]["End Date"]
            )

            check_roster_expiry(
                "DevOps",
                last_end_date,
                "devops_roster"
            )

        with st.popover(
            "📘 DevOps On-Call",
            use_container_width=True
        ):

            render_oncall_data(
                devops_df
            )
        with st.popover("🏢 Real Estate On-Call", use_container_width=True):
            render_oncall_data(get_real_estate_oncall())
        
    with col_crisis:
        with st.popover("🚨 NOC Crisis", use_container_width=True):
            st.markdown("##### Remedy Paging System")
            
            saved_token = get_saved_token()

            ticket_token = st.text_input(
                "Remedy Ticket Token:",
                value=saved_token
            )
            
            df_crisis = get_crisis_connect_data()
            remedy_groups = df_crisis["Remedy Group Names"].tolist()
            selected_group = st.selectbox("Select Team to Page:", remedy_groups)
            
            default_draft = (
                "Hi Team,\n\n"
                "We are seeing an issue, please check and assist."
            )

            if selected_group == "SRG Batch":

                raw_draft = st.session_state.get(
                    "batch_draft",
                    default_draft
                )

            elif selected_group == "SRG Database":

                raw_draft = st.session_state.get(
                    "dba_email_draft",
                    st.session_state.get(
                        "dba_dashboard_draft",
                        default_draft
                    )
                )

            elif selected_group in [
                "SRG Infra",
                "SRG Data"
            ]:

                raw_draft = st.session_state.get(
                    "cluster_draft",
                    default_draft
                )
                
            elif selected_group == "SRG Devops Support":

                raw_draft = st.session_state.get(
                    "devops_draft",
                    default_draft
                )

            else:

                raw_draft = default_draft
                
            clean_draft = raw_draft

            # remove ##### headers
            clean_draft = re.sub(
                r'^#+\s*.*?$',
                '',
                clean_draft,
                flags=re.MULTILINE
            )

            # remove bold markers
            clean_draft = clean_draft.replace("**", "")

            # replace greeting
            clean_draft = re.sub(
                r'Hi .*?Chat,',
                'Hi Team,',
                clean_draft,
                flags=re.IGNORECASE | re.DOTALL
            )

            # remove excess blank lines
            clean_draft = re.sub(
                r'\n{3,}',
                '\n\n',
                clean_draft
            ).strip()    
            
            
            page_text = st.text_area("Notification Text:", value=clean_draft, height=150)
            
            if st.button("🚀 Open Remedy & Page Team", type="primary"):

                st.toast(
                    "Launching Browser Automation...",
                    icon="🚀"
                )

                from noc_pager import automate_remedy_paging

                full_url = f"https://transunion-smartit.onbmc.com/smartit/app/#/incidentPV/{ticket_token}"

                success, msg = automate_remedy_paging(
                    selected_group,
                    page_text,
                    full_url
                )

                if success:
                    st.toast(msg, icon="✅")
                else:
                    st.toast(msg, icon="❌")
                        
        if st.button("🚀 Create New Incident", type="primary"):

            st.session_state["confirm_incident"] = True

        if st.session_state.get("confirm_incident", False):

            st.warning("Create a new Remedy ticket?")

            col1, col2 = st.columns(2)

            with col1:
                if st.button("✅ Yes"):

                        st.toast(
                            "Launching Browser Automation...",
                            icon="🚀"
                        )

                        from newincident import automate_incident_creation

                        success, msg = automate_incident_creation(
                            test_mode=False
                        )

                        if success:
                            st.toast(msg, icon="✅")
                        else:
                            st.toast(msg, icon="❌")

                        st.session_state["confirm_incident"] = False

            with col2:
                if st.button("❌ No"):

                    st.session_state["confirm_incident"] = False
                    st.rerun()
                                    
    with col_refresh:
        if st.button("🔄", help="Force Data Refresh"):
            with st.spinner("Force refreshing data..."):
                perform_data_fetch()
        
    with col_toggle:
        sound_enabled = st.toggle("🔊 Audio Alerts", value=True,
            help="Turn Off alert sound if not required.")
        auto_post_enabled = st.toggle("🤖 Auto Post Teams", value=False,
            help="When enabled, unresolved alerts will be auto-posted to Teams.")
            
        st.session_state["auto_post_enabled"] = (auto_post_enabled)

    if st.session_state.get("pending_post_text"):
        confirm_post_dialog(
            st.session_state.pending_post_text, 
            st.session_state.get("pending_post_mentions"),
            st.session_state.get("pending_post_image")
        )
    elif st.session_state.get("active_node"):
        show_node_details(st.session_state.active_node)
        
    live_dashboard_fragment(sound_enabled)
    
    # --- NATIVE FLOATING AI CHAT WIDGET ---
    from streamlit_float import float_init
    import streamlit.components.v1 as components
    
    float_init()
    chat_container = st.container()
    notification_container = st.container()
    
    with chat_container:
        # 1. AGGRESSIVE JAVASCRIPT: Runs every 1 second to guarantee it catches the button!
        js_code = """
        <script>
        function styleBotButton() {
            const buttons = window.parent.document.querySelectorAll('button');
            buttons.forEach(btn => {
                // Find the button that contains the robot emoji (but NOT the Send button)
                if(btn.innerText.includes('🤖') && !btn.innerText.includes('Assistant')) {
                    btn.style.borderRadius = '50%';
                    btn.style.width = '75px';
                    btn.style.height = '75px';
                    btn.style.backgroundColor = '#0099B9';
                    btn.style.border = 'none';
                    btn.style.boxShadow = '0 4px 12px rgba(0,0,0,0.4)';
                    
                    // Hide the dropdown arrow
                    const svg = btn.querySelector('svg');
                    if(svg) svg.style.display = 'none';
                    
                    // Make the emoji massive
                    const p = btn.querySelector('p');
                    if(p) {
                        p.style.fontSize = '40px';
                        p.style.margin = '0';
                        p.style.lineHeight = '1';
                    }
                    
                    // Hover effects
                    btn.onmouseover = function() {
                        this.style.backgroundColor = '#007a93';
                        this.style.transform = 'scale(1.1)';
                    }
                    btn.onmouseout = function() {
                        this.style.backgroundColor = '#0099B9';
                        this.style.transform = 'scale(1)';
                    }
                }
            });
        }
        // Run immediately, and keep running every 1 second to defeat Streamlit's loading delay!
        styleBotButton();
        setInterval(styleBotButton, 1000);
        </script>
        """
        components.html(js_code, height=0, width=0)
        
        
        # 2. The Popover Button
        with st.popover("🤖"):
            st.markdown('<div style="width: 450px; height: 1px;"></div>', unsafe_allow_html=True)
            st.markdown("#### 🤖 AURA Assistant")
            
            if "chat_history" not in st.session_state:
                st.session_state.chat_history = []
                
            history_box = st.container(height=400)
            with history_box:
                for msg in st.session_state.chat_history:
                    with st.chat_message(msg["role"]):
                        st.markdown(msg["content"])
            
            with st.form("chat_form", clear_on_submit=True, border=False):
                cols = st.columns([5, 1])
                with cols[0]:
                    user_input = st.text_input("Ask a question...", label_visibility="collapsed")
                with cols[1]:
                    submit = st.form_submit_button("Send", use_container_width=True)
                
                if submit and user_input:
                    st.session_state.chat_history.append({"role": "user", "content": user_input})
                    try:
                        from noc_ai import get_ai_response
                        active_alerts = st.session_state.get("active_alerts", [])
                        alert_timestamps = st.session_state.get("alert_timestamps", {})
                        response = get_ai_response(user_input, active_alerts, alert_timestamps)
                        st.session_state.chat_history.append({"role": "assistant", "content": response})
                        st.rerun()
                    except Exception as e:
                        st.error(f"Could not load AI module: {e}")
    
    # 3. Float the container in the bottom right corner
    chat_container.float("bottom: 9px; right: 7px; width: 75px; background-color: transparent;")    
                        
                        
    with notification_container:
        # 1. AGGRESSIVE JAVASCRIPT: Runs every 1 second to guarantee it catches the button!
        
        notification_count = len(
            st.session_state.get(
                "notifications",
                []
            )
        )
        
        js_code = f"""
        <script>

        function styleBellButton() {{

            const buttons =
                window.parent.document.querySelectorAll('button');

            buttons.forEach(btn => {{

                if (
                    btn.innerText.includes('🔔')
                    &&
                    !btn.innerText.includes('Assistant')
                ) {{

                    btn.style.background = 'transparent';
                    btn.style.border = 'none';
                    btn.style.boxShadow = 'none';
                    btn.style.width = 'auto';
                    btn.style.height = 'auto';
                    btn.style.padding = '0';
                    btn.style.position = 'relative';

                    const svg =
                        btn.querySelector('svg');

                    if(svg)
                        svg.style.display = 'none';

                    const p =
                        btn.querySelector('p');

                    if(p) {{
                        p.style.fontSize = '28px';
                        p.style.margin = '0';
                        p.style.lineHeight = '1';
                    }}

                    let badge =
                        btn.querySelector('.notif-badge');

                    if(!badge) {{

                        badge =
                            document.createElement('span');

                        badge.className =
                            'notif-badge';

                        btn.appendChild(badge);
                    }}

                    badge.innerText =
                        "{notification_count}";

                    badge.style.position = 'absolute';
                    badge.style.top = '-5px';
                    badge.style.right = '-5px';
                    badge.style.background = '#ff3b30';
                    badge.style.color = 'white';
                    badge.style.borderRadius = '50%';
                    badge.style.width = '22px';
                    badge.style.height = '22px';
                    badge.style.fontSize = '13px';
                    badge.style.fontWeight = 'bold';
                    badge.style.display = 'flex';
                    badge.style.alignItems = 'center';
                    badge.style.justifyContent = 'center';
                    badge.style.border = '2px solid white';

                    if ({notification_count} == 0) {{
                        badge.style.display = 'none';
                    }}
                }}
            }});
        }}

        styleBellButton();

        setInterval(
            styleBellButton,
            1000
        );

        </script>
        """
        components.html(js_code, height=0, width=0) 
                        
        
        with st.popover("🔔"):

            st.markdown(
                """
                <div style="
                    width:420px;
                    max-height:500px;
                    overflow-y:auto;
                ">
                """,
                unsafe_allow_html=True
            )

            notifications = st.session_state.get(
                "notifications",
                []
            )
            

            if not notifications:

                st.info(
                    "No notifications"
                )

            else:

                for notif in notifications:

                    severity = notif.get(
                        "severity",
                        "info"
                    )

                    if severity == "critical":

                        icon = "🚨"

                    elif severity == "warning":

                        icon = "⚠️"

                    else:

                        icon = "ℹ️"

                    st.markdown(
                        f"**{icon} {notif['title']}**"
                    )

                    st.write(
                        notif["message"]
                    )

                    st.caption(
                        notif["created"]
                    )

                    st.divider()

            st.markdown(
                "</div>",
                unsafe_allow_html=True
            )
               
    notification_container.float("top: 15px; right: 7px; width: 75px; background-color: transparent;")                
