"""The Modern Forms integration."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
import logging
from typing import Any, Concatenate

from aiomodernforms import ModernFormsConnectionError, ModernFormsError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ModernFormsDataUpdateCoordinator

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.FAN,
    Platform.LIGHT,
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


def modernforms_exception_handler[
    _ModernFormsDeviceEntityT: ModernFormsDeviceEntity,
    **_P,
](
    func: Callable[Concatenate[_ModernFormsDeviceEntityT, _P], Any],
) -> Callable[Concatenate[_ModernFormsDeviceEntityT, _P], Coroutine[Any, Any, None]]:
    """Decorate Modern Forms calls to handle Modern Forms exceptions.

    A decorator that wraps the passed in function, catches Modern Forms errors,
    and handles the availability of the device in the data coordinator.
    """

    async def handler(
        self: _ModernFormsDeviceEntityT, *args: _P.args, **kwargs: _P.kwargs
    ) -> None:
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


class ModernFormsDeviceEntity(CoordinatorEntity[ModernFormsDataUpdateCoordinator]):
    """Defines a Modern Forms device entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        *,
        entry_id: str,
        coordinator: ModernFormsDataUpdateCoordinator,
        enabled_default: bool = True,
    ) -> None:
        """Initialize the Modern Forms entity."""
        super().__init__(coordinator)
        self._attr_enabled_default = enabled_default
        self._entry_id = entry_id

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this Modern Forms device."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.data.info.mac_address)},
            name=self.coordinator.data.info.device_name,
            manufacturer="Modern Forms",
            model=self.coordinator.data.info.fan_type,
            sw_version=(
                f"{self.coordinator.data.info.firmware_version} /"
                f" {self.coordinator.data.info.main_mcu_firmware_version}"
            ),
        )
