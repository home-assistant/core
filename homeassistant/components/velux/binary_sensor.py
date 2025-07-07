"""Support for rain sensors build into some velux windows."""

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

    entities = [
        VeluxRainSensor(node, config.entry_id)
        for node in module.pyvlx.nodes
        if isinstance(node, Window) and node.rain_sensor
    ]

    async_add_entities(entities)


class VeluxRainSensor(VeluxEntity, BinarySensorEntity):
    """Representation of a Velux rain sensor."""

    node: Window
    _attr_should_poll = True  # the rain sensor / opening limitations needs polling unlike the rest of the Velux devices
    _attr_entity_registry_enabled_default = False

    def __init__(self, node: OpeningDevice, config_entry_id: str) -> None:
        """Initialize VeluxRainSensor."""
        super().__init__(node, config_entry_id)
        LOGGER.info("Creating velux rain sensor from %s", node.name)
        self._attr_unique_id = f"{self._attr_unique_id}_rain_sensor"
        self._attr_name = f"{node.name} Rain Sensor"
        self._attr_device_class = BinarySensorDeviceClass.MOISTURE
        self.rain_detected = False

    async def async_update(self) -> None:
        """Fetch the latest state from the device."""
        try:
            limitation = await self.node.get_limitation()
        except PyVLXException:
            LOGGER.error("Error fetch limitation data for cover %s", self.name)
            return

        # Velux windows with rain sensors report an opening limitation of 93 when rain is detected.
        self.rain_detected = limitation.min_value == 93
        LOGGER.debug(
            "Rain sensor updated, limitation max/min_value=%s/%s",
            limitation.max_value,
            limitation.min_value,
        )

    @property
    def is_on(self) -> bool:
        """Return if the rain sensor is triggered."""
        return self.rain_detected
