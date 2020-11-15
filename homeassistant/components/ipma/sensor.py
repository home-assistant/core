"""Support for Instituto Portuguese do Mar e Atmosfera (IPMA) weather service."""

import logging

from homeassistant.const import LENGTH_METERS
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

from .const import (
    DOMAIN,
    FORECAST_PERIOD,
    IPMA_API,
    IPMA_LOCATION,
    MAX_SWELL_HIGH,
    MAX_SWELL_PERIOD,
    MAX_TEMPERATURE,
    MAX_WAVE_HIGH,
    MIN_SWELL_HIGH,
    MIN_SWELL_PERIOD,
    MIN_TEMPERATURE,
    MIN_WAVE_HIGH,
    WAVE_DIRECTION,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistantType, config_entry: ConfigType, async_add_entities
) -> None:
    """Add a weather sensors from a config_entry."""
    hass_data = hass.data[DOMAIN][config_entry.entry_id]
    api = hass_data[IPMA_API]
    location = hass_data[IPMA_LOCATION]

    async_add_entities([IPMASeaSensor(location, api, config_entry.data)], True)


class IPMASeaSensor(Entity):
    """Implementation of an IPMA Maritime Weather sensor."""

    def __init__(self, location, api, config):
        """Initialize the sensor."""
        self._location = location
        self._api = api
        self._location_name = location.sea_station_name
        self._name = f"IPMA {self._location_name}"

        self._sea_forecast = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unique_id(self):
        """Return the unique of the sensor."""
        return f"{self._location.station_latitude}, {self._location.station_longitude}, maritime"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._sea_forecast.max_swell_high

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return LENGTH_METERS

    @property
    def icon(self):
        """Return the icon for the entity card."""
        return "mdi:beach"

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        return {
            FORECAST_PERIOD: self._sea_forecast._time,
            MIN_WAVE_HIGH: self._sea_forecast.min_wave_high,
            MAX_WAVE_HIGH: self._sea_forecast.max_wave_high,
            MIN_TEMPERATURE: self._sea_forecast.min_temperature,
            MAX_TEMPERATURE: self._sea_forecast.max_temperature,
            MIN_SWELL_PERIOD: self._sea_forecast.min_swell_period,
            MAX_SWELL_PERIOD: self._sea_forecast.max_swell_period,
            MIN_SWELL_HIGH: self._sea_forecast.min_swell_high,
            MAX_SWELL_HIGH: self._sea_forecast.max_swell_high,
            WAVE_DIRECTION: self._sea_forecast.wave_direction,
        }

    async def async_update(self):
        """Schedule a custom update via the common entity update service."""
        self._sea_forecast = await self._location.sea_forecast(self._api)
        _LOGGER.debug(self._sea_forecast)

    @property
    def should_poll(self) -> bool:
        """Entities do not individually poll."""
        return True

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        return False

    @property
    def available(self):
        """Return if state is available."""
        return self._sea_forecast is not None
