"""Support for VOC."""
from __future__ import annotations

from contextlib import suppress

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.binary_sensor import (
    DEVICE_CLASSES_SCHEMA,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN, VolvoEntity, VolvoUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Configure binary_sensors from a config entry created in the integrations UI."""
    volvo_data = hass.data[DOMAIN][config_entry.entry_id].volvo_data
    for instrument in volvo_data.instruments:
        if instrument.component == "binary_sensor":
            discovery_info = (
                instrument.vehicle.vin,
                instrument.component,
                instrument.attr,
                instrument.slug_attr,
            )

            async_add_entities(
                [VolvoSensor(hass.data[DOMAIN][config_entry.entry_id], *discovery_info)]
            )


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
