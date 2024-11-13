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

from .const import (
    CONF_CURRENT_TEMP_SELECTOR,
    CONF_EXTERNAL_TEMP_SENSOR,
    CONF_MAC_ADDRESS,
    CONF_TARGET_TEMP_SELECTOR,
    DEVICE_MODEL,
    MANUFACTURER,
    SIGNAL_THERMOSTAT_DISCONNECTED,
    CurrentTemperatureSelector,
    TargetTemperatureSelector,
)
from .coordinator import Eq3ConfigEntry, Eq3Coordinator


class Eq3Entity(CoordinatorEntity[Eq3Coordinator]):
    """Base class for all eQ-3 entities."""

    _attr_has_entity_name = True
    _current_temp_selector: CurrentTemperatureSelector
    _target_temp_selector: TargetTemperatureSelector
    _external_temp_sensor: str | None

    def __init__(
        self,
        entry: Eq3ConfigEntry,
        unique_id_key: str | None = None,
    ) -> None:
        """Initialize the eq3 entity."""

        super().__init__(entry.runtime_data.coordinator)

        self._mac_address = entry.data.get(CONF_MAC_ADDRESS, entry.unique_id)
        self._current_temp_selector = entry.options[CONF_CURRENT_TEMP_SELECTOR]
        self._target_temp_selector = entry.options[CONF_TARGET_TEMP_SELECTOR]
        self._external_temp_sensor = entry.options.get(CONF_EXTERNAL_TEMP_SENSOR)
        self._thermostat = entry.runtime_data.thermostat
        self._attr_device_info = DeviceInfo(
            name=slugify(self._mac_address),
            manufacturer=MANUFACTURER,
            model=DEVICE_MODEL,
            connections={(CONNECTION_BLUETOOTH, self._mac_address)},
        )
        suffix = f"_{unique_id_key}" if unique_id_key else ""
        self._attr_unique_id = f"{format_mac(self._mac_address)}{suffix}"

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
                f"{SIGNAL_THERMOSTAT_DISCONNECTED}_{self._mac_address}",
                self._async_on_disconnected,
            )
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""

        self._attr_available = self.coordinator.last_update_success
        super()._handle_coordinator_update()

    @callback
    def _async_on_disconnected(self) -> None:
        """Handle disconnection from the thermostat."""

        self._attr_available = False
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Return True if entity is available."""

        return self._attr_available
