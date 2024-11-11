"""Base class for all eQ-3 entities."""

from abc import ABC

from homeassistant.core import callback
from homeassistant.helpers.device_registry import (
    CONNECTION_BLUETOOTH,
    DeviceInfo,
    format_mac,
)
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import UndefinedType
from homeassistant.util import slugify

from . import Eq3ConfigEntry
from .const import (
    DEVICE_MODEL,
    MANUFACTURER,
    SIGNAL_THERMOSTAT_CONNECTED,
    SIGNAL_THERMOSTAT_DISCONNECTED,
)


class Eq3Entity(Entity, ABC):
    """Base class for all eQ-3 entities."""

    _attr_has_entity_name = True

    def __init__(self, entry: Eq3ConfigEntry) -> None:
        """Initialize the eq3 entity."""

        self._eq3_config = entry.runtime_data.eq3_config
        self._thermostat = entry.runtime_data.thermostat
        self._attr_device_info = DeviceInfo(
            name=slugify(self._eq3_config.mac_address),
            manufacturer=MANUFACTURER,
            model=DEVICE_MODEL,
            connections={(CONNECTION_BLUETOOTH, self._eq3_config.mac_address)},
        )

    @property
    def unique_id(self) -> str | None:
        """Return a unique ID."""

        return format_mac(self._eq3_config.mac_address) + (
            "_" + self.name
            if not isinstance(self.name, UndefinedType) and self.name
            else ""
        )

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""

        self._thermostat.register_update_callback(self._async_on_updated)

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{SIGNAL_THERMOSTAT_DISCONNECTED}_{self._eq3_config.mac_address}",
                self._async_on_disconnected,
            )
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{SIGNAL_THERMOSTAT_CONNECTED}_{self._eq3_config.mac_address}",
                self._async_on_connected,
            )
        )

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""

        self._thermostat.unregister_update_callback(self._async_on_updated)

    def _async_on_updated(self) -> None:
        """Handle updated data from the thermostat."""

        self.async_write_ha_state()

    @callback
    def _async_on_disconnected(self) -> None:
        """Handle disconnection from the thermostat."""

        self._attr_available = False
        self.async_write_ha_state()

    @callback
    def _async_on_connected(self) -> None:
        """Handle connection to the thermostat."""

        self._attr_available = True
        self.async_write_ha_state()
