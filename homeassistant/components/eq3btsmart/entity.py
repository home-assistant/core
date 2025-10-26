"""Base class for all eQ-3 entities."""

from typing import Any

from eq3btsmart import Eq3Exception
from eq3btsmart.const import Eq3Event

from homeassistant.core import callback
from homeassistant.helpers.device_registry import (
    CONNECTION_BLUETOOTH,
    DeviceInfo,
    format_mac,
)
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity
from homeassistant.util import slugify

from . import Eq3ConfigEntry
from .const import (
    DEVICE_MODEL,
    MANUFACTURER,
    SIGNAL_THERMOSTAT_CONNECTED,
    SIGNAL_THERMOSTAT_DISCONNECTED,
)


class Eq3Entity(Entity):
    """Base class for all eQ-3 entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        entry: Eq3ConfigEntry,
        unique_id_key: str | None = None,
    ) -> None:
        """Initialize the eq3 entity."""

        self._eq3_config = entry.runtime_data.eq3_config
        self._thermostat = entry.runtime_data.thermostat
        self._attr_device_info = DeviceInfo(
            name=slugify(self._eq3_config.mac_address),
            manufacturer=MANUFACTURER,
            model=DEVICE_MODEL,
            connections={(CONNECTION_BLUETOOTH, self._eq3_config.mac_address)},
        )
        suffix = f"_{unique_id_key}" if unique_id_key else ""
        self._attr_unique_id = f"{format_mac(self._eq3_config.mac_address)}{suffix}"

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""

        self._thermostat.register_callback(
            Eq3Event.DEVICE_DATA_RECEIVED, self._async_on_device_updated
        )
        self._thermostat.register_callback(
            Eq3Event.STATUS_RECEIVED, self._async_on_status_updated
        )
        self._thermostat.register_callback(
            Eq3Event.SCHEDULE_RECEIVED, self._async_on_status_updated
        )

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

        self._thermostat.unregister_callback(
            Eq3Event.DEVICE_DATA_RECEIVED, self._async_on_device_updated
        )
        self._thermostat.unregister_callback(
            Eq3Event.STATUS_RECEIVED, self._async_on_status_updated
        )
        self._thermostat.unregister_callback(
            Eq3Event.SCHEDULE_RECEIVED, self._async_on_status_updated
        )

    @callback
    def _async_on_status_updated(self, data: Any) -> None:
        """Handle updated status from the thermostat."""

        self.async_write_ha_state()

    @callback
    def _async_on_device_updated(self, data: Any) -> None:
        """Handle updated device data from the thermostat."""

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

    @property
    def available(self) -> bool:
        """Whether the entity is available."""

        try:
            _ = self._thermostat.status
        except Eq3Exception:
            return False

        return self._attr_available
