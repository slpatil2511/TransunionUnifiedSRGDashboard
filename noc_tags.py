#noc_tags.py

from config import *
from noc_data import *
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

def normalize_dba_roster():

    raw_data = get_dba_oncall()

    if isinstance(raw_data, str):
        tables = pd.read_html(io.StringIO(raw_data))
        df = tables[0]
    else:
        df = raw_data.copy()

    # Force column names
    df.columns = [
        "date",
        "day",
        "primary",
        "secondary",
        "timing",
        "contact_day",
        "contact_night"
    ]

    roster = []
    contacts = {}

    for _, row in df.iterrows():

        date_val = str(row["date"]).strip()

        # Skip header rows that sometimes appear inside Confluence tables
        if date_val.lower() == "date":
            continue

        roster.append(
            {
                "date": date_val,
                "primary": str(row["primary"]).strip(),
                "secondary": str(row["secondary"]).strip(),
                "timing": str(row["timing"]).strip()
            }
        )

        # DAY CONTACT
        day_contact = str(row["contact_day"])

        if day_contact.lower() != "nan":

            emails = re.findall(
                r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
                day_contact
            )

            if emails:

                name = (
                    day_contact
                    .split("Email")[0]
                    .replace("--", "")
                    .strip()
                )

                contacts[name] = emails[0]

        # NIGHT CONTACT
        night_contact = str(row["contact_night"])

        if night_contact.lower() != "nan":

            emails = re.findall(
                r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
                night_contact
            )

            if emails:

                name = (
                    night_contact
                    .split("Email")[0]
                    .replace("--", "")
                    .strip()
                )

                contacts[name] = emails[0]

    return roster, contacts

