"""Support for mill wifi-enabled home heaters."""

from __future__ import annotations

from mill import Heater, MillDevice

from homeassistant.components.number import NumberDeviceClass, NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_USERNAME, UnitOfPower
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CLOUD, CONNECTION_TYPE, DOMAIN
from .coordinator import MillDataUpdateCoordinator
from .entity import MillBaseEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Mill Number."""
    if entry.data.get(CONNECTION_TYPE) == CLOUD:
        mill_data_coordinator: MillDataUpdateCoordinator = hass.data[DOMAIN][CLOUD][
            entry.data[CONF_USERNAME]
        ]

        async_add_entities(
            MillNumber(mill_data_coordinator, mill_device)
            for mill_device in mill_data_coordinator.data.values()
            if isinstance(mill_device, Heater)
        )


class MillNumber(MillBaseEntity, NumberEntity):
    """Representation of a Mill number device."""

    _attr_device_class = NumberDeviceClass.POWER
    _attr_native_max_value = 2000
    _attr_native_min_value = 0
    _attr_native_step = 1
    _attr_native_unit_of_measurement = UnitOfPower.WATT

    def __init__(
        self,
        coordinator: MillDataUpdateCoordinator,
        mill_device: MillDevice,
    ) -> None:
        """Initialize the number."""
        self._attr_unique_id = f"{mill_device.device_id}_max_heating_power"
        super().__init__(coordinator, mill_device)

    @callback
    def _update_attr(self, device: MillDevice) -> None:
        self._attr_native_value = device.data["deviceSettings"]["reported"].get(
            "max_heater_power"
        )
        self._available = device.available and self._attr_native_value is not None

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        await self.coordinator.mill_data_connection.max_heating_power(self._id, value)
