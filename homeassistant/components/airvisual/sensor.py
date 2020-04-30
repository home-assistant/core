"""Support for AirVisual air quality sensors."""
from logging import getLogger

from homeassistant.const import (
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    ATTR_STATE,
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_BILLION,
    CONCENTRATION_PARTS_PER_MILLION,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_SHOW_ON_MAP,
    CONF_STATE,
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_TEMPERATURE,
    TEMP_CELSIUS,
    UNIT_PERCENTAGE,
)
from homeassistant.core import callback

from . import AirVisualEntity
from .const import (
    CONF_CITY,
    CONF_COUNTRY,
    DATA_CLIENT,
    DOMAIN,
    INTEGRATION_TYPE_GEOGRAPHY,
)

_LOGGER = getLogger(__name__)

ATTR_CITY = "city"
ATTR_COUNTRY = "country"
ATTR_POLLUTANT_SYMBOL = "pollutant_symbol"
ATTR_POLLUTANT_UNIT = "pollutant_unit"
ATTR_REGION = "region"

MASS_PARTS_PER_MILLION = "ppm"
MASS_PARTS_PER_BILLION = "ppb"
VOLUME_MICROGRAMS_PER_CUBIC_METER = "µg/m3"

SENSOR_KIND_LEVEL = "air_pollution_level"
SENSOR_KIND_AQI = "air_quality_index"
SENSOR_KIND_POLLUTANT = "main_pollutant"
SENSOR_KIND_BATTERY_LEVEL = "battery_level"
SENSOR_KIND_HUMIDITY = "humidity"
SENSOR_KIND_TEMPERATURE = "temperature"

GEOGRAPHY_SENSORS = [
    (SENSOR_KIND_LEVEL, "Air Pollution Level", "mdi:gauge", None),
    (SENSOR_KIND_AQI, "Air Quality Index", "mdi:chart-line", "AQI"),
    (SENSOR_KIND_POLLUTANT, "Main Pollutant", "mdi:chemical-weapon", None),
]
GEOGRAPHY_SENSOR_LOCALES = {"cn": "Chinese", "us": "U.S."}

NODE_PRO_SENSORS = [
    (SENSOR_KIND_BATTERY_LEVEL, "Battery", DEVICE_CLASS_BATTERY, UNIT_PERCENTAGE),
    (SENSOR_KIND_HUMIDITY, "Humidity", DEVICE_CLASS_HUMIDITY, UNIT_PERCENTAGE),
    (SENSOR_KIND_TEMPERATURE, "Temperature", DEVICE_CLASS_TEMPERATURE, TEMP_CELSIUS),
]

POLLUTANT_LEVEL_MAPPING = [
    {"label": "Good", "icon": "mdi:emoticon-excited", "minimum": 0, "maximum": 50},
    {"label": "Moderate", "icon": "mdi:emoticon-happy", "minimum": 51, "maximum": 100},
    {
        "label": "Unhealthy for sensitive groups",
        "icon": "mdi:emoticon-neutral",
        "minimum": 101,
        "maximum": 150,
    },
    {"label": "Unhealthy", "icon": "mdi:emoticon-sad", "minimum": 151, "maximum": 200},
    {
        "label": "Very Unhealthy",
        "icon": "mdi:emoticon-dead",
        "minimum": 201,
        "maximum": 300,
    },
    {"label": "Hazardous", "icon": "mdi:biohazard", "minimum": 301, "maximum": 10000},
]

