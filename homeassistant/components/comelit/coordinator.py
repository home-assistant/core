"""Support for Comelit."""

from abc import abstractmethod
from datetime import timedelta
from typing import Any

from aiocomelit import (
    ComeliteSerialBridgeApi,
    ComelitSerialBridgeObject,
    ComelitVedoApi,
    ComelitVedoAreaObject,
    ComelitVedoZoneObject,
    exceptions,
)
from aiocomelit.api import ComelitCommonApi
from aiocomelit.const import BRIDGE, VEDO

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import _LOGGER, DOMAIN


class ComelitBaseCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Base coordinator for Comelit Devices."""

    _hw_version: str
    config_entry: ConfigEntry
    api: ComelitCommonApi

    def __init__(self, hass: HomeAssistant, device: str, host: str) -> None:
        """Initialize the scanner."""

        self._device = device
        self._host = host

        super().__init__(
            hass=hass,
            logger=_LOGGER,
            name=f"{DOMAIN}-{host}-coordinator",
            update_interval=timedelta(seconds=5),
        )
        device_registry = dr.async_get(self.hass)
        device_registry.async_get_or_create(
            config_entry_id=self.config_entry.entry_id,
            identifiers={(DOMAIN, self.config_entry.entry_id)},
            model=device,
            name=f"{device} ({self._host})",
            manufacturer="Comelit",
            hw_version=self._hw_version,
        )

    def platform_device_info(
        self,
        object_class: ComelitVedoZoneObject
        | ComelitVedoAreaObject
        | ComelitSerialBridgeObject,
        object_type: str,
    ) -> dr.DeviceInfo:
        """Set platform device info."""

        return dr.DeviceInfo(
            identifiers={
                (
                    DOMAIN,
                    f"{self.config_entry.entry_id}-{object_type}-{object_class.index}",
                )
            },
            via_device=(DOMAIN, self.config_entry.entry_id),
            name=object_class.name,
            model=f"{self._device} {object_type}",
            manufacturer="Comelit",
            hw_version=self._hw_version,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Update device data."""
        _LOGGER.debug("Polling Comelit %s host: %s", self._device, self._host)
        try:
            await self.api.login()
            return await self._async_update_system_data()
        except (exceptions.CannotConnect, exceptions.CannotRetrieveData) as err:
            raise UpdateFailed(repr(err)) from err
        except exceptions.CannotAuthenticate as err:
            raise ConfigEntryAuthFailed from err

    @abstractmethod
    async def _async_update_system_data(self) -> dict[str, Any]:
        """Class method for updating data."""


class ComelitSerialBridge(ComelitBaseCoordinator):
    """Queries Comelit Serial Bridge."""

    _hw_version = "20003101"
    api: ComeliteSerialBridgeApi

    def __init__(self, hass: HomeAssistant, host: str, port: int, pin: int) -> None:
        """Initialize the scanner."""
        self.api = ComeliteSerialBridgeApi(host, port, pin)
        super().__init__(hass, BRIDGE, host)

    async def _async_update_system_data(self) -> dict[str, Any]:
        """Specific method for updating data."""
        return await self.api.get_all_devices()


class ComelitVedoSystem(ComelitBaseCoordinator):
    """Queries Comelit VEDO system."""

    _hw_version = "VEDO IP"
    api: ComelitVedoApi

    def __init__(self, hass: HomeAssistant, host: str, port: int, pin: int) -> None:
        """Initialize the scanner."""
        self.api = ComelitVedoApi(host, port, pin)
        super().__init__(hass, VEDO, host)

    async def _async_update_system_data(self) -> dict[str, Any]:
        """Specific method for updating data."""
        return await self.api.get_all_areas_and_zones()
