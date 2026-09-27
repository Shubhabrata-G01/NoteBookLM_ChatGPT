import os
import asyncio
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from playwright.async_api import async_playwright

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
async def query_notebooklm(notebook_name: str, query: str) -> str:
    """
    Connects to the live NotebookLM interface, opens a notebook by name,
    submits a question, and returns the live text response.
    """
    # Using Playwright's ASYNC API here, not the sync API. The whole server
    # (FastMCP/Starlette/Uvicorn) runs on an asyncio event loop, and
    # Playwright's sync API is not safe to call from inside a running
    # asyncio loop's thread -- doing so fails before any browser
    # interaction happens, which is the bug that was occurring here
    # regardless of notebook name or query wording.
    async with async_playwright() as p:
        # Launching Chromium with user session flags.
        # headless=True is required in the cloud container: Render has no
        # display server, so headless=False would crash the tool call.
        context = await p.chromium.launch_persistent_context(
            USER_DATA_DIR,
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-blink-features=AutomationControlled"
            ]
        )
        page = await context.new_page()

        try:
            # Navigate directly to NotebookLM itself, not Google's generic
            # homepage. If the session is invalid/expired, NotebookLM
            # redirects to accounts.google.com -- checking the resulting
            # URL is a far more reliable signal than scanning page text for
            # words like "sign in", which can appear or be absent for
            # unrelated reasons (locale, layout, consent dialogs, etc.)
            # and was producing false "session expired" results even with
            # a genuinely fresh, valid login.
            await page.goto("https://notebooklm.google.com/", wait_until="networkidle")
            landed_url = page.url
            print(f"[query_notebooklm] Landed on: {landed_url}")

            if "accounts.google.com" in landed_url or "ServiceLogin" in landed_url:
                return "Error: Cloud session expired. Please update your google_session tokens."

            # Find and open your specific live notebook workspace
            notebook_selector = f"text={notebook_name}"
            await page.wait_for_selector(notebook_selector, timeout=10000)
            await page.click(notebook_selector)
            await page.wait_for_load_state("networkidle")

            # Locate the chat input box using its standard placeholder attribute
            chat_input = page.locator("textarea[placeholder*='Ask a question']")
            await chat_input.wait_for(state="visible", timeout=10000)
            await chat_input.fill(query)
            await chat_input.press("Enter")

            # Wait for NotebookLM's source generation streaming elements to stop processing
            await asyncio.sleep(8)

            # Grab all generated responses text panels on screen
            responses = await page.locator(".chat-response-text-class, [role='log'] div").all_text_contents()

            if not responses:
                # Fallback to extract visible paragraphs inside the active message block
                responses = await page.locator("p").all_text_contents()

            latest_answer = responses[-1] if responses else "Successfully processed query, but could not capture text elements."
            return latest_answer

        except Exception as e:
            # Include page URL/title in the error so failures are debuggable
            # from the returned tool output alone, without needing another
            # round trip to add logging.
            try:
                debug_info = f" (at {page.url}, title: {await page.title()})"
            except Exception:
                debug_info = ""
            return f"An error occurred while scraping the live dashboard: {str(e)}{debug_info}"
        finally:
            await context.close()


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