"""Downloader."""
from typing import Any, Optional

import aiohttp


class SmhiDownloader:
    """SmhiDownloader."""

    async def fetch(self, session: aiohttp.ClientSession, url: str) -> Optional[Any]:
        """Fetch data."""
        async with session.get(url) as response:
            if response.status == 200:
                return await response.json()
            return None

    async def download_json(self, url: str) -> Optional[Any]:
        """Download json."""
        async with aiohttp.ClientSession() as session:
            return await self.fetch(session, url)
