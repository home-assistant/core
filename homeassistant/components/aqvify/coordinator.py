"""Coordinator for Aqvify integration."""

from dataclasses import dataclass
from datetime import timedelta
import logging

from aiohttp import ClientResponseError
from pyaqvify import AqvifyAPI, AqvifyAuthException, AqvifyDeviceData, AqvifyDevices

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(seconds=60)

type AqvifyConfigEntry = ConfigEntry[AqvifyCoordinator]


@dataclass
class AqvifyCoordinatorData:
    """Data class for storing coordinator data."""

    devices: AqvifyDevices
    device_data: dict[str, AqvifyDeviceData]


class AqvifyCoordinator(DataUpdateCoordinator[AqvifyCoordinatorData]):
    """Data update coordinator for Aqvify devices."""

    config_entry: AqvifyConfigEntry

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

    async def _async_setup(self) -> None:
        """Set up the coordinator."""
        try:
            await self.api_client.async_get_account_id()
        except AqvifyAuthException as err:
            raise ConfigEntryAuthFailed(f"Invalid Aqvify API key: {err}") from err
        except (ClientResponseError, TimeoutError) as err:
            raise ConfigEntryNotReady(
                f"Failed to connect to Aqvify API: {err}"
            ) from err

    async def _async_update_data(self) -> AqvifyCoordinatorData:
        """Fetch device state."""
        try:
            devices = await self.api_client.async_get_devices()
        except AqvifyAuthException as err:
            raise ConfigEntryAuthFailed(f"Invalid Aqvify API key: {err}") from err
        except ClientResponseError as err:
            raise UpdateFailed(f"Error communicating with Aqvify API: {err}") from err
        except TimeoutError as err:
            raise UpdateFailed(f"Timeout communicating with Aqvify API: {err}") from err

        device_data = {}
        for device in devices.devices.values():
            try:
                device_key = str(device.device_key)
                device_data[
                    device_key
                ] = await self.api_client.async_get_device_latest_data(device_key)
            except AqvifyAuthException as err:
                raise ConfigEntryAuthFailed(f"Invalid Aqvify API key: {err}") from err
            except ClientResponseError as err:
                raise UpdateFailed(
                    f"Error communicating with Aqvify API: {err}"
                ) from err
            except TimeoutError as err:
                raise UpdateFailed(
                    f"Timeout communicating with Aqvify API: {err}"
                ) from err

        return AqvifyCoordinatorData(
            devices=devices,
            device_data=device_data,
        )
