"""Coordinator for the LibreNMS integration."""

from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import override

from aiolibrenms import Librenms
from aiolibrenms.const import CONNECT_ERRORS
from aiolibrenms.devices.models import LibrenmsDeviceInfo
from aiolibrenms.exceptions import LibrenmsUnauthenticatedError
from aiolibrenms.system.models import LibrenmsSystemInfo
from yarl import URL

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SSL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass
class LibrenmsCentralData:
    """Data class for storing data from the API."""

    system: LibrenmsSystemInfo
    devices: dict[int, LibrenmsDeviceInfo]


type LibrenmsConfigEntry = ConfigEntry[LibrenmsCentralDataUpdateCoordinator]


class LibrenmsBaseDataUpdateCoordinator[T](DataUpdateCoordinator[T]):
    """Base class to manage fetching LibreNMS data."""

    config_entry: LibrenmsConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: LibrenmsConfigEntry,
        api: Librenms,
        update_interval: timedelta,
    ) -> None:
        """Initialize the data update coordinator."""
        self.api = api
        self.configuration_url = str(
            URL.build(
                scheme="https" if config_entry.data[CONF_SSL] else "http",
                host=config_entry.data[CONF_HOST],
                port=config_entry.data[CONF_PORT],
            )
        )
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=update_interval,
        )


class LibrenmsCentralDataUpdateCoordinator(
    LibrenmsBaseDataUpdateCoordinator[LibrenmsCentralData]
):
    """Coordinator to fetch librenms system data and monitored devices meta data."""

    def __init__(
        self, hass: HomeAssistant, config_entry: LibrenmsConfigEntry, api: Librenms
    ) -> None:
        """Initialize the data update coordinator."""
        super().__init__(
            hass,
            config_entry=config_entry,
            api=api,
            update_interval=timedelta(seconds=60),
        )

    @override
    async def _async_update_data(self) -> LibrenmsCentralData:
        """Update data via internal method."""
        try:
            system = await self.api.system.async_get_system_info()
            devices = await self.api.devices.async_get_devices()
        except LibrenmsUnauthenticatedError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="auth_error",
            ) from err
        except CONNECT_ERRORS as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_error",
                translation_placeholders={"error": str(err)},
            ) from err

        device_reg = dr.async_get(self.hass)
        for device in devices:
            identifier = f"{self.config_entry.entry_id}_{device.device_id}"
            sw_version = device.version
            model = None
            if device.os != "ping":
                if sw_version and (feature := device.features) is not None:
                    sw_version += f" ({feature})"
                model = device.hardware

            device_reg.async_get_or_create(
                config_entry_id=self.config_entry.entry_id,
                identifiers={(DOMAIN, identifier)},
                sw_version=sw_version,
                configuration_url=f"{self.configuration_url}/device/{device.device_id}",
                name=device.display,
                model=model,
                serial_number=device.serial,
            )

        return LibrenmsCentralData(system, {dev.device_id: dev for dev in devices})
