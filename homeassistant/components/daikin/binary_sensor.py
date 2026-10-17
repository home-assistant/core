"""Support for Daikin binary sensors."""

from typing import Any, override

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import DaikinConfigEntry, DaikinCoordinator
from .entity import DaikinEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DaikinConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Daikin binary sensors based on a config entry."""
    daikin_api = entry.runtime_data
    if daikin_api.device.support_demand_control:
        async_add_entities([DaikinDemandControlSensor(daikin_api)])


class DaikinDemandControlSensor(DaikinEntity, BinarySensorEntity):
    """Representation of the demand control state."""

    _attr_translation_key = "demand_control"

    def __init__(self, coordinator: DaikinCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{self.device.mac}-demand_control"

    @property
    @override
    def is_on(self) -> bool:
        """Return the state of the sensor."""
        return self.device.get_demand_control().get("en_demand") == "1"

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        attrs = self.device.get_demand_control()
        if attrs.get("mode") != "0":
            attrs.pop("max_pow", None)
        return attrs
