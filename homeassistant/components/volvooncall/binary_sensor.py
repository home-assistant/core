"""Support for VOC."""
from __future__ import annotations

from homeassistant.components.binary_sensor import DEVICE_CLASSES, BinarySensorEntity
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


class VolvoSensor(VolvoEntity, BinarySensorEntity):
    """Representation of a Volvo sensor."""

    def __init__(
        self, hass: HomeAssistant, vin, component, attribute, slug_attr, coordinator
    ):
        """Initialize the sensor."""
        VolvoEntity.__init__(
            self, hass, vin, component, attribute, slug_attr, coordinator
        )

        if self.instrument.device_class in DEVICE_CLASSES:
            self._attr_device_class = self.instrument.device_class
        else:
            self._attr_device_class = None

        if self.instrument.attr == "is_locked":
            self._attr_is_on = not self.instrument.is_on
        else:
            self._attr_is_on = self.instrument.is_on

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self.instrument.attr == "is_locked":
            self._attr_is_on = not self.instrument.is_on
        else:
            self._attr_is_on = self.instrument.is_on
        self.async_write_ha_state()