# --- NEW MENTION ENGINE ---
def get_smart_mentions(system, extra_data=None):
    mentions = []
    seen_emails = set()
    
    from datetime import datetime, timedelta
    import re

    def is_current_shift(shift_text):
        """
        Evaluates an IST shift string such as:

        8:00 AM - 2:00 PM
        2:00 PM - 8:00 PM
        8:00 PM - 8:00 AM
        """

        current_ist_hour = (
            datetime.utcnow()
            + timedelta(hours=5, minutes=30)
        ).hour
        
        
        #print(
        #    f"SHIFT={shift_text} "
         #   f"CURRENT_IST_HOUR={current_ist_hour}"
        #)
        shift_text = str(shift_text).strip()

        if shift_text.lower() in ["nan", "none", ""]:
            return False

        matches = re.findall(
            r'(\d{1,2})(?::\d{2})?\s*(am|pm)',
            shift_text.lower()
        )

        if len(matches) < 2:
            return False

        start_hour = int(matches[0][0])
        end_hour = int(matches[1][0])

        if matches[0][1] == "pm" and start_hour != 12:
            start_hour += 12

        if matches[0][1] == "am" and start_hour == 12:
            start_hour = 0

        if matches[1][1] == "pm" and end_hour != 12:
            end_hour += 12

        if matches[1][1] == "am" and end_hour == 12:
            end_hour = 0


        if start_hour <= end_hour:

            return (
                start_hour
                <= current_ist_hour
                < end_hour
            )

        return (
            current_ist_hour >= start_hour
            or current_ist_hour < end_hour
        )
    
    def get_active_dba_mentions():

        raw_data = get_dba_oncall()

        if isinstance(raw_data, str):
            tables = pd.read_html(io.StringIO(raw_data))
            df = tables[0]
            
            df.columns = [
                "date",
                "day",
                "ist_time",
                "primary_name",
                "primary_email",
                "secondary_name",
                "secondary_email",
                "est_time",
                "est_name",
                "est_email"
            ]
            

        else:
            df = raw_data.copy()

        current_ist = (
            datetime.utcnow()
            + timedelta(hours=5, minutes=30)
        )
        
        current_hour = current_ist.hour

        today_str = (
            str(current_ist.day)
            + "-"
            + current_ist.strftime("%b-%y")
        )
        

        row = df[
            df["date"].astype(str)
            .str.strip()
            .eq(today_str)
        ]

        if row.empty:

            return []

        row = row.iloc[0]


        current_hour = current_ist.hour

        mentions = []

        # IST shift
        if 8 <= current_hour < 20:

            mentions.append({
                "name": str(row["primary_name"]).strip(),
                "email": str(row["primary_email"]).strip()
            })

            mentions.append({
                "name": str(row["secondary_name"]).strip(),
                "email": str(row["secondary_email"]).strip()
            })

        # EST shift
        else:

            mentions.append({
                "name": str(row["est_name"]).strip(),
                "email": str(row["est_email"]).strip()
            })
            

        return mentions

    # locate today's row
    
    def add_mention(name, email):

        if not name or str(name).lower() in ['nan', 'none', '']:
            return

        clean_name = str(name).strip()

        if not email or str(email).lower() in ['nan', 'none', '']:
            email = f"{clean_name.replace(' ', '').replace(',', '')}@transunion.com"

        if email.lower() not in seen_emails:


            seen_emails.add(email.lower())

            mentions.append({
                "name": clean_name,
                "email": email.lower()
            })


    def get_host_prefix(hostname):
        return re.sub(
            r'-[a-z0-9]{4,5}$',
            '',
            str(hostname).strip()
        ).lower()
        
    def get_pmass_host_group(hostname):

        hostname = str(hostname).strip().lower()

        # Preserve existing behavior first
        hostname = get_host_prefix(hostname)

        match = re.match(
            r'^(.*?)(?:ap|bp|cp|dp|ep|fp|hp|ps|q)\d+$',
            hostname
        )

        if match:
            return match.group(1)

        return hostname


    try:
        # --- RULE 5: PMASS (Excel Mapping) ---
        if system == "pmass" and extra_data:
            try:
                df = load_pmass_mapping()
                
                print(df.head())

                print(
                    "PMASS ROW COUNT:",
                    len(df)
                )

                print(
                    "PMASS COLUMNS:",
                    list(df.columns)
                )

                if df.empty:
                    return mentions

                team_col = next(
                    (
                        c for c in df.columns
                        if 'team' in str(c).lower()
                    ),
                    None
                )

                for search_host in extra_data:

                    search_host_clean = str(search_host).strip().lower()


                    search_prefix = get_host_prefix(
                        search_host_clean
                    )

                    host_group = get_pmass_host_group(
                        search_host_clean
                    )


                    for _, row in df.iterrows():

                        row_str = " ".join(
                            [str(x) for x in row.tolist()]
                        ).lower()

                        match_found = (
                            search_prefix in row_str
                            or search_host_clean in row_str
                            or (
                                host_group
                                and host_group in row_str
                            )
                        )

                        if match_found:


                            app_lead_col = next(
                                (
                                    c for c in df.columns
                                    if "application lead"
                                    in str(c).lower()
                                ),
                                None
                            )

                            devops_lead_col = next(
                                (
                                    c for c in df.columns
                                    if "devops lead"
                                    in str(c).lower()
                                ),
                                None
                            )

                            email_cols = [
                                c for c in df.columns
                                if "email" in str(c).lower()
                            ]

                            # Application Lead
                            if (
                                app_lead_col
                                and len(email_cols) >= 1
                            ):

                                app_name = str(
                                    row[app_lead_col]
                                ).strip()

                                app_email = str(
                                    row[email_cols[0]]
                                ).strip()

                                if app_name.lower() != "nan":
                                    add_mention(
                                        app_name,
                                        app_email
                                    )

                            # DevOps Lead
                            if (
                                devops_lead_col
                                and len(email_cols) >= 2
                            ):

                                dev_name = str(
                                    row[devops_lead_col]
                                ).strip()

                                dev_email = str(
                                    row[email_cols[1]]
                                ).strip()

                                if dev_name.lower() != "nan":
                                    add_mention(
                                        dev_name,
                                        dev_email
                                    )

                            if team_col:

                                team_val = str(
                                    row[team_col]
                                ).strip().lower()

                                if "database" in team_val:

                                    for m in get_active_dba_mentions():

                                        add_mention(
                                            m["name"],
                                            m["email"]
                                        )

                            break

            except Exception as e:
                print(
                    f"PMASS Excel Error: {e}"
                )

            return mentions

    except Exception as e:
        print(
            f"PMASS Rule Error: {e}"
        )
                            

        # --- RULE 1, 3 & 7: Cluster, DBA, Real Estate ---

    if system == "cluster":

            data = get_cluster_oncall()

            if isinstance(data, pd.DataFrame):

                name_col = next(
                    (c for c in data.columns if "name" in str(c).lower()),
                    None
                )

                email_col = next(
                    (c for c in data.columns if "email" in str(c).lower()),
                    None
                )

                shift_col = next(
                    (c for c in data.columns if "shift time (ist)" in str(c).lower()),
                    None
                )

                for _, row in data.iterrows():

                    if not is_current_shift(row[shift_col]):
                        continue

                    add_mention(
                        str(row[name_col]).strip(),
                        str(row[email_col]).strip()
                    )

            return mentions


    elif system == "real_estate":

            data = get_real_estate_oncall()

            if isinstance(data, pd.DataFrame):

                name_col = next(
                    (c for c in data.columns if "name" in str(c).lower()),
                    None
                )

                email_col = next(
                    (c for c in data.columns if "email" in str(c).lower()),
                    None
                )

                shift_col = next(
                    (c for c in data.columns if "shift time (ist)" in str(c).lower()),
                    None
                )

                for _, row in data.iterrows():

                    result = is_current_shift(row[shift_col])


                    if not result:
                        continue

                    add_mention(
                        str(row[name_col]).strip(),
                        str(row[email_col]).strip()
                    )

            return mentions    

    elif system == "dba":

            active_dba_mentions = get_active_dba_mentions()


            for m in active_dba_mentions:


                add_mention(
                    m["name"],
                    m["email"]
                )


            return mentions

            '''if isinstance(data, pd.DataFrame):


                current_ist = (
                    datetime.utcnow()
                    + timedelta(hours=5, minutes=30)
                )

                current_hour = current_ist.hour

                contact_cols = [
                    c for c in data.columns
                    if "contact" in str(c).lower()
                ]

                for _, row in data.iterrows():
                    

                    # DAY SHIFT
                    if 8 <= current_hour < 20:

                        if len(contact_cols) >= 1:

                            contact_text = str(row[contact_cols[0]])

                            emails = re.findall(
                                r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
                                contact_text
                            )

                            if emails:

                                first_line = (
                                    contact_text
                                    .split("Email")[0]
                                    .strip()
                                )

                                actual_name = (
                                    first_line
                                    .split("--")[0]
                                    .strip()
                                )

                                add_mention(
                                    actual_name,
                                    emails[0]
                                )

                    # NIGHT SHIFT
                    else:

                        if len(contact_cols) >= 2:

                            contact_text = str(row[contact_cols[1]])

                            emails = re.findall(
                                r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
                                contact_text
                            )

                            if emails:

                                first_line = (
                                    contact_text
                                    .split("Email")[0]
                                    .strip()
                                )

                                actual_name = (
                                    first_line
                                    .split("--")[0]
                                    .strip()
                                )

                                add_mention(
                                    actual_name,
                                    emails[0]
                                )
                #print(data.columns.tolist())
                return mentions'''

    # --- RULE 2: Batch ---
    elif system == "batch":
            data = get_batch_oncall()
            dfs = pd.read_html(io.StringIO(str(data))) if isinstance(data, str) else [data]

            
            for df in dfs:
                time_col = next((c for c in df.columns if "ist" in str(c).lower()), None)
                name_col = next((c for c in df.columns if 'name' in str(c).lower()), df.columns[0] if len(df.columns) > 0 else None)
                email_col = next((c for c in df.columns if 'email' in str(c).lower()), None)
                
                if time_col and name_col:

                    for _, row in df.iterrows():

                        shift = str(row[time_col]).lower()

                        if shift == 'nan':
                            continue
                            
                        
                        if "escalation" in shift:
                            continue
                            
                            
                        if is_current_shift(row[time_col]):

                            pri_name = str(row[name_col])

                            if pri_name.lower() == 'nan':
                                continue

                            pri_email = (
                                str(row[email_col])
                                if email_col
                                else ""
                            )

                            if pri_email.lower() == 'nan':
                                pri_email = ""

                            add_mention(
                                pri_name,
                                pri_email
                            )    
    
        
