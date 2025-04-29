#computers/base_playwright.py
import asyncio
import base64
import time
from typing import List, Dict, Literal
from playwright.async_api import async_playwright, Browser, Page

CUA_KEY_TO_PLAYWRIGHT_KEY = {
    "/": "Divide",
    "\\": "Backslash",
    "alt": "Alt",
    "arrowdown": "ArrowDown",
    "arrowleft": "ArrowLeft",
    "arrowright": "ArrowRight",
    "arrowup": "ArrowUp",
    "backspace": "Backspace",
    "capslock": "CapsLock",
    "cmd": "Meta",
    "ctrl": "Control",
    "delete": "Delete",
    "end": "End",
    "enter": "Enter",
    "esc": "Escape",
    "home": "Home",
    "insert": "Insert",
    "option": "Alt",
    "pagedown": "PageDown",
    "pageup": "PageUp",
    "shift": "Shift",
    "space": " ",
    "super": "Meta",
    "tab": "Tab",
    "win": "Meta",
}

class BasePlaywrightComputer:
    environment: Literal["browser"] = "browser"
    dimensions = (1024, 768)

    def __init__(self):
        self._playwright = None
        self._browser = None
        self._page = None
        self._code_buffer = []

    async def __aenter__(self):
        # Start Playwright, then get a browser and page via the subclass method
        self._playwright = await async_playwright().start()
        self._browser, self._page = await self._get_browser_and_page()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    async def _get_browser_and_page(self) -> tuple[Browser, Page]:
        """Subclasses must override this method to return (browser, page)."""
        raise NotImplementedError


    async def copy_text_from_page(self) -> str:
        """Extracts all visible text from the current webpage."""
        if not self._page:
            return ""
        return await self._page.evaluate("document.body.innerText")


    # async def get_current_url(self) -> str:
    #     if not self._page:
    #         return ""
    #     # page.url is usually simpler, but we'll mimic your evaluate approach:
    #     return await self._page.evaluate("window.location.href")
    async def get_current_url(self) -> str:
        """Returns the full current URL of the active page."""
        if not self._page:
            return ""
        return self._page.url  # Playwright's built-in property for full URLs


    async def screenshot(self) -> str:
        png_bytes = await self._page.screenshot(full_page=False)
        return base64.b64encode(png_bytes).decode("utf-8")

    async def click(self, x: int, y: int, button: str = "left") -> None:
  
        if button == "wheel":
            await self._page.mouse.click(x, y, button="middle")
        else:
            await self._page.mouse.click(x, y, button=button)
            ############code for handling new tab
            # initial_tabs = self._page.context.pages  # Store tabs before click
            # print(f"Current tabs: {len(initial_tabs)}")
    
            # await self._page.mouse.click(x, y, button=button)
            # await asyncio.sleep(1)  # Allow new tab to open
    
            # updated_tabs = self._page.context.pages  # Get all tabs after click
            # print(f"Tabs after click: {len(updated_tabs)}")
    
            # # Method 2: Check for a new tab manually
            # if len(updated_tabs) > len(initial_tabs):
            #     new_tab = updated_tabs[-1]  # Last opened tab is the new one
            #     await new_tab.bring_to_front()
            #     self._page = new_tab
            #     print("Switched to new tab.")
            


    async def double_click(self, x: int, y: int) -> None:
        await self._page.mouse.dblclick(x, y)

    async def scroll(self, x: int, y: int, scroll_x: int, scroll_y: int) -> None:
        await self._page.mouse.move(x, y)
        try:
            await self._page.mouse.wheel(delta_x=scroll_x, delta_y=scroll_y)
            await asyncio.sleep(0.5)
        except Exception as e:
            print(f"⚠️ Mouse wheel scrolling failed: {e}. Using JavaScript fallback.")
            await self._page.evaluate(f"window.scrollBy({scroll_x}, {scroll_y})")
            await asyncio.sleep(0.5)

    # async def type(self, text: str) -> None:
    #     with open("code.txt", "a") as code_file:
    #         code_file.write(text)
    #         code_file.write("\n")
    #     await self._page.keyboard.type(text)
    async def type(self, text: str) -> None:
        self._code_buffer.append(text)
        await self._page.keyboard.type(text)

    def get_code_buffer(self) -> str:
        return "\n".join(self._code_buffer)

    async def wait(self, ms: int = 1000) -> None:
        await asyncio.sleep(ms / 1000)

    async def move(self, x: int, y: int) -> None:
        await self._page.mouse.move(x, y)

    async def keypress(self, keys: List[str]) -> None:
        mapped_keys = [CUA_KEY_TO_PLAYWRIGHT_KEY.get(key.lower(), key) for key in keys]
    
        modifier_keys = {"Control", "Alt", "Shift", "Meta"}
        keys_to_hold = [key for key in mapped_keys if key in modifier_keys]
        normal_keys = [key for key in mapped_keys if key not in modifier_keys]
    
        # Detect "Ctrl + Tab" and switch to the next tab
        if "Control" in keys_to_hold and "Tab" in normal_keys:
            pages = self._page.context.pages  # Get all open tabs
            current_index = pages.index(self._page)  # Find the current tab index
            next_index = (current_index + 1) % len(pages)  # Loop back if last tab
            await pages[next_index].bring_to_front()  # Switch to next tab
            return  # Stop further key processing
    
        try:
            for key in keys_to_hold:
                await self._page.keyboard.down(key)
            for key in normal_keys:
                await self._page.keyboard.press(key)
        finally:
            for key in keys_to_hold:
                await self._page.keyboard.up(key)


    # async def drag(self, path: List[List[int]]) -> None:
    #     if not path:
    #         return
    #     await self._page.mouse.move(*path[0])
    #     await self._page.mouse.down()
    #     for px, py in path[1:]:
    #         await self._page.mouse.move(px, py)
    #     await self._page.mouse.up()
    async def drag(self, path: List) -> None:
        if not path:
            return
        start = path[0]
        if isinstance(start, dict):
            x, y = start['x'], start['y']
        elif isinstance(start, (list, tuple)):
            x, y = start[0], start[1]
        else:
            raise Exception("path[0] has unknown format, expected list, tuple, or dict")
        await self._page.mouse.move(x, y)
        await self._page.mouse.down()
        for pt in path[1:]:
            if isinstance(pt, dict):
                px, py = pt['x'], pt['y']
            else:
                px, py = pt[0], pt[1]
            await self._page.mouse.move(px, py)
        await self._page.mouse.up()

    async def goto(self, url: str) -> None:
        await self._page.goto(url)

    async def back(self) -> None:
        await self._page.go_back()


    async def copy_text_from_selector(self, selector: str, timeout: int = 10000) -> str:
        if not self._page:
            raise Exception("No page available.")
        await self._page.wait_for_selector(selector, timeout=timeout)
        try:
            text_content = await self._page.eval_on_selector(selector, "el => el.innerText")
        except:
            text_content = await self._page.evaluate("el => el.innerText", await self._page.query_selector(selector))

        return text_content


