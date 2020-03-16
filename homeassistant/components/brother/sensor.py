"""Support for the Brother service."""
import logging

from homeassistant.helpers.entity import Entity

from .const import (
    ATTR_BLACK_DRUM_COUNTER,
    ATTR_BLACK_DRUM_REMAINING_LIFE,
    ATTR_BLACK_DRUM_REMAINING_PAGES,
    ATTR_CYAN_DRUM_COUNTER,
    ATTR_CYAN_DRUM_REMAINING_LIFE,
    ATTR_CYAN_DRUM_REMAINING_PAGES,
    ATTR_DRUM_COUNTER,
    ATTR_DRUM_REMAINING_LIFE,
    ATTR_DRUM_REMAINING_PAGES,
    ATTR_ICON,
    ATTR_LABEL,
    ATTR_MAGENTA_DRUM_COUNTER,
    ATTR_MAGENTA_DRUM_REMAINING_LIFE,
    ATTR_MAGENTA_DRUM_REMAINING_PAGES,
    ATTR_MANUFACTURER,
    ATTR_UNIT,
    ATTR_YELLOW_DRUM_COUNTER,
    ATTR_YELLOW_DRUM_REMAINING_LIFE,
    ATTR_YELLOW_DRUM_REMAINING_PAGES,
    DOMAIN,
    SENSOR_TYPES,
)

ATTR_COUNTER = "counter"
ATTR_FIRMWARE = "firmware"
ATTR_MODEL = "model"
ATTR_REMAINING_PAGES = "remaining_pages"
ATTR_SERIAL = "serial"

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Add Brother entities from a config_entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    sensors = []

    device_info = {
        "identifiers": {(DOMAIN, coordinator.data[ATTR_SERIAL])},
        "name": coordinator.data[ATTR_MODEL],
        "manufacturer": ATTR_MANUFACTURER,
        "model": coordinator.data[ATTR_MODEL],
        "sw_version": coordinator.data.get(ATTR_FIRMWARE),
    }

    for sensor in SENSOR_TYPES:
        if sensor in coordinator.data:
            sensors.append(BrotherPrinterSensor(coordinator, sensor, device_info))
    async_add_entities(sensors, False)


class BrotherPrinterSensor(Entity):
    """Define an Brother Printer sensor."""

    def __init__(self, coordinator, kind, device_info):
        """Initialize."""
        self._name = f"{coordinator.data[ATTR_MODEL]} {SENSOR_TYPES[kind][ATTR_LABEL]}"
        self._unique_id = f"{coordinator.data[ATTR_SERIAL].lower()}_{kind}"
        self._device_info = device_info
        self.coordinator = coordinator
        self.kind = kind
        self._attrs = {}

    @property
    def name(self):
        """Return the name."""
        return self._name

    @property
    def state(self):
        """Return the state."""
        return self.coordinator.data.get(self.kind)

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        remaining_pages = None
        drum_counter = None
        if self.kind == ATTR_DRUM_REMAINING_LIFE:
            remaining_pages = ATTR_DRUM_REMAINING_PAGES
            drum_counter = ATTR_DRUM_COUNTER
        elif self.kind == ATTR_BLACK_DRUM_REMAINING_LIFE:
            remaining_pages = ATTR_BLACK_DRUM_REMAINING_PAGES
            drum_counter = ATTR_BLACK_DRUM_COUNTER
        elif self.kind == ATTR_CYAN_DRUM_REMAINING_LIFE:
            remaining_pages = ATTR_CYAN_DRUM_REMAINING_PAGES
            drum_counter = ATTR_CYAN_DRUM_COUNTER
        elif self.kind == ATTR_MAGENTA_DRUM_REMAINING_LIFE:
            remaining_pages = ATTR_MAGENTA_DRUM_REMAINING_PAGES
            drum_counter = ATTR_MAGENTA_DRUM_COUNTER
        elif self.kind == ATTR_YELLOW_DRUM_REMAINING_LIFE:
            remaining_pages = ATTR_YELLOW_DRUM_REMAINING_PAGES
            drum_counter = ATTR_YELLOW_DRUM_COUNTER
        if remaining_pages and drum_counter:
            self._attrs[ATTR_REMAINING_PAGES] = self.coordinator.data.get(
                remaining_pages
            )
            self._attrs[ATTR_COUNTER] = self.coordinator.data.get(drum_counter)
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
        return self.coordinator.last_update_success

    @property
    def should_poll(self):
        """Return the polling requirement of the entity."""
        return False

    @property
    def device_info(self):
        """Return the device info."""
        return self._device_info

    @property
    def entity_registry_enabled_default(self):
        """Return if the entity should be enabled when first added to the entity registry."""
        return True

    async def async_added_to_hass(self):
        """Connect to dispatcher listening for entity data notifications."""
        self.coordinator.async_add_listener(self.async_write_ha_state)

    async def async_will_remove_from_hass(self):
        """Disconnect from update signal."""
        self.coordinator.async_remove_listener(self.async_write_ha_state)
