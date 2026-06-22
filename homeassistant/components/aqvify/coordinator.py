"""Coordinator for Aqvify integration."""

from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import override

from aiohttp import ClientResponseError
from pyaqvify import AqvifyAPI, AqvifyAuthException, AqvifyDeviceData, AqvifyDevices

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.device_registry as dr
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
        self.previous_devices: set[str] = set()

    @override
    async def _async_setup(self) -> None:
        """Set up the coordinator."""
        try:
            await self.api_client.async_get_account_id()
        except AqvifyAuthException:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="invalid_api_key",
            ) from None
        except ClientResponseError as err:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="api_error",
                translation_placeholders={
                    "entry": self.config_entry.title,
                },
            ) from err
        except TimeoutError as err:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="api_timeout",
                translation_placeholders={
                    "entry": self.config_entry.title,
                },
            ) from err

    @override
    async def _async_update_data(self) -> AqvifyCoordinatorData:
        """Fetch device state."""
        try:
            devices = await self.api_client.async_get_devices()
        except AqvifyAuthException:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="invalid_api_key",
            ) from None
        except ClientResponseError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="api_error",
                translation_placeholders={
                    "entry": self.config_entry.title,
                },
            ) from err
        except TimeoutError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="api_timeout",
                translation_placeholders={
                    "entry": self.config_entry.title,
                },
            ) from err

        current_devices = set(devices.devices.keys())
        if stale_devices := self.previous_devices - current_devices:
            account_id = self.config_entry.unique_id
            device_registry = dr.async_get(self.hass)
            for device_id in stale_devices:
                device = device_registry.async_get_device(
                    identifiers={(DOMAIN, f"{account_id}_{device_id}")}
                )
                if device:
                    device_registry.async_update_device(
                        device_id=device.id,
                        remove_config_entry_id=self.config_entry.entry_id,
                    )
        self.previous_devices = current_devices

        device_data = {}
        for aqvify_device in devices.devices.values():
            try:
                device_key = str(aqvify_device.device_key)
                device_data[
                    device_key
                ] = await self.api_client.async_get_device_latest_data(device_key)
            except AqvifyAuthException:
                raise ConfigEntryAuthFailed(
                    translation_domain=DOMAIN,
                    translation_key="invalid_api_key",
                ) from None
            except ClientResponseError as err:
                raise UpdateFailed(
                    translation_domain=DOMAIN,
                    translation_key="api_error",
                    translation_placeholders={
                        "entry": self.config_entry.title,
                    },
                ) from err
            except TimeoutError as err:
                raise UpdateFailed(
                    translation_domain=DOMAIN,
                    translation_key="api_timeout",
                    translation_placeholders={
                        "entry": self.config_entry.title,
                    },
                ) from err

        return AqvifyCoordinatorData(
            devices=devices,
            device_data=device_data,
        )

    def async_add_devices(self, added_devices: set[str]) -> tuple[set[str], set[str]]:
        """Return newly discovered device keys and the full current device set."""

        current_devices = set(self.data.devices.devices)
        new_devices: set[str] = current_devices - added_devices
        return (new_devices, current_devices)
