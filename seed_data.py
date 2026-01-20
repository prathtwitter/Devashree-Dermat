# seed_data.py
import gspread
import pandas as pd
import json
import os

# --- IMPORTANT ---
# This script is now designed to run locally using OAuth 2.0.
# The first time you run it, it will open a browser window for you to log in
# and authorize the script to access your Google Drive and Sheets.

# Name for your Google Sheet database
SHEET_NAME = "Derma-AI-DB"

def seed_data():
    """
    Creates and seeds a Google Sheet using OAuth 2.0 for user authentication.
    """
    print("Attempting to authenticate using OAuth 2.0 for Desktop...")
    print("A browser window may open for you to grant permission.")

    try:
        # This command is now explicitly pointed to the correct credentials file.
        # It will create a "token.json" file to store your credentials
        # so you don't have to log in every time.
        gc = gspread.oauth(credentials_filename='desktop_app_credentials.json')
        print("Authentication successful.")
    except Exception as e:
        print(f"Authentication failed: {e}")
        print("\nPlease ensure you have a 'desktop_app_credentials.json' file in this directory.")
        print("Follow the new instructions in '.streamlit/secrets.toml' to get this file.")
        return

    # 1. Create a new spreadsheet or open an existing one
    try:
        print(f"Checking for existing spreadsheet named '{SHEET_NAME}'...")
        sheet = gc.open(SHEET_NAME)
        print("Spreadsheet found. It will be cleared and re-seeded.")
        # Get the service account email from secrets to grant it access
        service_account_email = None
        try:
             import tomllib
             secrets_path = os.path.join(".streamlit", "secrets.toml")
             with open(secrets_path, "rb") as f:
                secrets = tomllib.load(f)
                service_account_email = secrets.get("gcp_service_account", {}).get("client_email")
        except Exception:
            print("Could not read service account email from secrets.")

        # Clear all existing worksheets
        for worksheet in sheet.worksheets():
             if worksheet.title != "Sheet1": # Avoid trying to delete the default sheet if it's the only one
                try:
                    sheet.del_worksheet(worksheet)
                except Exception as del_e:
                    print(f"Could not delete worksheet {worksheet.title}: {del_e}")
    except gspread.SpreadsheetNotFound:
        print("Spreadsheet not found. Creating a new one...")
        sheet = gc.create(SHEET_NAME)
        print(f"Sheet '{SHEET_NAME}' created.")
    
    # After creating the sheet, it's crucial to share it with the service account
    # that the deployed Streamlit app will use.
    try:
        if not service_account_email:
             import tomllib
             secrets_path = os.path.join(".streamlit", "secrets.toml")
             with open(secrets_path, "rb") as f:
                secrets = tomllib.load(f)
                service_account_email = secrets.get("gcp_service_account", {}).get("client_email")

        if service_account_email:
            print(f"Sharing sheet with service account: {service_account_email}")
            sheet.share(service_account_email, perm_type='user', role='writer')
            print("Sheet shared successfully.")
        else:
            print("\nWARNING: Could not find the service account email in your secrets file.")
            print("You MUST manually share the created Google Sheet with that email address, or the deployed app will not work.")

    except Exception as e:
        print(f"An error occurred while trying to share the sheet: {e}")
        print(f"Please manually share the sheet with '{service_account_email}'")


    user_id = '12345678-1234-1234-1234-1234567890ab'

    # 2. Seed 'users' worksheet
    print("Seeding 'users' worksheet...")
    users_df = pd.DataFrame([{"id": user_id, "name": "Devashree", "skin_type": "Acne-Prone, Combination", "location": "Canada"}])
    users_ws = sheet.add_worksheet(title="users", rows=10, cols=10)
    users_ws.update([users_df.columns.values.tolist()] + users_df.values.tolist())

    # 3. Seed 'skin_profile' worksheet
    print("Seeding 'skin_profile' worksheet...")
    skin_profile_df = pd.DataFrame([{"user_id": user_id, "barrier_status": "Compromised", "current_concerns_json": json.dumps({"diagnosis": "Stress-Induced Inflammatory Acne...", "triggers": ["Environmental Shock", "..."], "...": "..."}), "active_medications_json": json.dumps(["CNN 50"]), "avoid_ingredients_json": json.dumps(["SA Cleansers"])}])
    profile_ws = sheet.add_worksheet(title="skin_profile", rows=10, cols=10)
    profile_ws.update([skin_profile_df.columns.values.tolist()] + skin_profile_df.values.tolist())
    
    # 4. Seed 'routine_audit' worksheet
    print("Seeding 'routine_audit' worksheet...")
    routine_audit_data = [{"user_id": user_id, "product_name": "Micro-Peeling gels", "category": "Cleanser", "status": "Unsafe", "notes": "Compromises barrier."}]
    audit_df = pd.DataFrame(routine_audit_data)
    audit_ws = sheet.add_worksheet(title="routine_audit", rows=20, cols=10)
    audit_ws.update([audit_df.columns.values.tolist()] + audit_df.values.tolist())

    # 5. Create 'interaction_logs' worksheet
    print("Creating 'interaction_logs' worksheet...")
    logs_df = pd.DataFrame(columns=["id", "created_at", "user_id", "input_type", "user_query", "ai_analysis", "severity_score", "recommended_product_name", "recommended_product_link"])
    logs_ws = sheet.add_worksheet(title="interaction_logs", rows=100, cols=10)
    logs_ws.update([logs_df.columns.values.tolist()])

    # Delete the default "Sheet1"
    try:
        sheet.del_worksheet(sheet.worksheet("Sheet1"))
    except gspread.WorksheetNotFound:
        pass
        
    print("\nSeeding process complete!")
    print(f"Your database is ready at: {sheet.url}")

if __name__ == "__main__":
    seed_data()