POLLUTANT_MAPPING = {
    "co": {"label": "Carbon Monoxide", "unit": CONCENTRATION_PARTS_PER_MILLION},
    "n2": {"label": "Nitrogen Dioxide", "unit": CONCENTRATION_PARTS_PER_BILLION},
    "o3": {"label": "Ozone", "unit": CONCENTRATION_PARTS_PER_BILLION},
    "p1": {"label": "PM10", "unit": CONCENTRATION_MICROGRAMS_PER_CUBIC_METER},
    "p2": {"label": "PM2.5", "unit": CONCENTRATION_MICROGRAMS_PER_CUBIC_METER},
    "s2": {"label": "Sulfur Dioxide", "unit": CONCENTRATION_PARTS_PER_BILLION},
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up AirVisual sensors based on a config entry."""
    airvisual = hass.data[DOMAIN][DATA_CLIENT][config_entry.entry_id]

    if airvisual.integration_type == INTEGRATION_TYPE_GEOGRAPHY:
        sensors = [
            AirVisualGeographySensor(
                airvisual, kind, name, icon, unit, locale, geography_id,
            )
            for geography_id in airvisual.data
            for locale in GEOGRAPHY_SENSOR_LOCALES
            for kind, name, icon, unit in GEOGRAPHY_SENSORS
        ]
    else:
        sensors = [
            AirVisualNodeProSensor(airvisual, kind, name, device_class, unit)
            for kind, name, device_class, unit in NODE_PRO_SENSORS
        ]

    async_add_entities(sensors, True)


class AirVisualSensor(AirVisualEntity):
    """Define a generic AirVisual sensor."""

    def __init__(self, airvisual, kind, name, unit):
        """Initialize."""
        super().__init__(airvisual)

        self._kind = kind
        self._name = name
        self._state = None
        self._unit = unit

    @property
    def state(self):
        """Return the state."""
        return self._state


class AirVisualGeographySensor(AirVisualSensor):
    """Define an AirVisual sensor related to geography data via the Cloud API."""

    def __init__(self, airvisual, kind, name, icon, unit, locale, geography_id):
        """Initialize."""
        super().__init__(airvisual, kind, name, unit)

        self._attrs.update(
            {
                ATTR_CITY: airvisual.data[geography_id].get(CONF_CITY),
                ATTR_STATE: airvisual.data[geography_id].get(CONF_STATE),
                ATTR_COUNTRY: airvisual.data[geography_id].get(CONF_COUNTRY),
            }
        )
        self._geography_id = geography_id
        self._icon = icon
        self._locale = locale

    @property
    def available(self):
        """Return True if entity is available."""
        try:
            return bool(
                self._airvisual.data[self._geography_id]["current"]["pollution"]
            )
        except KeyError:
            return False

    @property
    def name(self):
        """Return the name."""
        return f"{GEOGRAPHY_SENSOR_LOCALES[self._locale]} {self._name}"

    @property
    def unique_id(self):
        """Return a unique, Home Assistant friendly identifier for this entity."""
        return f"{self._geography_id}_{self._locale}_{self._kind}"

    @callback
    def update_from_latest_data(self):
        """Update the sensor."""
        try:
            data = self._airvisual.data[self._geography_id]["current"]["pollution"]
        except KeyError:
            return

        if self._kind == SENSOR_KIND_LEVEL:
            aqi = data[f"aqi{self._locale}"]
            [level] = [
                i
                for i in POLLUTANT_LEVEL_MAPPING
                if i["minimum"] <= aqi <= i["maximum"]
            ]
            self._state = level["label"]
            self._icon = level["icon"]
        elif self._kind == SENSOR_KIND_AQI:
            self._state = data[f"aqi{self._locale}"]
        elif self._kind == SENSOR_KIND_POLLUTANT:
            symbol = data[f"main{self._locale}"]
            self._state = POLLUTANT_MAPPING[symbol]["label"]
            self._attrs.update(
                {
                    ATTR_POLLUTANT_SYMBOL: symbol,
                    ATTR_POLLUTANT_UNIT: POLLUTANT_MAPPING[symbol]["unit"],
                }
            )

        if CONF_LATITUDE in self._airvisual.geography_data:
            if self._airvisual.options[CONF_SHOW_ON_MAP]:
                self._attrs[ATTR_LATITUDE] = self._airvisual.geography_data[
                    CONF_LATITUDE
                ]
                self._attrs[ATTR_LONGITUDE] = self._airvisual.geography_data[
                    CONF_LONGITUDE
                ]
                self._attrs.pop("lati", None)
                self._attrs.pop("long", None)
            else:
                self._attrs["lati"] = self._airvisual.geography_data[CONF_LATITUDE]
                self._attrs["long"] = self._airvisual.geography_data[CONF_LONGITUDE]
                self._attrs.pop(ATTR_LATITUDE, None)
                self._attrs.pop(ATTR_LONGITUDE, None)


class AirVisualNodeProSensor(AirVisualSensor):
    """Define an AirVisual sensor related to a Node/Pro unit."""

    def __init__(self, airvisual, kind, name, device_class, unit):
        """Initialize."""
        super().__init__(airvisual, kind, name, unit)

        self._device_class = device_class

    @property
    def available(self):
        """Return True if entity is available."""
        return bool(self._airvisual.data)

    @property
    def device_class(self):
        """Return the device class."""
        return self._device_class

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
        node_name = self._airvisual.data["current"]["settings"]["node_name"]
        return f"{node_name} Node/Pro: {self._name}"

    @property
    def unique_id(self):
        """Return a unique, Home Assistant friendly identifier for this entity."""
        return f"{self._airvisual.data['current']['serial_number']}_{self._kind}"

    @callback
    def update_from_latest_data(self):
        """Update from the Node/Pro's data."""
        if self._kind == SENSOR_KIND_BATTERY_LEVEL:
            self._state = self._airvisual.data["current"]["status"]["battery"]
        elif self._kind == SENSOR_KIND_HUMIDITY:
            self._state = self._airvisual.data["current"]["measurements"].get(
                "humidity"
            )
        elif self._kind == SENSOR_KIND_TEMPERATURE:
            self._state = self._airvisual.data["current"]["measurements"].get(
                "temperature_C"
            )
