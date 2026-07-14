import logging

import aiohttp

INFO_URL = "is.xml"
DATA_URL = "fresh.xml"
SETTINGS_URL = "settings.xml"
SET_URL = "set.xml"

_LOGGER = logging.getLogger(__name__)


class PapouchApiClient:
    """API client for communicating with a device."""

    def __init__(self, ip_address: str, session: aiohttp.ClientSession) -> None:
        """Constructor for API client."""
        self.base_url = f"http://{ip_address}/"
        self.session = session

    async def _fetch(self, endpoint: str) -> str:
        async with self.session.get(self.base_url + endpoint) as response:
            response.raise_for_status()
            return await response.text()

    async def fetch_info(self) -> str:
        """Fetching information about a device."""
        return await self._fetch(INFO_URL)

    async def fetch_data(self) -> str:
        """Fetching data about a device."""
        return await self._fetch(DATA_URL)

    async def fetch_settings(self) -> str:
        """Fetching settings about a device."""
        return await self._fetch(SETTINGS_URL)

    async def send_command(
        self, cmd_type: str, output_id: str, time: int | None = None
    ) -> None:
        """Send a GET command to the Quido device."""
        params = {"type": cmd_type, "id": output_id}
        if time:
            params["time"] = time

        async with self.session.get(self.base_url + SET_URL, params=params) as response:
            if response.status != 200:
                _LOGGER.error("Failed to send command to Quido: %s", response.status)
        # TODO: maybe Quido will send message that status will be 0
