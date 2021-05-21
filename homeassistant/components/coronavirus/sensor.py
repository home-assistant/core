"""Sensor platform for the Corona virus."""
from homeassistant.components.sensor import SensorEntity
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.helpers.update_coordinator import CoordinatorEntity

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


class CoronavirusSensor(CoordinatorEntity, SensorEntity):
    """Sensor representing corona virus data."""

    name = None
    unique_id = None

    def __init__(self, coordinator, country, info_type):
        """Initialize coronavirus sensor."""
        super().__init__(coordinator)
        if country == OPTION_WORLDWIDE:
            self.name = f"Worldwide Coronavirus {info_type}"
        else:
            self.name = f"{coordinator.data[country].country} Coronavirus {info_type}"
        self.unique_id = f"{country}-{info_type}"
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
            sum_cases = 0
            for case in self.coordinator.data.values():
                value = getattr(case, self.info_type)
                if value is None:
                    continue
                sum_cases += value

            return sum_cases

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
    def extra_state_attributes(self):
        """Return device attributes."""
        return {ATTR_ATTRIBUTION: ATTRIBUTION}
