"""Support for AirVisual air quality sensors."""
from logging import getLogger

from homeassistant.const import (
    ATTR_ATTRIBUTION,
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
)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import CONF_CITY, CONF_COUNTRY, DATA_CLIENT, DOMAIN, TOPIC_UPDATE

_LOGGER = getLogger(__name__)

ATTR_CITY = "city"
ATTR_COUNTRY = "country"
ATTR_POLLUTANT_SYMBOL = "pollutant_symbol"
ATTR_POLLUTANT_UNIT = "pollutant_unit"
ATTR_REGION = "region"

DEFAULT_ATTRIBUTION = "Data provided by AirVisual"

MASS_PARTS_PER_MILLION = "ppm"
MASS_PARTS_PER_BILLION = "ppb"
VOLUME_MICROGRAMS_PER_CUBIC_METER = "µg/m3"

SENSOR_KIND_LEVEL = "air_pollution_level"
SENSOR_KIND_AQI = "air_quality_index"
SENSOR_KIND_POLLUTANT = "main_pollutant"
SENSORS = [
    (SENSOR_KIND_LEVEL, "Air Pollution Level", "mdi:gauge", None),
    (SENSOR_KIND_AQI, "Air Quality Index", "mdi:chart-line", "AQI"),
    (SENSOR_KIND_POLLUTANT, "Main Pollutant", "mdi:chemical-weapon", None),
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

SENSOR_LOCALES = {"cn": "Chinese", "us": "U.S."}


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up AirVisual sensors based on a config entry."""
    airvisual = hass.data[DOMAIN][DATA_CLIENT][entry.entry_id]

    async_add_entities(
        [
            AirVisualSensor(airvisual, kind, name, icon, unit, locale, geography_id)
            for geography_id in airvisual.data
            for locale in SENSOR_LOCALES
            for kind, name, icon, unit in SENSORS
        ],
        True,
    )


class AirVisualSensor(Entity):
    """Define an AirVisual sensor."""

    def __init__(self, airvisual, kind, name, icon, unit, locale, geography_id):
        """Initialize."""
        self._airvisual = airvisual
        self._async_unsub_dispatcher_connects = []
        self._geography_id = geography_id
        self._icon = icon
        self._kind = kind
        self._locale = locale
        self._name = name
        self._state = None
        self._unit = unit

        self._attrs = {
            ATTR_ATTRIBUTION: DEFAULT_ATTRIBUTION,
            ATTR_CITY: airvisual.data[geography_id].get(CONF_CITY),
            ATTR_STATE: airvisual.data[geography_id].get(CONF_STATE),
            ATTR_COUNTRY: airvisual.data[geography_id].get(CONF_COUNTRY),
        }

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
    def device_state_attributes(self):
        """Return the device state attributes."""
        return self._attrs

    @property
    def icon(self):
        """Return the icon."""
        return self._icon

    @property
    def name(self):
        """Return the name."""
        return f"{SENSOR_LOCALES[self._locale]} {self._name}"

    @property
    def state(self):
        """Return the state."""
        return self._state

    @property
    def unique_id(self):
        """Return a unique, Home Assistant friendly identifier for this entity."""
        return f"{self._geography_id}_{self._locale}_{self._kind}"

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit

    async def async_added_to_hass(self):
        """Register callbacks."""

        @callback
        def update():
            """Update the state."""
            self.async_schedule_update_ha_state(True)

        self._async_unsub_dispatcher_connects.append(
            async_dispatcher_connect(self.hass, TOPIC_UPDATE, update)
        )

    async def async_update(self):
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

    async def async_will_remove_from_hass(self) -> None:
        """Disconnect dispatcher listener when removed."""
        for cancel in self._async_unsub_dispatcher_connects:
            cancel()
        self._async_unsub_dispatcher_connects = []
