"""Base scraper using Playwright for dynamic site rendering."""

import asyncio
import os
import platform
import shutil
from playwright.async_api import async_playwright
from datetime import date, timedelta

if platform.system() == "Darwin":
    _CHROME_PROFILE_SRC = os.path.expanduser(
        "~/Library/Application Support/Google/Chrome/Default"
    )
    _CHROME_PROFILE_TMP = os.path.expanduser("~/Library/Caches/chrome_pw_profile")
else:
    _CHROME_PROFILE_SRC = os.path.expandvars(
        r"%LOCALAPPDATA%\Google\Chrome\User Data\Default"
    )
    _CHROME_PROFILE_TMP = os.path.expandvars(
        r"%LOCALAPPDATA%\Temp\chrome_pw_profile"
    )


def _copy_chrome_profile(dest: str = _CHROME_PROFILE_TMP) -> bool:
    """Copy Chrome profile to dest dir (skipping locked files) for Zscaler session."""
    dst = os.path.join(dest, "Default")
    if os.path.exists(dest):
        shutil.rmtree(dest, ignore_errors=True)
    os.makedirs(dst, exist_ok=True)

    def _copy_dir(s, d):
        os.makedirs(d, exist_ok=True)
        for item in os.listdir(s):
            ss, dd = os.path.join(s, item), os.path.join(d, item)
            try:
                if os.path.isdir(ss):
                    _copy_dir(ss, dd)
                else:
                    shutil.copy2(ss, dd)
            except Exception:
                pass

    if os.path.isdir(_CHROME_PROFILE_SRC):
        _copy_dir(_CHROME_PROFILE_SRC, dst)
        # Some Chrome installs expect this at the user-data root.
        local_state = os.path.join(os.path.dirname(_CHROME_PROFILE_SRC), "Local State")
        if os.path.isfile(local_state):
            try:
                shutil.copy2(local_state, os.path.join(dest, "Local State"))
            except Exception:
                pass
        return True
    return False


class BaseScraper:
    """Base class for web scrapers."""

    def __init__(self, venue_key: str, venue_url: str):
        self.venue_key = venue_key  # attraction identifier (e.g. 'esb', 'edge')
        self.venue_url = venue_url
        self.browser = None
        self.context = None
        self._playwright = None
        self._profile_tmp = None

    async def start_browser(self):
        """Launch real Chrome with headless=new so Ventrata checkout widget loads.

        GTM blocks the Ventrata widget for HeadlessChrome (old headless exposes itself
        via Client Hints UA). Using channel=chrome + --headless=new + disabling the
        AutomationControlled blink feature makes the browser appear non-headless to
        third-party scripts like Ventrata's checkout.js.
        """
        self._playwright = await async_playwright().start()
        _STEALTH_ARGS = [
            "--disable-blink-features=AutomationControlled",
            "--headless=new",
        ]
        try:
            self.browser = await self._playwright.chromium.launch(
                channel="chrome",
                headless=True,
                args=_STEALTH_ARGS,
            )
            self.context = await self.browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
                ignore_https_errors=True,
            )
            return
        except Exception as e:
            print(f"  [{self.venue_key}] WARNING: real Chrome launch failed, falling back ({e})")

        self.browser = await self._playwright.chromium.launch(headless=True)
        self.context = await self.browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
            ignore_https_errors=True,
        )

    async def new_page(self):
        """Create a new page with stealth patches applied."""
        page = await self.context.new_page()
        try:
            from playwright_stealth import Stealth
            await Stealth().apply_stealth_async(page)
        except ImportError:
            pass
        return page

    async def close(self):
        """Close browser."""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self._playwright:
            await self._playwright.stop()
        if self._profile_tmp:
            shutil.rmtree(self._profile_tmp, ignore_errors=True)
            self._profile_tmp = None

    async def delay(self, seconds=2.5):
        """Respectful delay between requests."""
        await asyncio.sleep(seconds)

    async def run(self, start_date: str, end_date: str) -> list[dict]:
        """Scrape prices for date range. Return list of price dicts."""
        raise NotImplementedError("Subclasses must implement run()")

    @staticmethod
    def date_range(start: str, end: str) -> list[str]:
        """Generate list of dates between start and end (inclusive)."""
        s = date.fromisoformat(start)
        e = date.fromisoformat(end)
        dates = []
        current = s
        while current <= e:
            dates.append(current.isoformat())
            current += timedelta(days=1)
        return dates
