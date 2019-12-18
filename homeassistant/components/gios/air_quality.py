"""Support for the GIOS service."""
from homeassistant.components.air_quality import (
    ATTR_CO,
    ATTR_NO2,
    ATTR_OZONE,
    ATTR_PM_2_5,
    ATTR_PM_10,
    ATTR_SO2,
    AirQualityEntity,
)
from homeassistant.const import CONF_NAME

from .const import ATTR_STATION, DATA_CLIENT, DEFAULT_SCAN_INTERVAL, DOMAIN, ICONS_MAP

ATTRIBUTION = "Data provided by GIOŚ"
SCAN_INTERVAL = DEFAULT_SCAN_INTERVAL


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Add a GIOS entities from a config_entry."""
    name = config_entry.data[CONF_NAME]

    data = hass.data[DOMAIN][DATA_CLIENT][config_entry.entry_id]

    async_add_entities([GiosAirQuality(data, name)], True)


def round_state(func):
    """Round state."""

    def _decorator(self):
        res = func(self)
        if isinstance(res, float):
            return round(res)
        return res

    return _decorator


class GiosAirQuality(AirQualityEntity):
    """Define an GIOS sensor."""

    def __init__(self, gios, name):
        """Initialize."""
        self.gios = gios
        self._name = name
        self._aqi = None
        self._co = None
        self._no2 = None
        self._o3 = None
        self._pm_2_5 = None
        self._pm_10 = None
        self._so2 = None
        self._attrs = {}

    @property
    def name(self):
        """Return the name."""
        return self._name

    @property
    def icon(self):
        """Return the icon."""
        if self._aqi in ICONS_MAP:
            return ICONS_MAP[self._aqi]
        return "mdi:blur"

    @property
    def air_quality_index(self):
        """Return the air quality index."""
        return self._aqi

    @property
    @round_state
    def particulate_matter_2_5(self):
        """Return the particulate matter 2.5 level."""
        return self._pm_2_5

    @property
    @round_state
    def particulate_matter_10(self):
        """Return the particulate matter 10 level."""
        return self._pm_10

    @property
    @round_state
    def ozone(self):
        """Return the O3 (ozone) level."""
        return self._o3

    @property
    @round_state
    def carbon_monoxide(self):
        """Return the CO (carbon monoxide) level."""
        return self._co

    @property
    @round_state
    def sulphur_dioxide(self):
        """Return the SO2 (sulphur dioxide) level."""
        return self._so2

    @property
    @round_state
    def nitrogen_dioxide(self):
        """Return the NO2 (nitrogen dioxide) level."""
        return self._no2

    @property
    def attribution(self):
        """Return the attribution."""
        return ATTRIBUTION

    @property
    def unique_id(self):
        """Return a unique_id for this entity."""
        return self.gios.station_id

    @property
    def available(self):
        """Return True if entity is available."""
        return self.gios.available

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        self._attrs[ATTR_STATION] = self.gios.station_name
        return self._attrs

    async def async_update(self):
        """Get the data from GIOS."""
        await self.gios.async_update()

        if self.gios.available:
            # Different measuring stations have different sets of sensors. We don't know
            # what data we will get.
            if "AQI" in self.gios.sensors:
                self._aqi = self.gios.sensors["AQI"]["value"]
            if "CO" in self.gios.sensors:
                self._co = self.gios.sensors["CO"]["value"]
                self._attrs[f"{ATTR_CO}_index"] = self.gios.sensors["CO"]["index"]
            if "NO2" in self.gios.sensors:
                self._no2 = self.gios.sensors["NO2"]["value"]
                self._attrs[f"{ATTR_NO2}_index"] = self.gios.sensors["NO2"]["index"]
            if "O3" in self.gios.sensors:
                self._o3 = self.gios.sensors["O3"]["value"]
                self._attrs[f"{ATTR_OZONE}_index"] = self.gios.sensors["O3"]["index"]
            if "PM2.5" in self.gios.sensors:
                self._pm_2_5 = self.gios.sensors["PM2.5"]["value"]
                self._attrs[f"{ATTR_PM_2_5}_index"] = self.gios.sensors["PM2.5"][
                    "index"
                ]
            if "PM10" in self.gios.sensors:
                self._pm_10 = self.gios.sensors["PM10"]["value"]
                self._attrs[f"{ATTR_PM_10}_index"] = self.gios.sensors["PM10"]["index"]
            if "SO2" in self.gios.sensors:
                self._so2 = self.gios.sensors["SO2"]["value"]
                self._attrs[f"{ATTR_SO2}_index"] = self.gios.sensors["SO2"]["index"]
