#noc_teams.py

from config import *
from noc_tags import *
#from noc_ui import *
from noc_data import *
from noc_pager import *
import streamlit as st
import time
from datetime import datetime
import base64
import os
import urllib.parse
import requests
import re
import threading
from plyer import notification
import pandas as pd
from bs4 import BeautifulSoup
from streamlit.runtime.scriptrunner import add_script_run_ctx
import io
from config import TARGET_OUTLOOK_FOLDERS
import asyncio
import sys

def get_sad_face_html():
    for ext in ['jpg', 'png', 'jpeg']:
        filepath = f"sad_face.{ext}"
        if os.path.exists(filepath):
            with open(filepath, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
                return f'<div style="text-align: center; margin: 15px 0;"><img src="data:image/{ext};base64,{b64}" width="120"></div>'
    return '<div style="text-align: center; font-size: 80px; margin: 10px 0;">😡</div>'

def get_sad_face_base64():
    for ext in ['jpg', 'png', 'jpeg']:
        filepath = f"sad_face.{ext}"
        if os.path.exists(filepath):
            with open(filepath, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
                return f"data:image/{ext};base64,{b64}"
    return None

def get_transunion_html():
    for ext in ['jpg', 'png', 'jpeg']:
        filepath = f"transunion.{ext}"
        if os.path.exists(filepath):
            with open(filepath, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
                return f'<img src="data:image/{ext};base64,{b64}" width="140" style="display: block;">'
    return '<span style="font-size: 24px; font-weight: bold; color: white;">TU</span>'

def get_happy_face_html():
    for ext in ['jpg', 'png', 'jpeg']:
        filepath = f"happy_face.{ext}"
        if os.path.exists(filepath):
            with open(filepath, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
                return f'<div style="text-align: center; margin-bottom: 15px;"><img src="data:image/{ext};base64,{b64}" width="100"></div>'
    return '<div style="text-align: center; font-size: 70px; margin-bottom: 10px;">😃</div>'
    
def classify_dba_issue(issue):

    issue_lower = issue.lower()

    if (
        "select coalesce(lower(conv(bit_xor(cast(crc32(concat_ws("
        in issue_lower
    ):
        return "IGNORE"

    if (
        "replication lag" in issue_lower
        or "slow query" in issue_lower
    ):
        return "LONG_WAIT"

    return "CRITICAL"
    
def register_auto_post(
    alert_key,
    draft_text,
    mentions,
    delay_seconds=300
):

    print(
        "REGISTER_AUTO_POST:",
        alert_key
    )

    print(
        "POSTED AUTO ALERTS:",
        st.session_state.get(
            "posted_auto_alerts",
            set()
        )
    )

    if alert_key in st.session_state.get(
        "posted_auto_alerts",
        set()
    ):
        print(
            "ALREADY POSTED:",
            alert_key
        )
        return

    pending = st.session_state.get(
        "pending_auto_posts",
        {}
    )

    print(
        "PENDING BEFORE:",
        pending
    )

    if alert_key in pending:

        print(
            "ALREADY PENDING:",
            alert_key
        )

        return

    pending[alert_key] = {
        "created": time.time(),
        "draft_text": draft_text,
        "mentions": mentions,
        "delay": delay_seconds,
        "posted": False
    }

    st.session_state[
        "pending_auto_posts"
    ] = pending
    
    st.session_state.setdefault(
        "dba_alert_active",
        False
    )

    st.session_state.setdefault(
        "dba_first_seen",
        None
    )

    print(
        "REGISTERED:",
        alert_key
    )

    print(
        "PENDING AFTER:",
        pending
    )

def render_cluster_section(cluster_data):

    if "_error" in cluster_data:

        st.error(cluster_data["_error"])
        return

    if not cluster_data:

        st.markdown(
            f'<div class="all-clear">{get_happy_face_html()}✔️ All Hosts Green</div>',
            unsafe_allow_html=True
        )

        return

    html = ""
    draft_nodes = []

    for host, clusters in cluster_data.items():

        total_nodes = sum(
            len(nodes)
            for nodes in clusters.values()
        )

        is_open = (
            ""
            if host.lower() in ["echo", "foxtrot"]
            else "open"
        )

        html += f'<details class="host-details" {is_open}>'
        html += (
            f'<summary class="host-summary">'
            f'<span class="host-name-title">🖥️ {host}</span>'
            f'<span class="host-badge">{total_nodes}</span>'
            f'</summary>'
        )
        html += '<div class="clusters-wrapper">'

        for abbrv, nodes in clusters.items():

            html += (
                f'<div class="cluster-row">'
                f'<div class="cluster-abbrv">{abbrv}</div>'
            )

            for node in nodes:

                status = node["status"]
                hostname = node.get("hostname", "")

                if not is_ignored_for_draft(
                    host,
                    abbrv,
                    node["id"]
                ):

                    node_name = (
                        hostname
                        if hostname
                        else abbrv + node["id"]
                    )

                    alerts = []

                    if hostname and status in ["1", "2", "-1"]:
                        alerts = get_cluster_node_alerts(hostname)

                    if alerts:

                        draft_nodes.append(
                            f"{host} - {node_name} | "
                            + "\n".join(alerts)
                        )

                    else:

                        draft_nodes.append(
                            f"{host} - {node_name}"
                        )

                if status == "1":
                    color_class = "node-yellow"

                elif status == "-1":
                    color_class = "node-pink"

                elif status == "2":
                    color_class = "node-red"

                else:
                    color_class = "node-pink"

                if hostname: html += f'<a href="?node={hostname}" target="_self" class="node-link"><div class="node-box {color_class}">{node["id"]}</div></a>'
                else: html += f'<div class="node-box {color_class}">{node["id"]}</div>'
                

            html += "</div>"

        html += "</div></details>"
        

    st.markdown(
        html,
        unsafe_allow_html=True
    )

    if not draft_nodes:
        return

    with st.expander("📝 Draft Teams Message"):

        mentions = get_smart_mentions("cluster")

        names_str = ", ".join(
            [m["name"] for m in mentions]
        )

        greeting = (
            f"Hi Team, {names_str}, Public SRG_IT Chat,"
            if names_str
            else "Hi Team, Public SRG_IT Chat,"
        )

        nodes_str = "\n".join(
            [f"**{node}**" for node in draft_nodes]
        )

        draft_text = (
            f"##### Cluster issue\n\n"
            f"{greeting}\n\n"
            f"We are seeing issues for below nodes, "
            f"could you please check and assist?\n\n"
            f"{nodes_str}\n"
        )

        st.session_state["cluster_draft"] = draft_text

        st.code(
            draft_text,
            language="markdown"
        )

        edited_text = st.text_area(
            "Edit before posting to Teams:",
            value=draft_text,
            height=150,
            key="ta_cluster"
        )

        if st.button(
            "🚀 Post to Teams",
            key="btn_cluster"
        ):

            st.session_state.pending_post_text = edited_text

            st.session_state.pending_post_mentions = mentions

            st.rerun()


def render_batch_section(batch_data):

    if not batch_data:

        st.session_state[
            "batch_first_seen"
        ] = None

        st.session_state[
            "batch_last_signature"
        ] = None

        # Remove only batch entries from posted history
        posted = st.session_state.get(
            "posted_auto_alerts",
            set()
        )

        posted = {
            p for p in posted
            if not p.startswith("batch_")
        }

        st.session_state[
            "posted_auto_alerts"
        ] = posted

        st.markdown(
            f'<div class="all-clear">{get_happy_face_html()}✔️ All Batch Servers Are Active</div>',
            unsafe_allow_html=True
        )

        return
        
    batch_delay = 900

    for issue in batch_data:

        if "Active SRG" in issue:

            batch_delay = 420

            break

    now = time.time()

    if not st.session_state.get(
        "batch_first_seen"
    ):

        st.session_state[
            "batch_first_seen"
        ] = now

    batch_age = (
        now
        - st.session_state[
            "batch_first_seen"
        ]
    )

    batch_should_post = (
        batch_age >= batch_delay
    )
                
    batch_alert_key = (
        get_batch_signature_key(
            batch_data
        )
    )

    print(
        "BATCH AGE:",
         batch_age
    )

    print(
         "BATCH DELAY:",
         batch_delay
    )

    print(
        "BATCH SHOULD POST:",
         batch_should_post
    )            
                        
    html = (
        '<div style="border: 1px solid #ddd; '
        'border-top: none; padding: 10px; '
        'background-color: white;">'
    )

    html += get_sad_face_html()

    for issue in batch_data:

        html += (
            f'<div class="batch-error">'
            f'{issue}'
            f'</div>'
        )

    html += '</div>'

    st.markdown(
        html,
        unsafe_allow_html=True
    )

    with st.expander("📝 Draft Teams Message"):

        mentions = get_smart_mentions("batch")

        names_str = ", ".join(
            [m["name"] for m in mentions]
        )

        greeting = (
            f"Hi Batch Team, {names_str}, Public SRG_IT Chat,"
            if names_str
            else "Hi Batch Team, Public SRG_IT Chat,"
        )

        issues_str = "\n".join(
            [f"**{issue}**" for issue in batch_data]
        )

        draft_text = (
            f"##### Batch service issue\n\n"
            f"{greeting}\n\n"
            f"We are seeing batch service issues, "
            f"please check and assist.\n\n"
            f"{issues_str}\n"
        )
        
        if batch_should_post:

            register_auto_post(
                batch_alert_key,
                draft_text,
                mentions,
                delay_seconds=0
            )

            print(
                "REGISTERING BATCH:",
                batch_alert_key
            )

        st.session_state["batch_draft"] = draft_text

        st.code(
            draft_text,
            language="markdown"
        )

        edited_text = st.text_area(
            "Edit before posting to Teams:",
            value=draft_text,
            height=150,
            key="ta_batch"
        )

        if st.button(
            "🚀 Post to Teams",
            key="btn_batch"
        ):

            st.session_state.pending_post_text = edited_text

            st.session_state.pending_post_mentions = mentions

            st.session_state.pending_post_image = (
                get_sad_face_base64()
            )

            st.rerun()


def render_dba_section(dba_data):

    if not dba_data:

        st.markdown(
            f'<div class="all-clear">{get_happy_face_html()}✔️ No Database Errors</div>',
            unsafe_allow_html=True
        )

        return
    
    filtered_dba = []

    replication_alerts = []

    critical_alerts = []

    for issue in dba_data:

        alert_type = classify_dba_issue(
            issue
        )

        if alert_type == "IGNORE":

            print(
                "IGNORING DBA ALERT:",
                issue
            )

            continue

        filtered_dba.append(
            issue
        )

        if alert_type == "LONG_WAIT":

            replication_alerts.append(
                issue
            )

        else:

            critical_alerts.append(
                issue
            )

    dba_data = filtered_dba

    # Dashboard green
    if not dba_data:

        st.session_state[
            "dba_alert_active"
        ] = False

        st.session_state[
            "dba_first_seen"
        ] = None

        print(
            "DBA ALERT RESET"
        )

        st.markdown(
            f'<div class="all-clear">{get_happy_face_html()}✔️ No Database Errors</div>',
            unsafe_allow_html=True
        )

        return

    delay_seconds = 3600

    if critical_alerts:

        delay_seconds = 600

        print(
            "DBA ESCALATED TO 10 MIN"
        )

    now = time.time()

    if not st.session_state.get(
        "dba_first_seen"
    ):

        st.session_state[
            "dba_first_seen"
        ] = now

    age_seconds = (
        now
        - st.session_state[
            "dba_first_seen"
        ]
    )

    should_post = False

    if critical_alerts:

        should_post = (
            age_seconds >= 600
        )

    else:

        for issue in replication_alerts:

            issue_lower = issue.lower()

            # Replication Lag
            if "replication lag" in issue_lower:

                hour_match = re.search(
                    r':\s*(\d+)\s*hour\(s\)',
                    issue_lower
                )

                if (
                    hour_match
                    and int(hour_match.group(1)) >= 1
                ):

                    should_post = True

                    print(
                        "DBA REPLICATION READY:",
                        issue
                    )

                    break

            # Slow Query
            elif "slow query" in issue_lower:

                sec_match = re.search(
                    r'executed for\s+(\d+)\s+seconds',
                    issue_lower
                )

                if sec_match:

                    seconds = int(
                        sec_match.group(1)
                    )

                    if seconds >= 3600:

                        should_post = True

                        print(
                            "DBA SLOW QUERY READY:",
                            issue
                        )

                        break

    print(
        "DBA SHOULD POST:",
        should_post
    )

    print(
        "DBA AGE:",
        age_seconds
    )

    print(
        "DBA DELAY:",
        delay_seconds
    )    
                        
    dba_alert_key = (
        get_dba_signature_key(
            dba_data
        )
    ) 

    st.session_state[
        "dba_last_signature"
    ] = dba_alert_key    

    html = (
        '<div style="border: 1px solid #ddd; '
        'border-top: none; padding: 10px; '
        'background-color: white;">'
    )

    html += get_sad_face_html()

    for issue in dba_data:

        display_issue = (
            issue
            if len(issue) <= 500
            else issue[:500] + "..."
        )

        html += (
            f'<div class="dba-error">'
            f'{display_issue}'
            f'</div>'
        )

    html += '</div>'

    st.markdown(
        html,
        unsafe_allow_html=True
    )
    
    if st.session_state.get(
        "dba_alert_active",
        False
    ):

        print(
            "DBA ALERT ALREADY ACTIVE"
        )

        return

    with st.expander("📝 Draft Teams Message"):

        mentions = get_smart_mentions("dba")

        names_str = ", ".join(
            [m["name"] for m in mentions]
        )

        greeting = (
            f"Hi DBA Team, {names_str}, Public SRG_IT Chat,"
            if names_str
            else "Hi DBA Team, Public SRG_IT Chat,"
        )

        truncated_dba = []

        for issue in dba_data:

            clean_issue = re.sub(
                r"\s+",
                " ",
                issue
            ).strip()

            if len(clean_issue) > 250:
                clean_issue = clean_issue[:250] + "..."

            truncated_dba.append(
                f"- {clean_issue}"
            )

        issues_str = "\n".join(truncated_dba)

        draft_text = (
            f"##### DBMon - Alert\n\n"
            f"{greeting}\n\n"
            f"We can see the following errors on DBMon. "
            f"Please check and suggest on this!\n\n"
            f"{issues_str}\n"
        )
        
        if should_post:

            register_auto_post(
                dba_alert_key,
                draft_text,
                mentions,
                delay_seconds=0
            )

            print(
                "REGISTERING DBA:",
                dba_alert_key
            )

        st.session_state[
            "dba_dashboard_draft"
        ] = draft_text

        st.code(
            draft_text,
            language="markdown"
        )

        dynamic_key = (
            f"ta_dba_{len(dba_data)}"
        )

        edited_text = st.text_area(
            "Edit before posting to Teams:",
            value=draft_text,
            height=250,
            key=dynamic_key
        )

        if st.button(
            "🚀 Post to Teams",
            key="btn_dba"
        ):
            st.session_state[
                "pending_post_text"
            ] = edited_text

            st.session_state[
                "pending_post_mentions"
            ] = mentions

            st.rerun()
            
def register_bucket(
    bucket_name,
    draft_text,
    mentions,
    delay
):
    register_auto_post(
        bucket_name,
        draft_text,
        mentions,
        delay
    )
    
def get_batch_signature_key(
    batch_data
):

    active_signature = tuple(
        sorted(batch_data)
    )

    return (
        "batch_"
        + str(
            hash(
                active_signature
            )
        )
    )
    
def get_dba_signature_key(
    dba_data
):

    active_signature = tuple(
        sorted(dba_data)
    )

    return (
        "dba_"
        + str(
            hash(
                active_signature
            )
        )
    )
    
def get_alert_signature_key(
    prefix,
    draft_subjects
):

    active_signature = tuple(
        sorted(
            draft_subjects
        )
    )

    return (
        f"{prefix}_"
        f"{hash(active_signature)}"
    )

def generate_email_draft(email_data):
    auto_post_folders = [
        "PMASS",
        "Code Blue",
        "Zabbix alerts",
        "Remedy SRG"
    ]

    total_email_count = sum(
        email_data.get(folder, {}).get("count", 0)
        for folder in auto_post_folders
    )
    
    print(
        "TOTAL EMAIL COUNT:",
        total_email_count
    )

    pending = st.session_state.get(
        "pending_auto_posts",
        {}
    )

    if (
        total_email_count == 0
        and not pending
    ):

        clear_auto_post_cache()
        
    for folder_name in TARGET_OUTLOOK_FOLDERS:
            folder_info = email_data.get(folder_name, {"count": 0, "emails": []})
            count = folder_info["count"]
            emails = folder_info["emails"]
            
            if count > 0 and emails and ("Folder not found" in emails[0]["subject"] or "Ensure Outlook" in emails[0]["subject"]):
                with st.popover(f"📁 {folder_name} (⚠️)", use_container_width=True):
                    st.error(emails[0]["subject"])
            else:
                btn_label = f"📂 {folder_name} 🔴 {count}" if count > 0 else f"📁 {folder_name}"
                with st.popover(btn_label, use_container_width=True):
                    if count == 0: 
                        st.markdown('<div style="color: #28a745; font-weight: bold; padding: 10px; text-align: center;">✔️ No unread emails</div>', unsafe_allow_html=True)
                    else:
                        draft_subjects = []
                        draft_type = None
                        pmass_hosts = []
                        real_estate_flag = False
                        
                        latest_pmass_state = {}
                        latest_zabbix_state = {}
                        
                        print(
                            "PMASS STATE TABLE:",
                            latest_pmass_state
                        )

                        for em in emails:

                            subj = em["subject"]

                            host_match = re.search(
                                r'\[(FIRING|RESOLVED)\]\s+([^\s]+)',
                                subj
                            )

                            if not host_match:
                                continue

                            state = host_match.group(1)

                            host = host_match.group(2).strip().lower()

                            # Keep newest state only
                            if host not in latest_pmass_state:

                                latest_pmass_state[host] = state
                                
                        for em in emails:

                            subj = em["subject"]

                            host_match = re.search(
                                r'-\s*([a-zA-Z0-9.-]+)$',
                                subj
                            )

                            if not host_match:
                                continue

                            host = (
                                host_match.group(1)
                                .strip()
                                .lower()
                            )

                            if "Problem:" in subj:

                                if host not in latest_zabbix_state:

                                    latest_zabbix_state[host] = "PROBLEM"

                            elif "Resolved" in subj:

                                if host not in latest_zabbix_state:

                                    latest_zabbix_state[host] = "RESOLVED"
                                                
                        for em in emails: 
                            st.markdown(f"<div class='email-item'><div class='email-time'>{em['time']}</div>{em['subject']}</div>", unsafe_allow_html=True)
                            
                            subj = em['subject']
                            if folder_name == "PMASS" and "[RESOLVED]" in subj:

                                host_match = re.search(
                                    r'\[RESOLVED\]\s+([^\s]+)',
                                    subj
                                )

                                if host_match:

                                    pending = st.session_state.get(
                                        "pending_auto_posts",
                                        {}
                                    )

                                    st.session_state[
                                        "pending_auto_posts"
                                    ] = pending

                                    continue       
    
                            if folder_name == "PMASS" and "[FIRING]" in subj:
                                
                                subject_after_firing = re.sub(
                                    r'^\[FIRING\]\s*',
                                    '',
                                    subj,
                                    flags=re.IGNORECASE
                                ).strip()

                                if (
                                    subject_after_firing.lower()
                                    == "unisonservice-status"
                                    or (
                                        "unisonservice-status" in subj.lower()
                                        and "packer" in subj.lower()
                                    )
                                ):

                                    print(
                                        "IGNORING PMASS ALERT:",
                                        subj
                                    )

                                    continue

                                host_match = re.search(
                                    r'\[FIRING\]\s+([^\s]+)',
                                    subj
                                )

                                if not host_match:
                                    continue

                                host = host_match.group(1).strip().lower()

                                if latest_pmass_state.get(host) != "FIRING":
                                    
                                    print(
                                        "PMASS CHECK:",
                                        host,
                                        latest_pmass_state.get(host)
                                    )

                                    continue

                                draft_type = "PMass"

                                if host not in pmass_hosts:
                                    pmass_hosts.append(host)

                                if str(subj).strip() not in draft_subjects:
                                    draft_subjects.append(
                                        str(subj).strip()
                                    )
                                    
                            elif (
                                folder_name == "Code Blue"
                                and "CLR:" in subj
                            ):

                                ticket_match = re.search(
                                    r'#(\d+)',
                                    subj
                                )

                                if ticket_match:

                                    remove_auto_post(
                                        "codeblue_bucket"
                                    )

                                continue
                                    
                            elif folder_name == "Code Blue" and "NEW: FAIL" in subj:
                                draft_type = "Code Blue"
                                draft_subjects.append(str(subj).strip())
                                if "Real Estate" in subj:
                                    real_estate_flag = True
                                    
                            elif (
                                folder_name == "Zabbix alerts"
                                and "Resolved" in subj
                            ):

                                pending = st.session_state.get(
                                    "pending_auto_posts",
                                    {}
                                )

                                st.session_state[
                                    "pending_auto_posts"
                                ] = pending

                                print(
                                    "ZABBIX RESOLVED:",
                                    subj
                                )

                                continue        
                                    
                            elif (
                                folder_name == "Zabbix alerts"
                                and "Problem:" in subj
                            ):

                                host_match = re.search(
                                    r'-\s*([a-zA-Z0-9.-]+)$',
                                    subj
                                )

                                if not host_match:
                                    continue

                                zabbix_host = (
                                    host_match.group(1)
                                    .strip()
                                    .lower()
                                )

                                if latest_zabbix_state.get(
                                    zabbix_host
                                ) != "PROBLEM":
  
                                    continue

                                print(
                                    "ACTIVE ZABBIX:",
                                    zabbix_host
                                )

                                draft_type = "Zabbix"
                                
                                if (
                                    "mysql: service is down"
                                    in subj.lower()
                                ):
                                    draft_type = "Zabbix_DBA"

                                if str(subj).strip() not in draft_subjects:

                                    draft_subjects.append(
                                        str(subj).strip()
                                    )
                                    
                            elif (
                                folder_name == "Remedy SRG" and "Automatic 1st Response Ticket Escalation" in subj
                            ):

                             
                                continue
                                
                            elif (
                                folder_name == "Remedy SRG" and "SRG_NOC_Support_Incident- For paging teams" in subj
                            ):
                            
                                continue

                                
                            elif folder_name == "Remedy SRG" and "NEW: FAIL" not in subj:
                                if "Memory Warning" in subj:
                                    draft_type = "Remedy_DBA"
                                else:
                                    draft_type = "Remedy"
                                    
                                inc_match = re.search(r'(INC\d+)', subj)
                                desc_match = re.search(r'Description:\s*(.*)', subj, re.IGNORECASE)
                                inc_num = inc_match.group(1) if inc_match else "INC_UNKNOWN"
                                desc_text = desc_match.group(1).strip() if desc_match else subj
                                draft_subjects.append(f"{inc_num}- {desc_text}")      
                        

                        # PMASS
                        if (
                            folder_name == "PMASS"
                            and not draft_subjects
                        ):

                            st.session_state[
                                "current_pmass_draft_subjects"
                            ] = []

                        # ZABBIX
                        if (
                            folder_name == "Zabbix alerts"
                            and not draft_subjects
                        ):

                            st.session_state[
                                "current_zabbix_draft_subjects"
                            ] = []                      
                                
                        if draft_subjects:
                            if draft_type == "PMass":
                                mentions = get_smart_mentions("pmass", extra_data=pmass_hosts)
                            elif draft_type in ["Remedy_DBA" , "Zabbix_DBA"]:
                                mentions = get_smart_mentions("dba")                                
                            elif draft_type == "Remedy":
                                mentions = get_smart_mentions("devops")
                            else:
                                mentions = get_smart_mentions("devops")
                                if draft_type == "Code Blue" and real_estate_flag:
                                    re_mentions = get_smart_mentions("real_estate")
                                    existing_emails = [m['email'] for m in mentions]
                                    for rm in re_mentions:
                                        if rm['email'] not in existing_emails:
                                            mentions.append(rm)
                                
                            with st.expander("📝 Draft Teams Message"):
                                names_str = ", ".join([m['name'] for m in mentions])
                                greeting = f"Hi Team, {names_str}, Public SRG_IT Chat," if names_str else "Hi Team, Public SRG_IT Chat,"
                                
                                if draft_type in ["Remedy", "Remedy_DBA"]:
                                    subjects_str = "\n".join([f"**{subj}**" for subj in draft_subjects])
                                    if len(draft_subjects) > 1:
                                        title = "Multiple Remedy Tickets"
                                        intro = "We have received the below tickets can you check and suggest on this !"
                                    else:
                                        title = draft_subjects[0].split('- ', 1)[-1].split('(')[0].strip() if '- ' in draft_subjects[0] else "Remedy Ticket"
                                        intro = "We have received the below ticket can you check and suggest on this !"
                                else:
                                    subjects_str = "\n".join([f"**{str(subj).strip()}**" for subj in draft_subjects])
                                    if len(draft_subjects) > 1:
                                        title = f"Multiple {draft_type} alerts"
                                        intro = f"We have received multiple {draft_type} alerts, please check and assist."
                                    else:
                                        title = f"{draft_type} Alert"
                                        intro = f"We are seeing below {draft_type} alert, please have a look."
                                    
                                draft_text = f"##### {title}\n\n{greeting}\n\n{intro}\n\n{subjects_str}\n\n"
                                print(
                                    f"FINAL {draft_type}:",
                                    len(draft_subjects)
                                )
                                            
                                if draft_type == "PMass":
                                    
                                    st.session_state[
                                        "current_pmass_draft_subjects"
                                    ] = draft_subjects.copy()

                                    if not pmass_hosts:
                                        continue


                                    alert_key = get_alert_signature_key(
                                        "pmass",
                                        draft_subjects
                                    )
                                    
                                    pending = st.session_state.get(
                                        "pending_auto_posts",
                                        {}
                                    )

                                    for k in list(pending.keys()):

                                        if (
                                            k.startswith("pmass_")
                                            and k != alert_key
                                        ):

                                            pending.pop(k, None)

                                            print(
                                                "REMOVED OLD PMASS KEY:",
                                                k
                                            )

                                    st.session_state[
                                        "pending_auto_posts"
                                    ] = pending

                                    register_auto_post(
                                        alert_key,
                                        draft_text,
                                        mentions,
                                        delay_seconds=360
                                    )

                                
                                if draft_type == "Code Blue":

                                    alert_key = get_alert_signature_key(
                                        "codeblue",
                                        draft_subjects
                                    )

                                    register_auto_post(
                                        alert_key,
                                        draft_text,
                                        mentions,
                                        delay_seconds=130
                                    )
                                
                                if draft_type == "Zabbix":
                                    
                                    st.session_state[
                                        "current_zabbix_draft_subjects"
                                    ] = draft_subjects.copy()
                                    

                                    alert_key = get_alert_signature_key(
                                        "zabbix",
                                        draft_subjects
                                    )
                                    
                                    pending = st.session_state.get(
                                        "pending_auto_posts",
                                        {}
                                    )

                                    for k in list(pending.keys()):

                                        if (
                                            k.startswith("zabbix_")
                                            and k != alert_key
                                        ):

                                            pending.pop(k, None)

                                            print(
                                                "REMOVED OLD ZABBIX KEY:",
                                                k
                                            )

                                    st.session_state[
                                        "pending_auto_posts"
                                    ] = pending

                                    register_auto_post(
                                        alert_key,
                                        draft_text,
                                        mentions,
                                        delay_seconds=360
                                    )
                                
                                if draft_type in [
                                    "Remedy",
                                    "Remedy_DBA"
                                ]:

                                    alert_key = get_alert_signature_key(
                                        "remedy",
                                        draft_subjects
                                    )

                                    register_auto_post(
                                        alert_key,
                                        draft_text,
                                        mentions,
                                        delay_seconds=60
                                    )
                                    
                                if draft_type == "Remedy_DBA":

                                    st.session_state["dba_email_draft"] = draft_text

                                elif draft_type in [
                                    "PMass",
                                    "Code Blue",
                                    "Zabbix",
                                    "Remedy"
                                ]:

                                    st.session_state["devops_draft"] = draft_text
                                st.code(draft_text, language="markdown")
                                edited_text = st.text_area("Edit before posting to Teams:", value=draft_text, height=100, key=f"ta_email_{folder_name}")
                                if st.button("🚀 Post to Teams", key=f"btn_email_{folder_name}"):
                                    st.session_state.pending_post_text = edited_text
                                    st.session_state.pending_post_mentions = mentions
                                    st.rerun()
                                    
                        if count > len(emails): 
                            st.markdown(f"<div style='text-align: center; font-size: 12px; color: #666; margin-top: 5px;'>...and {count - len(emails)} more</div>", unsafe_allow_html=True)
                            
                            
def remove_auto_post(alert_key):

    pending = st.session_state.get(
        "pending_auto_posts",
        {}

    )

    pending.pop(alert_key, None)
    print(
        "REMOVING AUTO POST:",
        alert_key
    )

    st.session_state[
        "pending_auto_posts"
    ] = pending

         
                            
def process_auto_posts():
    
    print("PROCESS_AUTO_POSTS CALLED")

    if not st.session_state.get(
        "auto_post_enabled",
        False
    ):
        
        print(
            "AUTO POST ENABLED:",
            st.session_state.get(
                "auto_post_enabled",
                False
            )
        )
        return

    pending = st.session_state.get(
        "pending_auto_posts",
        {}
    )

    now = time.time()

    for key, item in list(
        pending.items()
    ):

        age = now - item["created"]

        if item["posted"]:
            continue

        if age < item["delay"]:
            continue
            
        current_pmass_draft = (
            st.session_state.get(
                "current_pmass_draft_subjects",
                []
            )
        )

        if key.startswith("pmass_"):

            current_drafts = st.session_state.get(
                "current_pmass_draft_subjects",
                []
            )

            current_key = get_alert_signature_key(
                "pmass",
                current_drafts
            )

            if key != current_key:

                print(
                    "SKIPPING STALE PMASS:",
                    key
                )

                del pending[key]

                continue

        if key.startswith("zabbix_"):

            current_drafts = st.session_state.get(
                "current_zabbix_draft_subjects",
                []
            )

            current_key = get_alert_signature_key(
                "zabbix",
                current_drafts
            )

            if key != current_key:

                print(
                    "SKIPPING STALE ZABBIX:",
                    key
                )

                del pending[key]

                continue

        success, msg = post_to_teams(
            item["draft_text"],
            item["mentions"]
        )
        print(
            "PENDING KEYS:",
            list(pending.keys())
        )

        if success:

            item["posted"] = True
            
            if key.startswith("dba_"):

                st.session_state[
                    "dba_alert_active"
                ] = True

                print(
                    "DBA ALERT NOW ACTIVE"
                )

            del pending[key]

            st.session_state[
                "posted_auto_alerts"
            ].add(key)
            
            print(
                "AUTO POST CHECK RUNNING"
            )
            
            print(
                "PENDING:",
                len(pending)
            )

            print(
                f"Auto posted: {key}"
            )
            
            
def clear_auto_post_cache():

    pending = st.session_state.get(
        "pending_auto_posts",
        {}
    )

    if pending:

        print(
            "CACHE CLEAR SKIPPED - PENDING ALERTS EXIST"
        )

        return

    st.session_state[
        "pending_auto_posts"
    ] = {}

    print(
        "AUTO POST CACHE CLEARED"
    )
    
  