# --- RULE 4 & 6: Code Blue & Zabbix ---
    elif system == "devops":
            data = get_devops_oncall()
            dfs = pd.read_html(io.StringIO(str(data))) if isinstance(data, str) else [data]
            today = datetime.now().date()
            
            for df in dfs:
                start_col = next((c for c in df.columns if 'start' in str(c).lower()), None)
                end_col = next((c for c in df.columns if 'end' in str(c).lower()), None)
                
                # FIX: Explicitly find the Primary and Secondary Email columns
                pri_col = next((c for c in df.columns if 'primary' in str(c).lower() and 'email' not in str(c).lower()), None)
                sec_col = next((c for c in df.columns if 'second' in str(c).lower() and 'email' not in str(c).lower()), None)
                pri_email_col = next((c for c in df.columns if 'primary email' in str(c).lower()), None)
                sec_email_col = next((c for c in df.columns if 'secondary email' in str(c).lower()), None)
                
                if start_col and end_col and pri_col:
                    for _, row in df.iterrows():
                        try:
                            s_str, e_str = str(row[start_col]), str(row[end_col])
                            if s_str.lower() == 'nan' or e_str.lower() == 'nan': continue
                            
                            s_match = re.search(r'(\d{1,2})[-/](\d{1,2})[-/](\d{2,4})', s_str)
                            e_match = re.search(r'(\d{1,2})[-/](\d{1,2})[-/](\d{2,4})', e_str)
                            
                            if s_match and e_match:
                                m1, d1, y1 = s_match.groups()
                                m2, d2, y2 = e_match.groups()
                                y1 = int(y1) + 2000 if len(y1) == 2 else int(y1)
                                y2 = int(y2) + 2000 if len(y2) == 2 else int(y2)
                                
                                start_date = datetime(y1, int(m1), int(d1)).date()
                                end_date = datetime(y2, int(m2), int(d2)).date()
                                
                                if start_date <= today <= end_date:
                                    pri_name = str(row[pri_col])
                                    if pri_name.lower() != 'nan':
                                        # FIX: Grab the email directly from the Primary Email column!
                                        pri_email = str(row[pri_email_col]) if pri_email_col else ""
                                        if str(pri_email).lower() == 'nan': pri_email = ""
                                        add_mention(pri_name, pri_email)
                                    
                                    if sec_col:
                                        sec_name = str(row[sec_col])
                                        if sec_name.lower() != 'nan':
                                            # FIX: Grab the email directly from the Secondary Email column!
                                            sec_email = str(row[sec_email_col]) if sec_email_col else ""
                                            if str(sec_email).lower() == 'nan': sec_email = ""
                                            add_mention(sec_name, sec_email)
                                    break
                        except: pass            

        
    return mentions    


