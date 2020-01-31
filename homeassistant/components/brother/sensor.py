"""Support for the Brother service."""
import logging

from homeassistant.helpers.entity import Entity

from .const import (
    ATTR_DRUM_COUNTER,
    ATTR_DRUM_REMAINING_LIFE,
    ATTR_DRUM_REMAINING_PAGES,
    ATTR_ICON,
    ATTR_LABEL,
    ATTR_MANUFACTURER,
    ATTR_UNIT,
    DOMAIN,
    SENSOR_TYPES,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Add Brother entities from a config_entry."""
    brother = hass.data[DOMAIN][config_entry.entry_id]

    sensors = []

    name = brother.model
    device_info = {
        "identifiers": {(DOMAIN, brother.serial)},
        "name": brother.model,
        "manufacturer": ATTR_MANUFACTURER,
        "model": brother.model,
        "sw_version": brother.firmware,
    }

    for sensor in SENSOR_TYPES:
        if sensor in brother.data:
            sensors.append(BrotherPrinterSensor(brother, name, sensor, device_info))
    async_add_entities(sensors, True)


class BrotherPrinterSensor(Entity):
    """Define an Brother Printer sensor."""

    def __init__(self, printer, name, kind, device_info):
        """Initialize."""
        self.printer = printer
        self._name = name
        self._device_info = device_info
        self._unique_id = f"{self.printer.serial.lower()}_{kind}"
        self.kind = kind
        self._state = None
        self._attrs = {}

    @property
    def name(self):
        """Return the name."""
        return f"{self._name} {SENSOR_TYPES[self.kind][ATTR_LABEL]}"

    @property
    def state(self):
        """Return the state."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        if self.kind == ATTR_DRUM_REMAINING_LIFE:
            self._attrs["remaining_pages"] = self.printer.data.get(
                ATTR_DRUM_REMAINING_PAGES
            )
            self._attrs["counter"] = self.printer.data.get(ATTR_DRUM_COUNTER)
        return self._attrs

    @property
    def icon(self):
        """Return the icon."""
        return SENSOR_TYPES[self.kind][ATTR_ICON]

    @property
    def unique_id(self):
        """Return a unique_id for this entity."""
        return self._unique_id

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return SENSOR_TYPES[self.kind][ATTR_UNIT]

    @property
    def available(self):
        """Return True if entity is available."""
        return self.printer.available

    @property
    def device_info(self):
        """Return the device info."""
        return self._device_info

    async def async_update(self):
        """Update the data from printer."""
        await self.printer.async_update()

        self._state = self.printer.data.get(self.kind)
