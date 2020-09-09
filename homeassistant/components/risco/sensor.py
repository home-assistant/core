"""Sensor for Risco Events."""
from homeassistant.const import DEVICE_CLASS_TIMESTAMP
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, EVENTS_COORDINATOR

CATEGORIES = {
    2: "Alarm",
    4: "Status",
    7: "Trouble",
}
EVENT_ATTRIBUTES = [
    "category_id",
    "category_name",
    "type_id",
    "type_name",
    "name",
    "text",
    "partition_id",
    "zone_id",
    "user_id",
    "group",
    "priority",
    "raw",
]


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up sensors for device."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id][EVENTS_COORDINATOR]
    sensors = [
        RiscoSensor(coordinator, id, [], name) for id, name in CATEGORIES.items()
    ]
    sensors.append(RiscoSensor(coordinator, None, CATEGORIES.keys(), "Other"))
    async_add_entities(sensors)


class RiscoSensor(CoordinatorEntity):
    """Sensor for Risco events."""

    def __init__(self, coordinator, category_id, excludes, name) -> None:
        """Initialize sensor."""
        super().__init__(coordinator)
        self._event = None
        self._category_id = category_id
        self._excludes = excludes
        self._name = name

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"Risco {self.coordinator.risco.site_name} {self._name} Events"

    @property
    def unique_id(self):
        """Return a unique id for this sensor."""
        return f"events_{self._name}_{self.coordinator.risco.site_uuid}"

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self._refresh_from_coordinator)
        )
        await self.coordinator.async_request_refresh()

    def _refresh_from_coordinator(self):
        events = self.coordinator.data
        for event in reversed(events):
            if event.category_id in self._excludes:
                continue
            if self._category_id is not None and event.category_id != self._category_id:
                continue

            self._event = event
            self.async_write_ha_state()

    @property
    def state(self):
        """Value of sensor."""
        if self._event is None:
            return None

        return self._event.time

    @property
    def device_state_attributes(self):
        """State attributes."""
        if self._event is None:
            return None

        return {atr: getattr(self._event, atr, None) for atr in EVENT_ATTRIBUTES}

    @property
    def device_class(self):
        """Device class of sensor."""
        return DEVICE_CLASS_TIMESTAMP
