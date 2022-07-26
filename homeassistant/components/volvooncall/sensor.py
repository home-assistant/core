"""Support for Volvo On Call sensors."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import VolvoEntity


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Volvo sensors."""
    if discovery_info is None:
        return
    async_add_entities([VolvoSensor(hass, *discovery_info)])


class VolvoSensor(VolvoEntity, SensorEntity):
    """Representation of a Volvo sensor."""

    def __init__(
        self, hass: HomeAssistant, vin, component, attribute, slug_attr, coordinator
    ):
        """Initialize the sensor."""
        VolvoEntity.__init__(
            self, hass, vin, component, attribute, slug_attr, coordinator
        )

        self._attr_native_value = self.instrument.state
        self._attr_native_unit_of_measurement = self.instrument.unit

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_native_value = self.instrument.state
        self._attr_native_unit_of_measurement = self.instrument.unit
        self.async_write_ha_state()
