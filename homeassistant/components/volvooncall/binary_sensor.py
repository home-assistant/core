"""Support for VOC."""
from __future__ import annotations

from contextlib import suppress

import voluptuous as vol

from homeassistant.components.binary_sensor import (
    DEVICE_CLASSES_SCHEMA,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import DATA_KEY, VolvoEntity, VolvoUpdateCoordinator


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


class VolvoSensor(VolvoEntity, BinarySensorEntity):
    """Representation of a Volvo sensor."""

    def __init__(
        self,
        coordinator: VolvoUpdateCoordinator,
        vin: str,
        component: str,
        attribute: str,
        slug_attr: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(vin, component, attribute, slug_attr, coordinator)

        with suppress(vol.Invalid):
            self._attr_device_class = DEVICE_CLASSES_SCHEMA(
                self.instrument.device_class
            )

    @property
    def is_on(self) -> bool | None:
        """Fetch from update coordinator."""
        if self.instrument.attr == "is_locked":
            return not self.instrument.is_on
        return self.instrument.is_on
