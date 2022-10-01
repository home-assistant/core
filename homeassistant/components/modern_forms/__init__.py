"""The Modern Forms integration."""
from __future__ import annotations

from datetime import timedelta
import logging

from aiomodernforms import (
    ModernFormsConnectionError,
    ModernFormsDevice,
    ModernFormsError,
)
from aiomodernforms.models import Device as ModernFormsDeviceState

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import DOMAIN

SCAN_INTERVAL = timedelta(seconds=5)
PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.LIGHT,
    Platform.FAN,
    Platform.SENSOR,
    Platform.SWITCH,
]
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a Modern Forms device from a config entry."""

    # Create Modern Forms instance for this entry
    coordinator = ModernFormsDataUpdateCoordinator(hass, host=entry.data[CONF_HOST])
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Set up all platforms for this device/entry.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Modern Forms config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        del hass.data[DOMAIN][entry.entry_id]

    if not hass.data[DOMAIN]:
        del hass.data[DOMAIN]

    return unload_ok


def modernforms_exception_handler(func):
    """Decorate Modern Forms calls to handle Modern Forms exceptions.

    A decorator that wraps the passed in function, catches Modern Forms errors,
    and handles the availability of the device in the data coordinator.
    """

    async def handler(self, *args, **kwargs):
        try:
            await func(self, *args, **kwargs)
            self.coordinator.async_update_listeners()

        except ModernFormsConnectionError as error:
            _LOGGER.error("Error communicating with API: %s", error)
            self.coordinator.last_update_success = False
            self.coordinator.async_update_listeners()

        except ModernFormsError as error:
            _LOGGER.error("Invalid response from API: %s", error)

    return handler


class ModernFormsDataUpdateCoordinator(DataUpdateCoordinator[ModernFormsDeviceState]):
    """Class to manage fetching Modern Forms data from single endpoint."""

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        host: str,
    ) -> None:
        """Initialize global Modern Forms data updater."""
        self.modern_forms = ModernFormsDevice(
            host, session=async_get_clientsession(hass)
        )

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )

    async def _async_update_data(self) -> ModernFormsDevice:
        """Fetch data from Modern Forms."""
        try:
            return await self.modern_forms.update(
                full_update=not self.last_update_success
            )
        except ModernFormsError as error:
            raise UpdateFailed(f"Invalid response from API: {error}") from error


class ModernFormsDeviceEntity(CoordinatorEntity[ModernFormsDataUpdateCoordinator]):
    """Defines a Modern Forms device entity."""

    def __init__(
        self,
        *,
        entry_id: str,
        coordinator: ModernFormsDataUpdateCoordinator,
        name: str,
        icon: str | None = None,
        enabled_default: bool = True,
    ) -> None:
        """Initialize the Modern Forms entity."""
        super().__init__(coordinator)
        self._attr_enabled_default = enabled_default
        self._entry_id = entry_id
        self._attr_icon = icon
        self._attr_name = name

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this Modern Forms device."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.data.info.mac_address)},
            name=self.coordinator.data.info.device_name,
            manufacturer="Modern Forms",
            model=self.coordinator.data.info.fan_type,
            sw_version=f"{self.coordinator.data.info.firmware_version} / {self.coordinator.data.info.main_mcu_firmware_version}",
        )
