"""Support for mill wifi-enabled home heaters."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.number import NumberDeviceClass, NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_USERNAME, UnitOfPower
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CLOUD, CONNECTION_TYPE, DOMAIN, MANUFACTURER

if TYPE_CHECKING:
    from .coordinator import MillDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Mill Number."""
    if entry.data.get(CONNECTION_TYPE) == CLOUD:
        mill_data_coordinator: MillDataUpdateCoordinator = hass.data[DOMAIN][CLOUD][
            entry.data[CONF_USERNAME]
        ]

        async_add_entities(
            MillNumber(mill_data_coordinator, mill_device)
            for mill_device in mill_data_coordinator.data.values()
        )


class MillNumber(CoordinatorEntity, NumberEntity):
    """Representation of a Mill number device."""

    _attr_device_class = NumberDeviceClass.POWER
    _attr_has_entity_name = True
    _attr_native_max_value = 2000
    _attr_native_min_value = 0
    _attr_native_step = 1
    _attr_native_unit_of_measurement = UnitOfPower.WATT

    def __init__(self, coordinator: MillDataUpdateCoordinator, mill_device) -> None:
        """Initialize the number."""
        super().__init__(coordinator)

        self._id = mill_device.device_id
        self._available = False
        self._attr_unique_id = f"{mill_device.device_id}_max_heating_power"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, mill_device.device_id)},
            name=mill_device.name,
            manufacturer=MANUFACTURER,
            model=mill_device.model,
        )
        self._update_attr(mill_device)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_attr(self.coordinator.data[self._id])
        self.async_write_ha_state()

    @callback
    def _update_attr(self, device):
        self._attr_native_value = device.data["deviceSettings"]["reported"].get(
            "max_heater_power"
        )
        self._available = device.available and self._attr_native_value is not None

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self._available

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        await self.coordinator.mill_data_connection.max_heating_power(self._id, value)  # type: ignore[attr-defined]
