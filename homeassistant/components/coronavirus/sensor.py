"""Sensor platform for the Corona virus."""
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.helpers.entity import Entity

from . import get_coordinator
from .const import ATTRIBUTION, OPTION_WORLDWIDE

SENSORS = {
    "confirmed": "mdi:emoticon-neutral-outline",
    "current": "mdi:emoticon-sad-outline",
    "recovered": "mdi:emoticon-happy-outline",
    "deaths": "mdi:emoticon-cry-outline",
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Defer sensor setup to the shared sensor module."""
    coordinator = await get_coordinator(hass)

    async_add_entities(
        CoronavirusSensor(coordinator, config_entry.data["country"], info_type)
        for info_type in SENSORS
    )


class CoronavirusSensor(Entity):
    """Sensor representing corona virus data."""

    name = None
    unique_id = None

    def __init__(self, coordinator, country, info_type):
        """Initialize coronavirus sensor."""
        if country == OPTION_WORLDWIDE:
            self.name = f"Worldwide Coronavirus {info_type}"
        else:
            self.name = f"{coordinator.data[country].country} Coronavirus {info_type}"
        self.unique_id = f"{country}-{info_type}"
        self.coordinator = coordinator
        self.country = country
        self.info_type = info_type

    @property
    def available(self):
        """Return if sensor is available."""
        return self.coordinator.last_update_success and (
            self.country in self.coordinator.data or self.country == OPTION_WORLDWIDE
        )

    @property
    def state(self):
        """State of the sensor."""
        if self.country == OPTION_WORLDWIDE:
            return sum(
                getattr(case, self.info_type) for case in self.coordinator.data.values()
            )

        return getattr(self.coordinator.data[self.country], self.info_type)

    @property
    def icon(self):
        """Return the icon."""
        return SENSORS[self.info_type]

    @property
    def unit_of_measurement(self):
        """Return unit of measurement."""
        return "people"

    @property
    def device_state_attributes(self):
        """Return device attributes."""
        return {ATTR_ATTRIBUTION: ATTRIBUTION}

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        self.coordinator.async_add_listener(self.async_write_ha_state)

    async def async_will_remove_from_hass(self):
        """When entity will be removed from hass."""
        self.coordinator.async_remove_listener(self.async_write_ha_state)
