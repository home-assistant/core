"""Support for AirVisual Node/Pro units."""
from homeassistant.components.air_quality import AirQualityEntity
from homeassistant.const import (
    ATTR_BATTERY_LEVEL,
    ATTR_TEMPERATURE,
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    PRECISION_TENTHS,
    TEMP_CELSIUS,
)
from homeassistant.core import callback
from homeassistant.helpers.temperature import display_temp
from homeassistant.util import slugify

from . import AirVisualEntity
from .const import DATA_CLIENT, DOMAIN

ATTR_HUMIDITY = "humidity"
ATTR_SENSOR_LIFE = "{0}_sensor_life"
ATTR_TREND = "{0}_trend"
ATTR_VOC = "voc"


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up AirVisual air quality entities based on a config entry."""
    airvisual = hass.data[DOMAIN][DATA_CLIENT][config_entry.entry_id]
    async_add_entities([AirVisualNodeProSensor(airvisual)], True)


class AirVisualNodeProSensor(AirVisualEntity, AirQualityEntity):
    """Define a sensor for a AirVisual Node/Pro."""

    def __init__(self, airvisual):
        """Initialize."""
        super().__init__(airvisual)

        self._icon = "mdi:chemical-weapon"
        self._unit = CONCENTRATION_MICROGRAMS_PER_CUBIC_METER

    @property
    def air_quality_index(self):
        """Return the Air Quality Index (AQI)."""
        if self._airvisual.data["current"]["settings"]["is_aqi_usa"]:
            return self._airvisual.data["current"]["measurements"]["aqi_us"]
        return self._airvisual.data["current"]["measurements"]["aqi_cn"]

    @property
    def available(self):
        """Return True if entity is available."""
        return bool(self._airvisual.data)

    @property
    def carbon_dioxide(self):
        """Return the CO2 (carbon dioxide) level."""
        return self._airvisual.data["current"]["measurements"].get("co2_ppm")

    @property
    def device_info(self):
        """Return device registry information for this entity."""
        return {
            "identifiers": {(DOMAIN, self._airvisual.data["current"]["serial_number"])},
            "name": self._airvisual.data["current"]["settings"]["node_name"],
            "manufacturer": "AirVisual",
            "model": f'{self._airvisual.data["current"]["status"]["model"]}',
            "sw_version": (
                f'Version {self._airvisual.data["current"]["status"]["system_version"]}'
                f'{self._airvisual.data["current"]["status"]["app_version"]}'
            ),
        }

    @property
    def name(self):
        """Return the name."""
        return f"{self._airvisual.data['current']['settings']['node_name']} Air Quality"

    @property
    def particulate_matter_2_5(self):
        """Return the particulate matter 2.5 level."""
        return self._airvisual.data["current"]["measurements"].get("pm2_5")

    @property
    def particulate_matter_10(self):
        """Return the particulate matter 10 level."""
        return self._airvisual.data["current"]["measurements"].get("pm1_0")

    @property
    def particulate_matter_0_1(self):
        """Return the particulate matter 0.1 level."""
        return self._airvisual.data["current"]["measurements"].get("pm0_1")

    @property
    def unique_id(self):
        """Return a unique, Home Assistant friendly identifier for this entity."""
        return self._airvisual.data["current"]["serial_number"]

    @callback
    def update_from_latest_data(self):
        """Update the Node/Pro's data."""
        trends = {
            ATTR_TREND.format(slugify(pollutant)): trend
            for pollutant, trend in self._airvisual.data["trends"].items()
        }
        if self._airvisual.data["current"]["settings"]["is_aqi_usa"]:
            trends.pop(ATTR_TREND.format("aqi_cn"))
        else:
            trends.pop(ATTR_TREND.format("aqi_us"))

        self._attrs.update(
            {
                ATTR_BATTERY_LEVEL: self._airvisual.data["current"]["status"][
                    "battery"
                ],
                ATTR_HUMIDITY: self._airvisual.data["current"]["measurements"].get(
                    "humidity"
                ),
                ATTR_TEMPERATURE: display_temp(
                    self.hass,
                    float(
                        self._airvisual.data["current"]["measurements"].get(
                            "temperature_C"
                        )
                    ),
                    TEMP_CELSIUS,
                    PRECISION_TENTHS,
                ),
                ATTR_VOC: self._airvisual.data["current"]["measurements"].get("voc"),
                **{
                    ATTR_SENSOR_LIFE.format(pollutant): lifespan
                    for pollutant, lifespan in self._airvisual.data["current"][
                        "status"
                    ]["sensor_life"].items()
                },
                **trends,
            }
        )
