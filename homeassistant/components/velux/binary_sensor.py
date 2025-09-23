"""Support for rain sensors built into some Velux windows."""

from __future__ import annotations

from datetime import timedelta

from pyvlx.exception import PyVLXException
from pyvlx.opening_device import OpeningDevice, Window

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, LOGGER
from .entity import VeluxEntity

PARALLEL_UPDATES = 1
SCAN_INTERVAL = timedelta(minutes=5)  # Use standard polling


async def async_setup_entry(
    hass: HomeAssistant,
    config: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up rain sensor(s) for Velux platform."""
    module = hass.data[DOMAIN][config.entry_id]

    async_add_entities(
        VeluxRainSensor(node, config.entry_id)
        for node in module.pyvlx.nodes
        if isinstance(node, Window) and node.rain_sensor
    )


class VeluxRainSensor(VeluxEntity, BinarySensorEntity):
    """Representation of a Velux rain sensor."""

    node: Window
    _attr_should_poll = True  # the rain sensor / opening limitations needs polling unlike the rest of the Velux devices
    _attr_entity_registry_enabled_default = False
    _attr_device_class = BinarySensorDeviceClass.MOISTURE
    _attr_translation_key = "rain_sensor"

    def __init__(self, node: OpeningDevice, config_entry_id: str) -> None:
        """Initialize VeluxRainSensor."""
        super().__init__(node, config_entry_id)
        self._attr_unique_id = f"{self._attr_unique_id}_rain_sensor"

    async def async_update(self) -> None:
        """Fetch the latest state from the device."""
        try:
            limitation = await self.node.get_limitation()
        except PyVLXException:
            LOGGER.error("Error fetching limitation data for cover %s", self.name)
            return

        # Velux windows with rain sensors report an opening limitation of 93 or 100 (Velux GPU) when rain is detected.
        # So far, only 93 and 100 have been observed in practice, documentation on this is non-existent AFAIK.
        self._attr_is_on = limitation.min_value in {93, 100}
