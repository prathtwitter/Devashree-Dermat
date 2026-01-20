# app.py
import streamlit as st
import os
import base64
import json
import google.generativeai as genai
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from googlesearch import search
from datetime import datetime

# --- 1. SETUP & INITIALIZATION ---

# Load credentials from Streamlit secrets
try:
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
    GCP_CREDS = st.secrets["gcp_service_account"]
except KeyError:
    st.error("ERROR: Missing credentials. Please add GEMINI_API_KEY and gcp_service_account to .streamlit/secrets.toml")
    st.stop()

# Initialize clients
try:
    genai.configure(api_key=GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel('gemini-1.5-pro-latest')
    
    # Google Sheets Client
    SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(GCP_CREDS, scopes=SCOPES)
    gc = gspread.authorize(creds)
    SHEET_NAME = "Derma-AI-DB"
    spreadsheet = gc.open(SHEET_NAME)

    print("Clients initialized successfully.")
except Exception as e:
    st.error(f"Error initializing clients: {e}")
    st.stop()

# Hardcoded User ID
USER_ID = '12345678-1234-1234-1234-1234567890ab'

# --- 2. DATABASE HELPER FUNCTIONS (Google Sheets) ---

@st.cache_data(ttl=600) # Cache data for 10 minutes
def get_user_data(user_id):
    """Fetches the latest skin profile and routine audit from Google Sheets."""
    try:
        # Fetch skin profile
        profile_ws = spreadsheet.worksheet("skin_profile")
        profile_df = pd.DataFrame(profile_ws.get_all_records())
        user_profile_series = profile_df[profile_df['user_id'] == user_id].iloc[0]
        
        # Fetch routine audit
        audit_ws = spreadsheet.worksheet("routine_audit")
        audit_df = pd.DataFrame(audit_ws.get_all_records())
        user_audit_df = audit_df[audit_df['user_id'] == user_id]

        # Convert to dictionary and deserialize JSON
        profile_data = user_profile_series.to_dict()
        profile_data['current_concerns'] = json.loads(profile_data.pop('current_concerns_json', '{}'))
        profile_data['active_medications'] = json.loads(profile_data.pop('active_medications_json', '[]'))
        profile_data['avoid_ingredients'] = json.loads(profile_data.pop('avoid_ingredients_json', '[]'))
        
        audit_data = user_audit_df.to_dict('records')

        return profile_data, audit_data
    except Exception as e:
        st.error(f"Error fetching data from Google Sheets: {e}")
        st.info("Please ensure the sheet is named 'Derma-AI-DB' and shared with your service account email.")
        return None, None

def log_interaction(user_id, input_type, query, analysis, severity, product_name, product_link):
    """Logs the user interaction to the Google Sheet."""
    try:
        logs_ws = spreadsheet.worksheet("interaction_logs")
        new_row = [
            str(datetime.now()),
            str(datetime.now().isoformat()),
            user_id,
            input_type,
            query,
            analysis,
            severity,
            product_name,
            product_link
        ]
        logs_ws.append_row(new_row, table_range="A1")
    except Exception as e:
        st.warning(f"Failed to log interaction to Google Sheet: {e}")

# --- 3. CORE AI & SEARCH LOGIC --- (Identical to previous versions)

def construct_system_prompt(skin_profile, routine_audit):
    if not skin_profile:
        return "You are a helpful dermatological assistant."

    profile_str = json.dumps(skin_profile.get('current_concerns', {}), indent=2)
    audit_str = "\n".join([f"- {item['product_name']} ({item['status']}): {item['notes']}" for item in routine_audit])

    prompt = f"""
    You are a highly personalized, localized Canadian Dermatological Assistant for Devashree.
    Your goal is to analyze her skin issues, remember her history, and recommend budget-friendly products from Amazon Canada.
    **GUARDRAILS:**
    1.  **NEVER Refuse to Help:** If an issue seems severe, label it "High Severity" but always provide the best possible over-the-counter palliative care advice.
    2.  **Amazon Canada Only:** All product searches must be for `amazon.ca`.
    3.  **Budget-Friendly:** Prioritize products under $25 CAD.
    4.  **Context is Key:** You MUST use the user's history below to inform your diagnosis.
    ---
    **DEEP CONTEXT: Devashree's Current Skin Profile**
    -   **Barrier Status:** {skin_profile.get('barrier_status', 'N/A')}
    -   **Active Medications:** {', '.join(skin_profile.get('active_medications', []))}
    -   **Detailed Concerns:**
        ```json
        {profile_str}
        ```
    -   **Ingredients to Avoid:** {', '.join(skin_profile.get('avoid_ingredients', []))}
    ---
    **PRODUCT DATABASE: Routine Audit**
    {audit_str}
    ---
    **YOUR PROTOCOL:**
    1.  **Analyze Input:** Review the user's text or image.
    2.  **Diagnose:** Identify the issue.
    3.  **Cross-Reference:** Check against her `avoid_ingredients` and `routine_audit`.
    4.  **Determine Action:** If a product is needed, formulate a search query on a new line formatted EXACTLY as `SEARCH: <product_type> <key_ingredient> under $25 CAD`.
    5.  **Respond:** Provide your analysis and the search query if needed.
    """
    return prompt.strip()

def search_amazon(query):
    try:
        full_query = f"{query} site:amazon.ca"
        st.write(f"⚙️ Searching Amazon Canada for: `{query}`...")
        search_results = list(search(full_query, num_results=3, lang="en"))
        for url in search_results:
            if "amazon.ca" in url and "/dp/" in url:
                st.success(f"✅ Found product: {url}")
                return url
        st.warning("Could not find a direct Amazon.ca product link.")
        return None
    except Exception as e:
        st.error(f"Google search failed: {e}")
        return None

# --- 4. STREAMLIT UI ---

st.set_page_config(page_title="Derma-AI", layout="wide")

with st.sidebar:
    st.title("👩‍⚕️ Derma-AI Assistant")
    st.write("Personalized skin analysis for Devashree.")
    st.markdown("---")
    st.header("Current Protocol")
    profile_data, audit_data = get_user_data(USER_ID)
    if profile_data:
        st.write(f"**Barrier Status:** `{profile_data.get('barrier_status', 'N/A')}`")
        st.info("Master Protocol: Keep barrier calm. No new acids until Feb 4th.")
        with st.expander("Active Medications"):
            st.write(profile_data.get('active_medications', ["None"]))
        with st.expander("View Full Skin Profile"):
            st.json(profile_data.get('current_concerns', {}))
    else:
        st.warning("Could not load user profile from Google Sheets.")

st.title("Chat with your AI Dermatologist")

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Describe your skin concern..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        full_response = ""
        system_prompt = construct_system_prompt(profile_data, audit_data)
        
        gemini_history = [{"role": "user" if msg["role"] == "user" else "model", "parts": [msg["content"]]} for msg in st.session_state.messages]
        
        try:
            chat_session = gemini_model.start_chat(history=gemini_history)
            response = chat_session.send_message(prompt, stream=True)
            for chunk in response:
                full_response += chunk.text
                message_placeholder.markdown(full_response + "▌")
            message_placeholder.markdown(full_response)
        except Exception as e:
            st.error(f"An error occurred with the Gemini API: {e}")
            full_response = "Sorry, I encountered an error."

    if "SEARCH:" in full_response:
        query_line = [line for line in full_response.split('\n') if line.startswith("SEARCH:")][0]
        search_query = query_line.replace("SEARCH:", "").strip()
        product_link = search_amazon(search_query)
        if product_link:
            st.session_state.messages.append({"role": "assistant", "content": f"Here is a recommended product: [View on Amazon.ca]({product_link})"})
            with st.chat_message("assistant"):
                 st.markdown(f"I found a product for you: [View on Amazon.ca]({product_link})")
            log_interaction(USER_ID, 'text', prompt, full_response, 5, search_query, product_link)
        else:
             log_interaction(USER_ID, 'text', prompt, full_response, 5, search_query, None)
    else:
        log_interaction(USER_ID, 'text', prompt, full_response, 3, None, None)

    st.session_state.messages.append({"role": "assistant", "content": full_response})

# Image uploader - remains the same
uploaded_file = st.file_uploader("Upload an image for analysis", type=["png", "jpg", "jpeg"])
if uploaded_file is not None:
    st.image(uploaded_file, caption="Image for Analysis", width=250)
    
    if st.button("Analyze Image"):
        with st.spinner("Analyzing image..."):
            image_bytes = uploaded_file.getvalue()
            system_prompt = construct_system_prompt(profile_data, audit_data)
            try:
                image_part = {"mime_type": uploaded_file.type, "data": image_bytes}
                prompt_parts = [system_prompt, "Analyze this image of my skin and tell me what you see.", image_part]
                response = gemini_model.generate_content(prompt_parts)
                analysis_result = response.text
                st.session_state.messages.append({"role": "user", "content": f" (Image: {uploaded_file.name})"})
                st.session_state.messages.append({"role": "assistant", "content": analysis_result})
                st.rerun()
            except Exception as e:
                st.error(f"Gemini image analysis failed: {e}")

