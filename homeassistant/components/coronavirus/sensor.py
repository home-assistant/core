"""Sensor platform for the Corona virus."""
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import get_coordinator
from .const import ATTRIBUTION, OPTION_WORLDWIDE

SENSORS = {
    "confirmed": "mdi:emoticon-neutral-outline",
    "current": "mdi:emoticon-sad-outline",
    "recovered": "mdi:emoticon-happy-outline",
    "deaths": "mdi:emoticon-cry-outline",
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Defer sensor setup to the shared sensor module."""
    coordinator = await get_coordinator(hass)

    async_add_entities(
        CoronavirusSensor(coordinator, config_entry.data["country"], info_type)
        for info_type in SENSORS
    )


class CoronavirusSensor(CoordinatorEntity, SensorEntity):
    """Sensor representing corona virus data."""

    _attr_attribution = ATTRIBUTION
    _attr_native_unit_of_measurement = "people"

    def __init__(self, coordinator, country, info_type):
        """Initialize coronavirus sensor."""
        super().__init__(coordinator)
        self._attr_icon = SENSORS[info_type]
        self._attr_unique_id = f"{country}-{info_type}"
        if country == OPTION_WORLDWIDE:
            self._attr_name = f"Worldwide Coronavirus {info_type}"
        else:
            self._attr_name = (
                f"{coordinator.data[country].country} Coronavirus {info_type}"
            )

        self.country = country
        self.info_type = info_type

    @property
    def available(self) -> bool:
        """Return if sensor is available."""
        return self.coordinator.last_update_success and (
            self.country in self.coordinator.data or self.country == OPTION_WORLDWIDE
        )

    @property
    def native_value(self):
        """State of the sensor."""
        if self.country == OPTION_WORLDWIDE:
            sum_cases = 0
            for case in self.coordinator.data.values():
                if (value := getattr(case, self.info_type)) is None:
                    continue
                sum_cases += value

            return sum_cases

        return getattr(self.coordinator.data[self.country], self.info_type)
