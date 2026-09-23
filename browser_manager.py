import sys
import asyncio
import subprocess
import urllib.request
from pathlib import Path
from typing import Optional, List, Tuple, Dict
from playwright.async_api import async_playwright, Playwright, Browser, BrowserContext, Page, Download
from config import config, AgentConfig
from dom_annotator import DOMAnnotator, DOMElement

class BrowserManager:
    """Manages Playwright lifecycle, browser interactions, screenshots, and downloads."""

    def __init__(self, cfg: Optional[AgentConfig] = None):
        self.cfg = cfg or config
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.downloaded_files: List[Path] = []
        self.current_elements: List[DOMElement] = []
        self._connected_via_cdp: bool = False

    def _check_cdp_available(self, url: str) -> bool:
        """Checks if Chrome DevTools Protocol endpoint is responding."""
        try:
            version_url = f"{url.rstrip('/')}/json/version"
            req = urllib.request.Request(version_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=0.8) as response:
                return response.status == 200
        except Exception:
            return False

    def _is_browser_process_running(self) -> bool:
        """Checks if Brave or Chromium process is currently running on the system."""
        try:
            if sys.platform == "win32":
                res = subprocess.run(["tasklist", "/FI", "IMAGENAME eq brave.exe"], capture_output=True, text=True, check=False)
                return "brave.exe" in res.stdout.lower()
            else:
                res = subprocess.run(["pgrep", "-f", "brave"], capture_output=True, text=True, check=False)
                return bool(res.stdout.strip())
        except Exception:
            return False

    async def start(self) -> None:
        """Starts Playwright, attaching to active Brave via CDP or launching persistent context."""
        self._playwright = await async_playwright().start()

        # Strategy 1: Attach directly to user's running Brave browser via CDP if active
        cdp_endpoint = self.cfg.cdp_url or "http://localhost:9222"
        if self._check_cdp_available(cdp_endpoint):
            print(f"[BrowserManager] Connected directly to your active running Brave browser via {cdp_endpoint}!")
            self._browser = await self._playwright.chromium.connect_over_cdp(cdp_endpoint)
            self._context = self._browser.contexts[0]
            self.page = self._context.pages[0] if self._context.pages else await self._context.new_page()
            self._connected_via_cdp = True
            self.page.on("dialog", lambda dialog: asyncio.create_task(dialog.accept()))
            self.page.on("download", self._handle_download)
            return

        # Strategy 2: Determine user data directory
        target_user_data_dir = None
        if self.cfg.isolated_profile:
            target_user_data_dir = str(self.cfg.persistent_profile_dir)
            print(f"[BrowserManager] Using isolated profile: {target_user_data_dir}")
        elif self.cfg.use_existing_profile:
            brave_running = self._is_browser_process_running()
            if brave_running:
                raise RuntimeError(
                    "\n" + "=" * 70 + "\n"
                    " [!] BRAVE IS CURRENTLY RUNNING AND LOCKING YOUR REAL PROFILE\n"
                    "=" * 70 + "\n"
                    "Your real Brave profile ('Work') is locked by the open Brave window.\n"
                    "Chromium prohibits two independent processes from accessing the same\n"
                    "profile files (Cookies, Logins, Sessions) at the same time.\n\n"
                    "HOW TO FIX:\n"
                    "  1. Run this command to connect directly to your real profile:\n"
                    "     python main.py connect-brave\n"
                    "     (This restarts Brave with remote debugging and restores your tabs)\n\n"
                    "  2. OR close all Brave windows before running the agent.\n\n"
                    "  3. OR pass '--new-profile' if you intentionally want an isolated profile.\n"
                    + "=" * 70
                )
            else:
                target_user_data_dir = self.cfg.brave_user_data_dir
                print(f"[BrowserManager] Launching your real Brave profile ('{self.cfg.profile_name}'): {target_user_data_dir}")


        # Strategy 3: Launch persistent context
        if target_user_data_dir:
            launch_args = [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-infobars",
                f"--profile-directory={self.cfg.profile_name}"
            ]

            self._context = await self._playwright.chromium.launch_persistent_context(
                user_data_dir=target_user_data_dir,
                executable_path=self.cfg.browser_executable,
                headless=self.cfg.headless,
                slow_mo=self.cfg.slow_mo_ms if not self.cfg.headless else 0,
                viewport={"width": self.cfg.viewport_width, "height": self.cfg.viewport_height},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                accept_downloads=True,
                args=launch_args
            )
            self.page = self._context.pages[0] if self._context.pages else await self._context.new_page()
        else:
            # Ephemeral fallback
            self._browser = await self._playwright.chromium.launch(
                headless=self.cfg.headless,
                executable_path=self.cfg.browser_executable,
                slow_mo=self.cfg.slow_mo_ms if not self.cfg.headless else 0
            )
            self._context = await self._browser.new_context(
                viewport={"width": self.cfg.viewport_width, "height": self.cfg.viewport_height},
                accept_downloads=True
            )
            self.page = await self._context.new_page()

        # Auto-dismiss alerts/dialogs
        self.page.on("dialog", lambda dialog: asyncio.create_task(dialog.accept()))
        self.page.on("download", self._handle_download)

    async def _handle_download(self, download: Download) -> None:
        """Saves any downloaded files into config.downloads_dir."""
        target_path = self.cfg.downloads_dir / download.suggested_filename
        await download.save_as(str(target_path))
        self.downloaded_files.append(target_path)
        print(f"[BrowserManager] Saved downloaded file to: {target_path}")

    async def navigate(self, url: str) -> bool:
        """Navigates to the specified URL."""
        if not self.page:
            raise RuntimeError("Browser not started.")

        if not url.startswith("http://") and not url.startswith("https://") and not url.startswith("file://"):
            url = "https://" + url

        try:
            await self.page.goto(url, wait_until="domcontentloaded", timeout=self.cfg.timeout_ms)
            await asyncio.sleep(1.0)
            return True
        except Exception as e:
            print(f"[BrowserManager] Navigation error to {url}: {e}")
            return False

    async def capture_state(self, step_num: int) -> Tuple[bytes, List[DOMElement], Dict[str, str]]:
        """Annotates DOM with Set-of-Marks badges, extracts page summary, takes screenshot, and returns state."""
        if not self.page:
            raise RuntimeError("Browser not started.")

        # 1. Inject visual markers into DOM
        self.current_elements = await DOMAnnotator.annotate_page(self.page)

        # 2. Extract textual page summary (headings + readable content)
        page_summary = await DOMAnnotator.extract_page_summary(self.page)
        await asyncio.sleep(0.15)  # Allow badges to render

        # 3. Capture screenshot with overlays for auditing
        screenshot_path = self.cfg.screenshots_dir / f"step_{step_num:02d}_annotated.png"
        screenshot_bytes = await self.page.screenshot(path=str(screenshot_path), full_page=False)

        # 4. Clean up visual markers so page remains functional for clicking
        await DOMAnnotator.cleanup_annotations(self.page)

        return screenshot_bytes, self.current_elements, page_summary

    async def execute_click(self, element_id: Optional[int], x: Optional[int] = None, y: Optional[int] = None) -> bool:
        """Clicks an element by ID, or self-heals by falling back to coordinates."""
        if not self.page:
            return False

        # Strategy A: Click via data-agent-id selector
        if element_id is not None:
            selector = f"[data-agent-id='{element_id}']"
            try:
                await DOMAnnotator.annotate_page(self.page)
                el = await self.page.query_selector(selector)
                if el and await el.is_visible():
                    await el.scroll_into_view_if_needed(timeout=3000)
                    await el.click(timeout=5000)
                    await DOMAnnotator.cleanup_annotations(self.page)
                    await asyncio.sleep(1.0)
                    return True
                await DOMAnnotator.cleanup_annotations(self.page)
            except Exception as e:
                print(f"[BrowserManager] Selector click failed for ID [{element_id}]: {e}. Attempting self-healing fallback...")

            # Strategy B: Click using known element center coordinates
            matched = next((el for el in self.current_elements if el.id == element_id), None)
            if matched and matched.center_x and matched.center_y:
                try:
                    await self.page.mouse.click(matched.center_x, matched.center_y)
                    await asyncio.sleep(1.0)
                    return True
                except Exception as e:
                    print(f"[BrowserManager] Coordinate fallback click failed: {e}")

        # Strategy C: Direct explicit coordinates
        if x is not None and y is not None:
            try:
                await self.page.mouse.click(x, y)
                await asyncio.sleep(1.0)
                return True
            except Exception as e:
                print(f"[BrowserManager] Explicit coordinate click failed: {e}")

        return False

    async def execute_type(self, element_id: Optional[int], text: str, clear_before: bool = True, press_enter: bool = False) -> bool:
        """Types text into an input field with self-healing."""
        if not self.page:
            return False

        if element_id is not None:
            selector = f"[data-agent-id='{element_id}']"
            try:
                await DOMAnnotator.annotate_page(self.page)
                el = await self.page.query_selector(selector)
                if el and await el.is_visible():
                    await el.scroll_into_view_if_needed(timeout=3000)
                    if clear_before:
                        await el.fill("")
                    await el.type(text, delay=25)
                    if press_enter:
                        await el.press("Enter")
                    await DOMAnnotator.cleanup_annotations(self.page)
                    await asyncio.sleep(1.0)
                    return True
                await DOMAnnotator.cleanup_annotations(self.page)
            except Exception as e:
                print(f"[BrowserManager] Type failed on ID [{element_id}]: {e}. Attempting coordinate click + type fallback...")

            # Fallback: Click center of element coordinates, clear, and type via keyboard
            matched = next((el for el in self.current_elements if el.id == element_id), None)
            if matched and matched.center_x and matched.center_y:
                try:
                    await self.page.mouse.click(matched.center_x, matched.center_y)
                    if clear_before:
                        await self.page.keyboard.press("Control+A")
                        await self.page.keyboard.press("Backspace")
                    await self.page.keyboard.type(text, delay=25)
                    if press_enter:
                        await self.page.keyboard.press("Enter")
                    await asyncio.sleep(1.0)
                    return True
                except Exception as e:
                    print(f"[BrowserManager] Fallback typing failed: {e}")

        # Fallback to direct keyboard typing if no specific element is targeted
        try:
            await self.page.keyboard.type(text, delay=25)
            if press_enter:
                await self.page.keyboard.press("Enter")
            await asyncio.sleep(1.0)
            return True
        except Exception as e:
            print(f"[BrowserManager] Generic keyboard type failed: {e}")
            return False

    async def execute_select_option(self, element_id: int, option_value: str) -> bool:
        """Selects an option in a <select> element."""
        if not self.page:
            return False
        try:
            await DOMAnnotator.annotate_page(self.page)
            el = await self.page.query_selector(f"[data-agent-id='{element_id}']")
            if el:
                await el.select_option(label=option_value)
                await DOMAnnotator.cleanup_annotations(self.page)
                return True
            await DOMAnnotator.cleanup_annotations(self.page)
        except Exception as e:
            print(f"[BrowserManager] Select option failed: {e}")
        return False

    async def execute_scroll(self, direction: str = "down", amount: int = 500) -> bool:
        """Scrolls the page up or down."""
        if not self.page:
            return False
        delta_y = amount if direction == "down" else -amount
        try:
            await self.page.mouse.wheel(0, delta_y)
            await asyncio.sleep(0.8)
            return True
        except Exception as e:
            print(f"[BrowserManager] Scroll failed: {e}")
            return False

    async def execute_press_key(self, key: str) -> bool:
        """Presses a keyboard key like 'Enter', 'Escape', 'ArrowDown'."""
        if not self.page:
            return False
        try:
            await self.page.keyboard.press(key)
            await asyncio.sleep(0.5)
            return True
        except Exception as e:
            print(f"[BrowserManager] Press key failed: {e}")
            return False

    async def wait(self, seconds: float = 2.0) -> bool:
        """Waits for specified duration."""
        await asyncio.sleep(seconds)
        return True

    async def stop(self) -> None:
        """Closes browser context and shuts down Playwright."""
        try:
            if not self._connected_via_cdp:
                if self._context:
                    await self._context.close()
                if self._browser:
                    await self._browser.close()
            if self._playwright:
                await self._playwright.stop()
        except Exception as e:
            print(f"[BrowserManager] Cleanup error: {e}")
