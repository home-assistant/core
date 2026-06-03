"""Coordinator for Aqvify integration."""

from dataclasses import dataclass
from datetime import timedelta
import logging

from aiohttp import ClientResponseError
from pyaqvify import AqvifyAPI, AqvifyDeviceData, AqvifyDevices

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(seconds=60)

type AqvifyConfigEntry = ConfigEntry[AqvifyCoordinator]


@dataclass
class AqvifyDeviceInfo:
    """Data about the Aqvify device."""

    device_key: str
    device_name: str


@dataclass
class AqvifyCoordinatorData:
    """Data class for storing coordinator data."""

    account_id: str
    devices: AqvifyDevices
    device_data: dict[str, AqvifyDeviceData]


class AqvifyCoordinator(DataUpdateCoordinator[AqvifyCoordinatorData]):
    """Data update coordinator for Aqvify devices."""

    config_entry: AqvifyConfigEntry
    device_info: AqvifyDeviceInfo

    def __init__(self, hass: HomeAssistant, entry: AqvifyConfigEntry) -> None:
        """Initialize the Aqvify data update coordinator."""
        super().__init__(
            hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
            config_entry=entry,
        )

        self.api_client = AqvifyAPI(
            entry.data[CONF_API_KEY], websession=async_get_clientsession(hass)
        )

    async def _async_update_data(self) -> AqvifyCoordinatorData:
        """Fetch device state."""
        try:
            _data = await self.api_client.async_get_devices()
            devices = AqvifyDevices(_data)
        except ClientResponseError as err:
            raise UpdateFailed(f"Error communicating with device: {err}") from err
        except TimeoutError as err:
            raise UpdateFailed(f"Unexpected response: {err}") from err

        device_data = {}
        try:
            device_key = "AQ20282"
            _data = await self.api_client.async_get_device_latest_data(device_key)
            device_data[device_key] = AqvifyDeviceData(_data)
        except ClientResponseError as err:
            raise UpdateFailed(f"Error communicating with device: {err}") from err
        except TimeoutError as err:
            raise UpdateFailed(f"Unexpected response: {err}") from err

        return AqvifyCoordinatorData(
            account_id="example_account_id", devices=devices, device_data=device_data
        )
