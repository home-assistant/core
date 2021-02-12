"""Support for the AEMET OpenData service."""
from homeassistant.components.weather import WeatherEntity
from homeassistant.const import TEMP_CELSIUS
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_API_CONDITION,
    ATTR_API_HUMIDITY,
    ATTR_API_PRESSURE,
    ATTR_API_TEMPERATURE,
    ATTR_API_WIND_BEARING,
    ATTR_API_WIND_SPEED,
    ATTRIBUTION,
    DOMAIN,
    ENTRY_NAME,
    ENTRY_WEATHER_COORDINATOR,
    FORECAST_MODE_ATTR_API,
    FORECAST_MODES,
)
from .weather_update_coordinator import WeatherUpdateCoordinator


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up AEMET OpenData weather entity based on a config entry."""
    domain_data = hass.data[DOMAIN][config_entry.entry_id]
    weather_coordinator = domain_data[ENTRY_WEATHER_COORDINATOR]

    entities = []
    for mode in FORECAST_MODES:
        name = f"{domain_data[ENTRY_NAME]} {mode}"
        unique_id = f"{config_entry.unique_id} {mode}"
        entities.append(AemetWeather(name, unique_id, weather_coordinator, mode))

    if entities:
        async_add_entities(entities, False)


class AemetWeather(CoordinatorEntity, WeatherEntity):
    """Implementation of an AEMET OpenData sensor."""

    def __init__(
        self,
        name,
        unique_id,
        coordinator: WeatherUpdateCoordinator,
        forecast_mode,
    ):
        """Initialize the sensor."""
        CoordinatorEntity.__init__(self, coordinator)
        WeatherEntity.__init__(self)
        self._name = name
        self._unique_id = unique_id
        self._forecast_mode = forecast_mode

    @property
    def attribution(self):
        """Return the attribution."""
        return ATTRIBUTION

    @property
    def available(self):
        """Return True if entity is available."""
        return self.coordinator.last_update_success

    @property
    def condition(self):
        """Return the current condition."""
        return self.coordinator.data[ATTR_API_CONDITION]

    @property
    def forecast(self):
        """Return the forecast array."""
        return self.coordinator.data[FORECAST_MODE_ATTR_API[self._forecast_mode]]

    @property
    def humidity(self):
        """Return the humidity."""
        return self.coordinator.data[ATTR_API_HUMIDITY]

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def pressure(self):
        """Return the pressure."""
        return self.coordinator.data[ATTR_API_PRESSURE]

    @property
    def should_poll(self):
        """Return the polling requirement of the entity."""
        return False

    @property
    def temperature(self):
        """Return the temperature."""
        return self.coordinator.data[ATTR_API_TEMPERATURE]

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def unique_id(self):
        """Return a unique_id for this entity."""
        return self._unique_id

    @property
    def wind_bearing(self):
        """Return the temperature."""
        return self.coordinator.data[ATTR_API_WIND_BEARING]

    @property
    def wind_speed(self):
        """Return the temperature."""
        return self.coordinator.data[ATTR_API_WIND_SPEED]

    async def async_added_to_hass(self):
        """Connect to dispatcher listening for entity data notifications."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )

    async def async_update(self):
        """Get the latest data from AEMET and updates the states."""
        await self.coordinator.async_request_refresh()
