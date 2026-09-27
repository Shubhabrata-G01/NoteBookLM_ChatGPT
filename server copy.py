import os
import time
from fastapi import FastAPI, Request  # type: ignore
from mcp.server.fastmcp import FastMCP  # type: ignore
from mcp.server.sse import SseServerTransport  # type: ignore
from playwright.sync_api import sync_playwright  # type: ignore

# 1. Initialize FastMCP instance
mcp = FastMCP("NotebookLM-Live-Link")

# Directory where your active Google login session tokens will live
USER_DATA_DIR = "/app/google_session" if os.environ.get("DOCKER_ENV") else "./google_session"

@mcp.tool()
def query_notebooklm(notebook_name: str, query: str) -> str:
    """
    Connects to the live NotebookLM interface, opens a notebook by name, 
    submits a question, and returns the live text response.
    """
    with sync_playwright() as p:
        # Launching Chromium with user session flags
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
            # NotebookLM typical loading element: wait until generation buttons reappear or status spinner drops
            time.sleep(8) 
            
            # Grab all generated responses text panels on screen
            # (Matches generic material/div components where NotebookLM prints results)
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

# # 2. Wrap MCP with FastAPI to handle web hooks via SSE
# app = FastAPI()
# sse_transport = SseServerTransport(mcp)

# @app.get("/sse")
# async def handle_sse():
#     async with sse_transport.connect_sse() as (read_stream, write_stream):
#         await mcp.handle_request(read_stream, write_stream)

# @app.post("/messages")
# async def handle_messages():
#     async with sse_transport.connect_messages() as (read_stream, write_stream):
#         await mcp.handle_request(read_stream, write_stream)

# if __name__ == "__main__":
#     import uvicorn
#     # Exposing the port for the cloud container routing framework
#     uvicorn.run(app, host="0.0.0.0", port=8080)

# app = FastAPI()

# Map the FastMCP instance correctly to an app framework endpoint
# @app.get("/sse")
# async def handle_sse():
#     transport = SseServerTransport("/messages")
#     async with transport.connect_sse() as (read_stream, write_stream):
#         await mcp.handle_request(read_stream, write_stream)

# @app.post("/messages")
# async def handle_messages():
#     transport = SseServerTransport("/messages")
#     async with transport.connect_messages() as (read_stream, write_stream):
#         await mcp.handle_request(read_stream, write_stream)

# if __name__ == "__main__":
#     import uvicorn
#     # Exposing the port for the cloud container routing framework
#     uvicorn.run(app, host="0.0.0.0", port=8080)



# 2. Wrap MCP with FastAPI using the proper application mapping
app = FastAPI()
transport = SseServerTransport("/messages")

@app.get("/sse")
async def handle_sse(request: Request):
    """
    Directly passes the complete ASGI network context components 
    down into the mcp server event stream parser.
    """
    await transport.handle_sse(
        scope=request.scope, 
        receive=request.receive, 
        send=request.send
    )

@app.post("/messages")
async def handle_messages(request: Request):
    """
    Directly processes internal incoming JSON-RPC calls sent via tools.
    """
    async with transport.connect_messages(
        scope=request.scope, 
        receive=request.receive, 
        send=request.send
    ) as (read_stream, write_stream):
        await mcp.handle_request(read_stream, write_stream)

if __name__ == "__main__":
    # Import from the same interpreter used to run this script.
    import sys
    import subprocess

    try:
        import uvicorn  # type: ignore[import-not-found]
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "uvicorn"])
        import uvicorn  # type: ignore[import-not-found]

    uvicorn.run(app, host="0.0.0.0", port=8080)