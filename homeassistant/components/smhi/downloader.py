"""SmhiDownloader Class."""
from typing import Any, Optional

import aiohttp


class SmhiDownloader:
    """A downloader class for fetching JSON data from a specified URL.

    This class uses asynchronous HTTP requests to fetch data, particularly
    focusing on JSON responses.

    Attributes:
        None

    Methods:
        fetch(session: aiohttp.ClientSession, url: str) -> Optional[Any]:
            Fetches data from the specified URL using the given aiohttp session.

        download_json(url: str) -> Optional[Any]:
            Creates an aiohttp session and uses it to download JSON data from the specified URL.
    """

    async def fetch(self, session: aiohttp.ClientSession, url: str) -> Optional[Any]:
        """Asynchronously fetches data from a specified URL using a given aiohttp ClientSession.

        The method sends an HTTP GET request to the specified URL. If the response status
        code is 200 (OK), it attempts to parse the response as JSON and return the parsed data.
        If the response status is not 200, it returns None.

        Args:
            session (aiohttp.ClientSession): The aiohttp session to be used for making the request.
            url (str): The URL to fetch the data from.

        Returns:
            Optional[Any]: Parsed JSON data from the response if the status is 200, otherwise None.
        """
        async with session.get(url) as response:
            if response.status == 200:
                return await response.json()
            return None

    async def download_json(self, url: str) -> Optional[Any]:
        """Asynchronously downloads JSON data from a specified URL.

        This method creates a new aiohttp ClientSession and uses it to fetch data from the
        specified URL. The actual fetching is delegated to the `fetch` method. If the fetched
        data is JSON, it returns the parsed JSON. Otherwise, it returns None.

        Args:
            url (str): The URL to download the JSON data from.

        Returns:
            Optional[Any]: Parsed JSON data from the fetched URL if successful, otherwise None.
        """
        async with aiohttp.ClientSession() as session:
            return await self.fetch(session, url)

    async def fetch_binary(
        self, session: aiohttp.ClientSession, url: str
    ) -> Optional[bytes]:
        """Asynchronously fetches binary data from a specified URL using a given aiohttp ClientSession.

        Args:
            session (aiohttp.ClientSession): The aiohttp session to be used for making the request.
            url (str): The URL to fetch the data from.

        Returns:
            Optional[bytes]: Binary data from the response if the status is 200, otherwise None.
        """
        async with session.get(url) as response:
            if response.status == 200:
                return await response.read()
            return None
