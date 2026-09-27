import os
from playwright.sync_api import sync_playwright

USER_DATA_DIR = "./google_session"

def initialize_session():
    # Ensure the folder structure physically exists on your drive
    if not os.path.exists(USER_DATA_DIR):
        os.makedirs(USER_DATA_DIR)
        print(f"Created directory: {USER_DATA_DIR}")

    print("Launching Chromium... Please log into your Google Account in the opened window.")
    
    with sync_playwright() as p:
        # Launching a visible persistent browser profile context
        context = p.chromium.launch_persistent_context(
            USER_DATA_DIR,
            headless=False,  # Keep this visible so you can interact with it
            args=["--disable-blink-features=AutomationControlled"]
        )
        page = context.new_page()
        
        # Go straight to NotebookLM's own login flow, not the generic Google
        # homepage. This ensures the resulting cookies include whatever
        # NotebookLM's specific sign-in path sets -- a generic google.com
        # login does not guarantee that.
        page.goto("https://notebooklm.google.com/")
        
        print("\n--> CRITICAL STEP: Log in completely, complete 2FA, and make sure you see your NotebookLM dashboard.")
        print("--> Once you see your dashboard, come back here and press Enter to save your tokens.")
        
        input("\nPress Enter here AFTER you have successfully logged in and see your NotebookLM dashboard...")

        # Verify we actually landed on NotebookLM's dashboard, not still on
        # a Google sign-in page, before saving anything as "successful".
        current_url = page.url
        if "accounts.google.com" in current_url:
            print(f"\nWARNING: Still on a Google sign-in page ({current_url}).")
            print("Session was NOT captured correctly -- login did not complete. Re-run this script and finish logging in before pressing Enter.")
        else:
            print(f"\nConfirmed landed on: {current_url}")
            print("Session tokens captured successfully inside ./google_session!")

        context.close()

if __name__ == "__main__":
    initialize_session()