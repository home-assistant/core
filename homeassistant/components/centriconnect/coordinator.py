"""Coordinator for CentriConnect/MyPropane API integration.

Responsible for polling the device API endpoint and normalizing data for entities.
"""

from dataclasses import dataclass
from datetime import timedelta
import logging

from aiocentriconnect import CentriConnect, Tank
from aiocentriconnect.exceptions import CentriConnectConnectionError, CentriConnectError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE_ID, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

COORDINATOR_NAME = f"{DOMAIN} Coordinator"
# Maximum update frequency is every 6 hours. The API will return 429 Too Many Requests if polled frequently.
# The device updates its data every 8-12 hours, so there's no need to poll more frequently.
UPDATE_INTERVAL = timedelta(hours=6)

type CentriConnectConfigEntry = ConfigEntry[CentriConnectCoordinator]


@dataclass
class CentriConnectDeviceInfo:
    """Data about the CentriConnect device."""

    device_id: str
    device_name: str
    hardware_version: str
    lte_version: str
    tank_size: int
    tank_size_unit: str


class CentriConnectCoordinator(DataUpdateCoordinator[Tank]):
    """Data update coordinator for CentriConnect/MyPropane devices."""

    config_entry: CentriConnectConfigEntry
    device_info: CentriConnectDeviceInfo

    def __init__(self, hass: HomeAssistant, entry: CentriConnectConfigEntry) -> None:
        """Initialize the CentriConnect data update coordinator."""
        super().__init__(
            hass,
            logger=_LOGGER,
            name=COORDINATOR_NAME,
            update_interval=UPDATE_INTERVAL,
            config_entry=entry,
        )

        self.api_client = CentriConnect(
            entry.data[CONF_USERNAME],
            entry.data[CONF_DEVICE_ID],
            entry.data[CONF_PASSWORD],
            session=async_get_clientsession(hass),
        )

    async def _async_setup(self) -> None:
        try:
            tank_data = await self.api_client.async_get_tank_data()
            self.device_info = CentriConnectDeviceInfo(
                device_id=tank_data.device_id,
                device_name=tank_data.device_name,
                hardware_version=tank_data.hardware_version,
                lte_version=tank_data.lte_version,
                tank_size=tank_data.tank_size,
                tank_size_unit=tank_data.tank_size_unit,
            )
        except CentriConnectError as err:
            raise ConfigEntryNotReady("Could not fetch device info") from err

    async def _async_update_data(self) -> Tank:
        """Fetch device state."""
        try:
            state = await self.api_client.async_get_tank_data()
        except CentriConnectConnectionError as err:
            raise UpdateFailed(f"Error communicating with device: {err}") from err
        except CentriConnectError as err:
            raise UpdateFailed(f"Unexpected response: {err}") from err
        return state
