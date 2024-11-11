"""Base class for all eQ-3 entities."""

from dataclasses import dataclass

from homeassistant.core import callback
from homeassistant.helpers.device_registry import (
    CONNECTION_BLUETOOTH,
    DeviceInfo,
    format_mac,
)
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.util import slugify

from . import Eq3ConfigEntry
from .const import (
    DEVICE_MODEL,
    MANUFACTURER,
    SIGNAL_THERMOSTAT_CONNECTED,
    SIGNAL_THERMOSTAT_DISCONNECTED,
)


@dataclass(frozen=True, kw_only=True)
class Eq3EntityDescription(EntityDescription):
    """Entity description for eQ-3 devices."""

    always_available: bool = False
    unique_id_key: str | None = None


class Eq3Entity(Entity):
    """Base class for all eQ-3 entities."""

    _attr_has_entity_name = True

    def __init__(
        self, entry: Eq3ConfigEntry, entity_description: Eq3EntityDescription
    ) -> None:
        """Initialize the eq3 entity."""

        self.entity_description: Eq3EntityDescription = entity_description
        super().__init__()

        self._eq3_config = entry.runtime_data.eq3_config
        self._thermostat = entry.runtime_data.thermostat
        self._attr_device_info = DeviceInfo(
            name=slugify(self._eq3_config.mac_address),
            manufacturer=MANUFACTURER,
            model=DEVICE_MODEL,
            connections={(CONNECTION_BLUETOOTH, self._eq3_config.mac_address)},
        )
        suffix = (
            f"_{entity_description.unique_id_key}"
            if entity_description.unique_id_key
            else ""
        )
        self._attr_unique_id = f"{format_mac(self._eq3_config.mac_address)}{suffix}"

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

        if not self.entity_description.always_available:
            self._attr_available = False
        self.async_write_ha_state()

    @callback
    def _async_on_connected(self) -> None:
        """Handle connection to the thermostat."""

        if not self.entity_description.always_available:
            self._attr_available = True
        self.async_write_ha_state()