def is_ignored_for_draft(host, abbrv, node_id):
    h = str(host).strip().lower()
    a = str(abbrv).strip().lower()
    n = str(node_id).strip()
    
    if h == "charlie" and a == "cc" and n == "14": return True
    if h == "delta" and a == "db" and n == "36": return True
    if h == "delta" and a == "dc": return True
    if h == "echo": return True
    if h == "foxtrot": return True
    if h == "romeo" and a in ["rc", "rd", "re", "rx"]: return True
    if h == "loadboxes" and a == "d4": return True
    
    return False

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
        formatted_message = f"🚨 **CRITICAL ALERT** 🚨\n\n{formatted_message}"

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

@st.dialog("Confirm Teams Post")
def confirm_post_dialog(message_text, mentions, image_base64=None):
    st.warning("Are you sure you want to post this message to the Teams channel?")
    st.markdown(f"<div style='background-color: #f4f4f4; padding: 10px; border-radius: 5px; font-family: monospace; font-size: 13px;'>{message_text.replace(chr(10), '<br>')}</div>", unsafe_allow_html=True)
    
    if image_base64:
        st.markdown(f"<div style='margin-top: 10px;'><b>Attached Image:</b><br><img src='{image_base64}' width='100'></div>", unsafe_allow_html=True)
        
    st.write("") 
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("✔️ Yes, Post Message", type="primary", use_container_width=True):
            with st.spinner("Posting to Teams..."):
                success, msg = post_to_teams(message_text, mentions, image_base64)
                if success:
                    st.success("Message posted successfully!")
                    time.sleep(2)
                    st.session_state.pending_post_text = None
                    st.session_state.pending_post_image = None
                    st.rerun()
                else:
                    st.error(f"Failed to post: {msg}")
    with col2:
        if st.button("❌ Cancel", use_container_width=True):
            st.session_state.pending_post_text = None
            st.session_state.pending_post_image = None
            st.rerun()
