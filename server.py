import os
import time
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from playwright.sync_api import sync_playwright

# =====================================================================
# 1. Initialize FastMCP instance
# =====================================================================
# Your deployed Render hostname. Update this if you ever redeploy under a
# different service name or custom domain.
RENDER_HOSTNAME = "notebooklm-mcp-bridge-chatgpt.onrender.com"

# In this SDK version (mcp 1.x), transport_security is a constructor
# argument on FastMCP itself, not on sse_app(). Passing it here allowlists
# the real Host header Render forwards, instead of the default localhost-only
# allowlist that DNS-rebinding protection auto-enables and that was causing
# every real request to be rejected with 421 Misdirected Request / Invalid
# Host header.
mcp = FastMCP(
    "NotebookLM-Live-Link",
    transport_security=TransportSecuritySettings(
        allowed_hosts=[
            RENDER_HOSTNAME,
            f"{RENDER_HOSTNAME}:*",
        ],
        allowed_origins=["*"],
    ),
)

# Directory where your active Google login session tokens will live
USER_DATA_DIR = "/app/google_session" if os.environ.get("DOCKER_ENV") else "./google_session"


@mcp.tool()
def query_notebooklm(notebook_name: str, query: str) -> str:
    """
    Connects to the live NotebookLM interface, opens a notebook by name,
    submits a question, and returns the live text response.
    """
    with sync_playwright() as p:
        # Launching Chromium with user session flags.
        # headless=True is required in the cloud container: Render has no
        # display server, so headless=False would crash the tool call.
        context = p.chromium.launch_persistent_context(
            USER_DATA_DIR,
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-blink-features=AutomationControlled"
            ]
        )
        page = context.new_page()

        try:
            # Navigate to the official NotebookLM live interface
            page.goto("https://google.com", wait_until="networkidle")

            # Check if login page is showing up instead of the dashboard
            if "signout" not in page.content().lower() and "sign in" in page.content().lower():
                return "Error: Cloud session expired. Please update your google_session tokens."

            # Find and open your specific live notebook workspace
            notebook_selector = f"text={notebook_name}"
            page.wait_for_selector(notebook_selector, timeout=10000)
            page.click(notebook_selector)
            page.wait_for_load_state("networkidle")

            # Locate the chat input box using its standard placeholder attribute
            chat_input = page.locator("textarea[placeholder*='Ask a question']")
            chat_input.wait_for(state="visible", timeout=10000)
            chat_input.fill(query)
            chat_input.press("Enter")

            # Wait for NotebookLM's source generation streaming elements to stop processing
            time.sleep(8)

            # Grab all generated responses text panels on screen
            responses = page.locator(".chat-response-text-class, [role='log'] div").all_text_contents()

            if not responses:
                # Fallback to extract visible paragraphs inside the active message block
                responses = page.locator("p").all_text_contents()

            latest_answer = responses[-1] if responses else "Successfully processed query, but could not capture text elements."
            return latest_answer

        except Exception as e:
            return f"An error occurred while scraping the live dashboard: {str(e)}"
        finally:
            context.close()


# =====================================================================
# 2. Native FastMCP Server Deployment via sse_app
# =====================================================================
if __name__ == "__main__":
    import uvicorn

    print("Starting Open Source NotebookLM MCP Server on port 8080...")

    # Generate the native SSE application from FastMCP. The transport
    # security settings (Host-header allowlist) were already configured
    # on the FastMCP instance above; sse_app() only accepts mount_path.
    starlette_app = mcp.sse_app()

    # Run the application cleanly via Uvicorn
    uvicorn.run(starlette_app, host="0.0.0.0", port=8080)
