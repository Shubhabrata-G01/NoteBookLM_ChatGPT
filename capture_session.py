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

        # Navigate to the Google login portal or NotebookLM directly
        page.goto("https://google.com")

        print("\n--> CRITICAL STEP: Log in completely, complete 2FA, and make sure you see your NotebookLM dashboard.")
        print("--> Once you see your dashboard, close the browser window or press Enter here to save your tokens.")

        input("\nPress Enter here AFTER you have successfully logged in...")
        context.close()
        print("Session tokens captured successfully inside ./google_session!")

if __name__ == "__main__":
    initialize_session()
