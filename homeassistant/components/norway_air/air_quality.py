"""Sensor for checking the air quality forecast around Norway."""

from __future__ import annotations

from datetime import timedelta
import logging

import metno
import voluptuous as vol

from homeassistant.components.air_quality import (
    PLATFORM_SCHEMA as AIR_QUALITY_PLATFORM_SCHEMA,
    AirQualityEntity,
)
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)


CONF_FORECAST = "forecast"

DEFAULT_FORECAST = 0
DEFAULT_NAME = "Air quality Norway"

OVERRIDE_URL = "https://aa015h6buqvih86i1.api.met.no/weatherapi/airqualityforecast/0.1/"

PLATFORM_SCHEMA = AIR_QUALITY_PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_FORECAST, default=DEFAULT_FORECAST): vol.Coerce(int),
        vol.Optional(CONF_LATITUDE): cv.latitude,
        vol.Optional(CONF_LONGITUDE): cv.longitude,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)

SCAN_INTERVAL = timedelta(minutes=5)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the air_quality norway sensor."""
    forecast = config.get(CONF_FORECAST)
    latitude = config.get(CONF_LATITUDE, hass.config.latitude)
    longitude = config.get(CONF_LONGITUDE, hass.config.longitude)
    name = config.get(CONF_NAME)

    if None in (latitude, longitude):
        _LOGGER.error("Latitude or longitude not set in Home Assistant config")
        return

    coordinates = {"lat": str(latitude), "lon": str(longitude)}

    async_add_entities(
        [AirSensor(name, coordinates, forecast, async_get_clientsession(hass))], True
    )


def round_state(func):
    """Round state."""

    def _decorator(self):
        res = func(self)
        if isinstance(res, float):
            return round(res, 2)
        return res

    return _decorator


class AirSensor(AirQualityEntity):
    """Representation of an air quality sensor."""

    # https://api.met.no/license_data.html
    _attr_attribution = (
        "Air quality from "
        "https://luftkvalitet.miljostatus.no/, "
        "delivered by the Norwegian Meteorological Institute."
    )

    def __init__(self, name, coordinates, forecast, session):
        """Initialize the sensor."""
        self._name = name
        self._api = metno.AirQualityData(
            coordinates, forecast, session, api_url=OVERRIDE_URL
        )

    @property
    def extra_state_attributes(self) -> dict:
        """Return other details about the sensor state."""
        return {
            "level": self._api.data.get("level"),
            "location": self._api.data.get("location"),
        }

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._name

    @property
    @round_state
    def air_quality_index(self):
        """Return the Air Quality Index (AQI)."""
        return self._api.data.get("aqi")

    @property
    @round_state
    def nitrogen_dioxide(self):
        """Return the NO2 (nitrogen dioxide) level."""
        return self._api.data.get("no2_concentration")

    @property
    @round_state
    def ozone(self):
        """Return the O3 (ozone) level."""
        return self._api.data.get("o3_concentration")

    @property
    @round_state
    def particulate_matter_2_5(self):
        """Return the particulate matter 2.5 level."""
        return self._api.data.get("pm25_concentration")

    @property
    @round_state
    def particulate_matter_10(self):
        """Return the particulate matter 10 level."""
        return self._api.data.get("pm10_concentration")

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._api.units.get("pm25_concentration")

    async def async_update(self) -> None:
        """Update the sensor."""
        await self._api.update()
