"""Support for the Brother service."""
import logging

from homeassistant.helpers import device_registry, entity_registry
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

    if brother.available:
        # list of sensors available for this printer model
        printer_sensor_list = {item for item in brother.data.keys()}

    else:
        _LOGGER.info("Printer is unavailable, reading device info from registry")

        # read printer info from device registry
        dev_reg = await device_registry.async_get_registry(hass)
        device = device_registry.async_entries_for_config_entry(
            dev_reg, config_entry.entry_id
        )[0]

        brother.model = device.model
        brother.firmware = device.sw_version
        brother.serial = next(iter(device.identifiers))[1]

        # read list of sensors from entity registry
        ent_reg = await entity_registry.async_get_registry(hass)
        entities = entity_registry.async_entries_for_config_entry(
            ent_reg, config_entry.entry_id
        )
        printer_sensor_list = {entity.unique_id.split("_", 1)[1] for entity in entities}

    device_info = {
        "identifiers": {(DOMAIN, brother.serial)},
        "name": brother.model,
        "manufacturer": ATTR_MANUFACTURER,
        "model": brother.model,
        "sw_version": brother.firmware,
    }

    sensors = []
    for sensor in SENSOR_TYPES:
        if sensor in printer_sensor_list:
            sensors.append(
                BrotherPrinterSensor(brother, brother.model, sensor, device_info)
            )
    async_add_entities(sensors, True)


class BrotherPrinterSensor(Entity):
    """Define a Brother Printer sensor."""

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
