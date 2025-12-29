"""Support for rain sensors built into some Velux windows."""

from __future__ import annotations

from datetime import timedelta

from pyvlx.exception import PyVLXException
from pyvlx.opening_device import OpeningDevice, Window

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import VeluxConfigEntry
from .const import LOGGER
from .entity import VeluxEntity

PARALLEL_UPDATES = 1
SCAN_INTERVAL = timedelta(minutes=5)  # Use standard polling


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: VeluxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up rain sensor(s) for Velux platform."""
    pyvlx = config_entry.runtime_data

    async_add_entities(
        VeluxRainSensor(node, config_entry.entry_id)
        for node in pyvlx.nodes
        if isinstance(node, Window) and node.rain_sensor
    )


class VeluxRainSensor(VeluxEntity, BinarySensorEntity):
    """Representation of a Velux rain sensor."""

    node: Window
    _attr_should_poll = True  # the rain sensor / opening limitations needs polling unlike the rest of the Velux devices
    _attr_entity_registry_enabled_default = False
    _attr_device_class = BinarySensorDeviceClass.MOISTURE
    _attr_translation_key = "rain_sensor"
    _unavailable_logged = False

    def __init__(self, node: OpeningDevice, config_entry_id: str) -> None:
        """Initialize VeluxRainSensor."""
        super().__init__(node, config_entry_id)
        self._attr_unique_id = f"{self._attr_unique_id}_rain_sensor"

    async def async_update(self) -> None:
        """Fetch the latest state from the device."""
        try:
            limitation = await self.node.get_limitation()
        except (OSError, PyVLXException) as err:
            if not self._unavailable_logged:
                LOGGER.warning(
                    "Rain sensor %s is unavailable: %s",
                    self.entity_id,
                    err,
                )
                self._unavailable_logged = True
            self._attr_available = False
            return

        # Log when entity comes back online after being unavailable
        if self._unavailable_logged:
            LOGGER.info("Rain sensor %s is back online", self.entity_id)
            self._unavailable_logged = False

        self._attr_available = True

        # Velux windows with rain sensors report an opening limitation of 93 or 100 (Velux GPU) when rain is detected.
        # So far, only 93 and 100 have been observed in practice, documentation on this is non-existent AFAIK.
        self._attr_is_on = limitation.min_value in {93, 100}
