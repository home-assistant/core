"""Support for the OpenWeatherMap (OWM) Air Pollution service."""

from __future__ import annotations

from datetime import timedelta

from pyopenweathermap import OWMClient, RequestError, create_owm_client

from homeassistant.components.air_quality import AirQualityEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import OpenweathermapConfigEntry
from .const import ATTRIBUTION

SCAN_INTERVAL = timedelta(minutes=10)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: OpenweathermapConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up OpenWeatherMap air_quality entity based on a config entry."""
    domain_data = config_entry.runtime_data
    name = domain_data.name

    owm_client = create_owm_client(config_entry.data["api_key"], "air_pollution")

    unique_id = f"{config_entry.unique_id}"
    owm_air_quality = OpenWeatherMapAirQuality(
        name,
        unique_id,
        owm_client,
        config_entry.data["latitude"],
        config_entry.data["longitude"],
    )

    async_add_entities([owm_air_quality], True)


class OpenWeatherMapAirQuality(AirQualityEntity):
    """Implementation of an OpenWeatherMap air quality entity."""

    _attr_attribution = ATTRIBUTION
    _attr_should_poll = False

    def __init__(
        self,
        name: str,
        unique_id: str,
        owm_client: OWMClient,
        latitude: int,
        longitude: int,
    ) -> None:
        """Initialize the sensor."""
        self._attr_name = name
        self._attr_unique_id = unique_id
        self._owm_client = owm_client
        self._latitude = latitude
        self._longitude = longitude
        self._current_air_quality = None
        self._available = False

    async def async_update(self):
        """Update and cache air quality level."""
        try:
            air_quality = await self._owm_client.get_air_pollution(
                self._latitude, self._longitude
            )
            self._available = True
            self._current_air_quality = air_quality.current
        except RequestError:
            self._available = False

    @property
    def available(self):
        """Return true when state is known."""
        return self._available

    @property
    def particulate_matter_2_5(self):
        """Return the particulate matter 2.5 level."""
        return self._current_air_quality.pm2_5

    @property
    def particulate_matter_10(self):
        """Return the particulate matter 10 level."""
        return self._current_air_quality.pm10

    @property
    def ammonia(self):
        """Return the NH3 (ammonia) level."""
        return self._current_air_quality.nh3

    @property
    def air_quality_index(self):
        """Return the Air Quality Index (AQI)."""
        return self._current_air_quality.aqi

    @property
    def ozone(self):
        """Return the O3 (ozone) level."""
        return self._current_air_quality.o3

    @property
    def carbon_monoxide(self):
        """Return the CO (carbon monoxide) level."""
        return self._current_air_quality.co

    @property
    def sulphur_dioxide(self):
        """Return the SO2 (sulphur dioxide) level."""
        return self._current_air_quality.so2

    @property
    def nitrogen_monoxide(self):
        """Return the NO (nitrogen monoxide) level."""
        return self._current_air_quality.no

    @property
    def nitrogen_dioxide(self):
        """Return the NO2 (nitrogen dioxide) level."""
        return self._current_air_quality.no2
