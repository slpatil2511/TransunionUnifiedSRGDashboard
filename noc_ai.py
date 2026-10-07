# noc_ai.py
import os
import requests
import urllib.request
import pandas as pd
from datetime import datetime
import config
from noc_data import get_cluster_oncall, get_batch_oncall, get_dba_oncall, get_devops_oncall, get_real_estate_oncall

def get_ai_response(user_question, active_alerts, alert_timestamps):
    """Gathers all NOC context and asks the OneTru AI for an answer."""
    
    if not getattr(config, 'AURA_API_KEY', None) or config.AURA_API_KEY == "":
        return "⚠️ **Aura Error:** Please generate a key from OneTru AI Studio and add it to config.py as `AURA_API_KEY`."

    # --- 1. GATHER DASHBOARD CONTEXT ---
    now = datetime.now()
    alert_context = "CURRENT ACTIVE ALERTS:\n"
    if not active_alerts:
        alert_context += "- No active alerts right now.\n"
    else:
        for alert in active_alerts:
            start_time = alert_timestamps.get(alert, now)
            duration_minutes = int((now - start_time).total_seconds() / 60)
            alert_context += f"- {alert} (Active for {duration_minutes} minutes)\n"

    oncall_context = "CURRENT ON-CALL SCHEDULES:\n"
    try:
        oncall_context += f"Cluster:\n{get_cluster_oncall().to_string()}\n\n"
        oncall_context += f"Batch:\n{get_batch_oncall().to_string()}\n\n"
        oncall_context += f"DBA:\n{get_dba_oncall().to_string()}\n\n"
        oncall_context += f"DevOps:\n{get_devops_oncall().to_string()}\n\n"
        oncall_context += f"Real Estate:\n{get_real_estate_oncall().to_string()}\n\n"
    except: pass

    pmass_context = "PMASS HOST MAPPINGS:\n"
    try:
        if os.path.exists(getattr(config, 'PMASS_EXCEL_PATH', '')):
            pmass_context += pd.read_excel(config.PMASS_EXCEL_PATH).to_csv(index=False)
    except: pass

    system_prompt = f"""
    You are an expert Senior NOC (Network Operations Center) Engineer at TransUnion.
    Your job is to assist L1 analysts by answering questions about the dashboard.
    
    Use the following live data to answer their questions:
    
    {alert_context}
    
    {oncall_context}
    
    {pmass_context}
    
    Instructions:
    - If asked about the reason for an alert, use your general IT knowledge to explain what the error usually means.
    - If asked about PMASS hosts, look at the PMASS HOST MAPPINGS to find the Application Lead or DevOps Lead.
    - If asked how long an alert has been active, refer to the CURRENT ACTIVE ALERTS duration.
    - Keep your answers concise, professional, and directly helpful.
    """

    # --- 2. BUILD THE EXACT PAYLOAD FROM THE ONETRU DOCS ---
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Name": "NOC_Dashboard",
        "Tracking-Info": "NOC Dashboard AI Assistant",
        "x-auth-type": "ais-iam",
        "Authorization": f"Bearer {config.AURA_API_KEY}"
    }

    # Using the exact JSON structure required by OneTru
    payload = {
        "model": "gemma-4",
        "stream": False, 
        "chat": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_question}
        ]
    }

    # --- 3. SEND THE REQUEST ---
    try:
        # Grab corporate proxy settings if needed
        proxies = urllib.request.getproxies()
        
        response = requests.post(
            config.AURA_BASE_URL, 
            headers=headers, 
            json=payload, 
            proxies=proxies, 
            verify=False, # Bypass corporate SSL blocks
            timeout=60
        )
        
        if response.status_code == 200:
            data = response.json()
            
            # Extract the AI's message from the OneTru JSON response
            if "chat" in data and len(data["chat"]) > 0:
                return data["chat"][-1].get("content", str(data))
            elif "choices" in data and len(data["choices"]) > 0:
                return data["choices"][0].get("message", {}).get("content", str(data))
            elif "message" in data:
                return data["message"]
            elif "response" in data:
                return data["response"]
            else:
                return str(data)
        else:
            return f"⚠️ **OneTru API Error {response.status_code}:** {response.text}"
            
    except Exception as e:
        return f"⚠️ **Connection Error:** {str(e)}"