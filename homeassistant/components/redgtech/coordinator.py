import logging
import aiohttp
from datetime import timedelta
from typing import List, Optional
from dataclasses import dataclass
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ON, STATE_OFF, CONF_ACCESS_TOKEN
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.exceptions import HomeAssistantError
from redgtech_api import RedgtechAPI
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
_LOGGER.debug("Coordinator for Redgtech is being initialized.")

@dataclass
class RedgtechDevice:
    """Representation of a Redgtech device."""
    id: str
    name: str
    state: str
    device_type: str = "switch"

class RedgtechDataUpdateCoordinator(DataUpdateCoordinator [List[RedgtechDevice]]):
    """Coordinator to manage fetching data from the Redgtech API."""

    def __init__(self, hass: HomeAssistant, config_entry: Optional[ConfigEntry] = None):
        """Initialize the coordinator."""
        self.api = RedgtechAPI()
        self.access_token = config_entry.data[CONF_ACCESS_TOKEN] if config_entry else None

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=5),
            config_entry=config_entry
        )

    async def login(self, email: str, password: str) -> str:
        """Login to the Redgtech API and return the access token."""
        try:
            access_token = await self.api.login(email, password)
            self.access_token = access_token
            return access_token
        except Exception as e:
            raise HomeAssistantError("Login failed")

    async def _async_update_data(self) -> List[RedgtechDevice]:
        """Fetch data from the API."""
        _LOGGER.debug("Fetching data from Redgtech API")
        try:
            data = await self.api.get_data(self.access_token)
        except Exception as e:
            raise UpdateFailed(f"Error fetching data: {e}")

        devices: List[RedgtechDevice] = []

        for item in data["boards"]:
            device = RedgtechDevice(
            id=item['endpointId'],
            name=item["friendlyName"],
            state=STATE_ON if item["value"] else STATE_OFF
            )
            _LOGGER.debug("Processing device: %s", device)
            devices.append(device)

        return devices

    async def set_device_state(self, device_id: str, state: str):
        """Set the state of a device."""
        success = await self.api.set_switch_state(device_id, state, self.access_token)
        if success:
            await self.async_request_refresh()
        else:
            raise HomeAssistantError(f"Failed to set state for {device_id}")