"""Base class for all eQ-3 entities."""

from eq3btsmart.models import Status

from homeassistant.core import callback
from homeassistant.helpers.device_registry import (
    CONNECTION_BLUETOOTH,
    DeviceInfo,
    format_mac,
)
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from . import Eq3ConfigEntry
from .const import DEVICE_MODEL, MANUFACTURER, SIGNAL_THERMOSTAT_DISCONNECTED
from .coordinator import Eq3Coordinator


class Eq3Entity(CoordinatorEntity[Eq3Coordinator]):
    """Base class for all eQ-3 entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        entry: Eq3ConfigEntry,
        unique_id_key: str | None = None,
    ) -> None:
        """Initialize the eq3 entity."""

        super().__init__(entry.runtime_data.coordinator)

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

    @property
    def _status(self) -> Status:
        """Return the status of the thermostat."""

        return self.coordinator.data

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""

        await super().async_added_to_hass()

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{SIGNAL_THERMOSTAT_DISCONNECTED}_{self._eq3_config.mac_address}",
                self._async_on_disconnected,
            )
        )

    @callback
    def _async_on_disconnected(self) -> None:
        """Handle disconnection from the thermostat."""

        self._attr_available = False
        self.async_write_ha_state()
