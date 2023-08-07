"""Support for the World Air Quality Index service."""
from __future__ import annotations

from datetime import timedelta
import logging

from aiowaqi import WAQIAirQuality, WAQIClient, WAQIConnectionError, WAQISearchResult
import voluptuous as vol

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_TEMPERATURE,
    ATTR_TIME,
    CONF_TOKEN,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

ATTR_DOMINENTPOL = "dominentpol"
ATTR_HUMIDITY = "humidity"
ATTR_NITROGEN_DIOXIDE = "nitrogen_dioxide"
ATTR_OZONE = "ozone"
ATTR_PM10 = "pm_10"
ATTR_PM2_5 = "pm_2_5"
ATTR_PRESSURE = "pressure"
ATTR_SULFUR_DIOXIDE = "sulfur_dioxide"

KEY_TO_ATTR = {
    "pm25": ATTR_PM2_5,
    "pm10": ATTR_PM10,
    "h": ATTR_HUMIDITY,
    "p": ATTR_PRESSURE,
    "t": ATTR_TEMPERATURE,
    "o3": ATTR_OZONE,
    "no2": ATTR_NITROGEN_DIOXIDE,
    "so2": ATTR_SULFUR_DIOXIDE,
}

ATTRIBUTION = "Data provided by the World Air Quality Index project"

ATTR_ICON = "mdi:cloud"

CONF_LOCATIONS = "locations"
CONF_STATIONS = "stations"

SCAN_INTERVAL = timedelta(minutes=5)

TIMEOUT = 10

PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_STATIONS): cv.ensure_list,
        vol.Required(CONF_TOKEN): cv.string,
        vol.Required(CONF_LOCATIONS): cv.ensure_list,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the requested World Air Quality Index locations."""

    token = config[CONF_TOKEN]
    station_filter = config.get(CONF_STATIONS)
    locations = config[CONF_LOCATIONS]

    client = WAQIClient(session=async_get_clientsession(hass), request_timeout=TIMEOUT)
    client.authenticate(token)
    dev = []
    try:
        for location_name in locations:
            stations = await client.search(location_name)
            _LOGGER.debug("The following stations were returned: %s", stations)
            for station in stations:
                waqi_sensor = WaqiSensor(client, station)
                if not station_filter or {
                    waqi_sensor.uid,
                    waqi_sensor.url,
                    waqi_sensor.station_name,
                } & set(station_filter):
                    dev.append(waqi_sensor)
    except WAQIConnectionError as err:
        _LOGGER.exception("Failed to connect to WAQI servers")
        raise PlatformNotReady from err
    async_add_entities(dev, True)


class WaqiSensor(SensorEntity):
    """Implementation of a WAQI sensor."""

    _attr_icon = ATTR_ICON
    _attr_device_class = SensorDeviceClass.AQI
    _attr_state_class = SensorStateClass.MEASUREMENT

    _data: WAQIAirQuality | None = None

    def __init__(self, client: WAQIClient, search_result: WAQISearchResult) -> None:
        """Initialize the sensor."""
        self._client = client
        self.uid = search_result.station_id
        self.url = search_result.station.external_url
        self.station_name = search_result.station.name

    @property
    def name(self):
        """Return the name of the sensor."""
        if self.station_name:
            return f"WAQI {self.station_name}"
        return f"WAQI {self.url if self.url else self.uid}"

    @property
    def native_value(self) -> int | None:
        """Return the state of the device."""
        assert self._data
        return self._data.air_quality_index

    @property
    def available(self):
        """Return sensor availability."""
        return self._data is not None

    @property
    def unique_id(self):
        """Return unique ID."""
        return self.uid

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the last update."""
        attrs = {}

        if self._data is not None:
            try:
                attrs[ATTR_ATTRIBUTION] = " and ".join(
                    [ATTRIBUTION]
                    + [attribution.name for attribution in self._data.attributions]
                )

                attrs[ATTR_TIME] = self._data.measured_at
                attrs[ATTR_DOMINENTPOL] = self._data.dominant_pollutant

                iaqi = self._data.extended_air_quality

                attribute = {
                    ATTR_PM2_5: iaqi.pm25,
                    ATTR_PM10: iaqi.pm10,
                    ATTR_HUMIDITY: iaqi.humidity,
                    ATTR_PRESSURE: iaqi.pressure,
                    ATTR_TEMPERATURE: iaqi.temperature,
                    ATTR_OZONE: iaqi.ozone,
                    ATTR_NITROGEN_DIOXIDE: iaqi.nitrogen_dioxide,
                    ATTR_SULFUR_DIOXIDE: iaqi.sulfur_dioxide,
                }
                res_attributes = {k: v for k, v in attribute.items() if v is not None}
                return {**attrs, **res_attributes}
            except (IndexError, KeyError):
                return {ATTR_ATTRIBUTION: ATTRIBUTION}

    async def async_update(self) -> None:
        """Get the latest data and updates the states."""
        if self.uid:
            result = await self._client.get_by_station_number(self.uid)
        elif self.url:
            result = await self._client.get_by_name(self.url)
        else:
            result = None
        self._data = result
