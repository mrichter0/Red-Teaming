# computers/local_playwright.py
import asyncio
from playwright.async_api import Browser, Page
from .base_playwright import BasePlaywrightComputer
import json

class LocalPlaywrightComputer(BasePlaywrightComputer):
    """Launches a local Chromium instance using Playwright with the Chrome channel."""

    async def __aenter__(self):
        await super().__aenter__()
        return self    

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await super().__aexit__(exc_type, exc_val, exc_tb)  # Explicitly call parent's __aexit__



    async def _get_browser_and_page(self) -> tuple[Browser, Page]:
        # browser = await self._playwright.chromium.launch(headless=False)
        # context = await browser.new_context(viewport={'width': 1024, 'height': 768})
        browser = await self._playwright.chromium.connect_over_cdp("http://localhost:9222")
        # context = await browser.contexts[0]
        if browser.contexts:
            context = browser.contexts[0]
        else:
            context = await browser.new_context()
        page = await context.new_page()  # Open a new tab in Chrome
        return browser, page
        # # Load cookies from the file and add them to the context
        # with open("cookie_br_updates2.json", "r") as f:
        #     cookies = json.load(f)
        # await context.add_cookies(cookies)
    






