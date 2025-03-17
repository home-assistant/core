"""Support for VOC."""

from __future__ import annotations

from contextlib import suppress

import voluptuous as vol
from volvooncall.dashboard import Instrument

from homeassistant.components.binary_sensor import (
    DEVICE_CLASSES_SCHEMA,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, VOLVO_DISCOVERY_NEW
from .coordinator import VolvoUpdateCoordinator
from .entity import VolvoEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Configure binary_sensors from a config entry created in the integrations UI."""
    coordinator: VolvoUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    volvo_data = coordinator.volvo_data

    @callback
    def async_discover_device(instruments: list[Instrument]) -> None:
        """Discover and add a discovered Volvo On Call binary sensor."""
        async_add_entities(
            VolvoSensor(
                coordinator,
                instrument.vehicle.vin,
                instrument.component,
                instrument.attr,
                instrument.slug_attr,
            )
            for instrument in instruments
            if instrument.component == "binary_sensor"
        )

    async_discover_device([*volvo_data.instruments])

    config_entry.async_on_unload(
        async_dispatcher_connect(hass, VOLVO_DISCOVERY_NEW, async_discover_device)
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
