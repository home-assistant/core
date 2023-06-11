"""The Midea ccm15 AC controller."""
import asyncio
import logging

import aiohttp
import httpx
import xmltodict

from .climate import CCM15Climate
from .const import BASE_URL, CONF_URL_STATUS, DEFAULT_INTERVAL, DEFAULT_TIMEOUT

_LOGGER = logging.getLogger(__name__)

CONST_MODE_MAP = {
    "off": 0,
    "cool": 2,
    "dry": 3,
    "fan_only": 4,
    "heat": 6,
}

CONST_FAN_MAP = {
    "auto": 0,
    "high": 3,
    "med": 2,
    "low": 1,
}


class CCM15Coordinator:
    """Class to coordinate multiple CCM15Climate devices."""

    def __init__(self, host: str, port: int, interval: int = DEFAULT_INTERVAL) -> None:
        """Initialize the coordinator."""
        self._host = host
        self._port = port
        self._interval = interval
        self._ac_devices: dict[int, CCM15Climate] = {}
        self._ac_data: dict[int, dict[str, int]] = {}
        self._running = False

    async def start(self):
        """Start polling."""
        self._running = True
        while self._running:
            await self.poll_status_async()
            await asyncio.sleep(self._interval)

    def stop(self):
        """Stop polling."""
        self._running = False

    def add_device(self, device):
        """Add a new device to the coordinator."""
        self._ac_devices[device.ac_id] = device

    def remove_device(self, ac_id):
        """Remove a device from the coordinator."""
        if ac_id in self._ac_devices:
            del self._ac_devices[ac_id]

    async def poll_status_async(self):
        """Get the current status of all AC devices."""
        try:
            url = BASE_URL.format(self._host, self._port, CONF_URL_STATUS)
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=DEFAULT_TIMEOUT)
        except httpx.RequestError as err:
            _LOGGER.exception("Exception retrieving API data %s", err)
        else:
            doc = xmltodict.parse(response.text)
            data = doc["response"]
            for ac_name, ac_binary in data.items():
                if len(ac_binary) > 1:
                    ac_state = self.get_status_from(ac_binary)
                if ac_state:
                    if ac_name in self._ac_devices:
                        self._ac_devices[ac_name].update_with_acdata(ac_state)
                    else:
                        _LOGGER.debug("AC device %s not registered", ac_name)

    def get_status_from(self, ac_binary: str) -> dict[str, int]:
        """Parse the binary data and return a dictionary with AC status."""
        # Parse data from the binary stream
        return {}

    def update_climates_from_status(self, ac_status):
        """Update climate devices from the latest status."""
        for ac_name in ac_status:
            if not ac_status[ac_name]:
                # Ignore empty entries
                continue
            if ac_name not in self._ac_devices:
                # Create new climate entity if it doesn't exist
                int(ac_status[ac_name]["id"])
                self._ac_devices[ac_name] = CCM15Climate(
                    ac_name, self._host, self._port, self
                )
                _LOGGER.debug("New climate created: %s", ac_name)
            else:
                # Update existing climate entity
                self._ac_devices[ac_name].updateWithAcdata(ac_status[ac_name])
                _LOGGER.debug("Climate updated: %s", ac_name)

    async def async_test_connection(self):
        """Test the connection to the CCM15 device."""
        url = f"http://{self._host}:{self._port}/{CONF_URL_STATUS}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        return True
                    return False
        except (aiohttp.ClientError, asyncio.TimeoutError):
            return False
