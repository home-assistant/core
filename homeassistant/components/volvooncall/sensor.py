"""Support for Volvo On Call sensors."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import DATA_KEY, VolvoEntity


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Volvo sensors."""
    if discovery_info is None:
        return
    async_add_entities([VolvoSensor(hass.data[DATA_KEY], *discovery_info)])


class VolvoSensor(VolvoEntity, SensorEntity):
    """Representation of a Volvo sensor."""

    @property
    def native_value(self):
        """Return the state."""
        return self.instrument.state

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement."""
        return self.instrument.unit
