"""Support for the Airly air_quality service."""
from homeassistant.components.air_quality import (
    ATTR_AQI,
    ATTR_PM_2_5,
    ATTR_PM_10,
    AirQualityEntity,
)
from homeassistant.const import CONF_NAME

from .const import (
    ATTR_API_ADVICE,
    ATTR_API_CAQI,
    ATTR_API_CAQI_DESCRIPTION,
    ATTR_API_CAQI_LEVEL,
    ATTR_API_PM10,
    ATTR_API_PM10_LIMIT,
    ATTR_API_PM10_PERCENT,
    ATTR_API_PM25,
    ATTR_API_PM25_LIMIT,
    ATTR_API_PM25_PERCENT,
    DATA_CLIENT,
    DOMAIN,
)

ATTRIBUTION = "Data provided by Airly"

LABEL_ADVICE = "advice"
LABEL_AQI_LEVEL = f"{ATTR_AQI}_level"
LABEL_PM_2_5_LIMIT = f"{ATTR_PM_2_5}_limit"
LABEL_PM_2_5_PERCENT = f"{ATTR_PM_2_5}_percent_of_limit"
LABEL_PM_10_LIMIT = f"{ATTR_PM_10}_limit"
LABEL_PM_10_PERCENT = f"{ATTR_PM_10}_percent_of_limit"


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Airly air_quality entity based on a config entry."""
    name = config_entry.data[CONF_NAME]

    data = hass.data[DOMAIN][DATA_CLIENT][config_entry.entry_id]

    async_add_entities([AirlyAirQuality(data, name, config_entry.unique_id)], True)


def round_state(func):
    """Round state."""

    def _decorator(self):
        res = func(self)
        if isinstance(res, float):
            return round(res)
        return res

    return _decorator


class AirlyAirQuality(AirQualityEntity):
    """Define an Airly air quality."""

    def __init__(self, airly, name, unique_id):
        """Initialize."""
        self.airly = airly
        self.data = airly.data
        self._name = name
        self._unique_id = unique_id
        self._pm_2_5 = None
        self._pm_10 = None
        self._aqi = None
        self._icon = "mdi:blur"
        self._attrs = {}

    @property
    def name(self):
        """Return the name."""
        return self._name

    @property
    def icon(self):
        """Return the icon."""
        return self._icon

    @property
    @round_state
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
    def attribution(self):
        """Return the attribution."""
        return ATTRIBUTION

    @property
    def state(self):
        """Return the CAQI description."""
        return self.data[ATTR_API_CAQI_DESCRIPTION]

    @property
    def unique_id(self):
        """Return a unique_id for this entity."""
        return self._unique_id

    @property
    def available(self):
        """Return True if entity is available."""
        return bool(self.data)

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        self._attrs[LABEL_ADVICE] = self.data[ATTR_API_ADVICE]
        self._attrs[LABEL_AQI_LEVEL] = self.data[ATTR_API_CAQI_LEVEL]
        self._attrs[LABEL_PM_2_5_LIMIT] = self.data[ATTR_API_PM25_LIMIT]
        self._attrs[LABEL_PM_2_5_PERCENT] = round(self.data[ATTR_API_PM25_PERCENT])
        self._attrs[LABEL_PM_10_LIMIT] = self.data[ATTR_API_PM10_LIMIT]
        self._attrs[LABEL_PM_10_PERCENT] = round(self.data[ATTR_API_PM10_PERCENT])
        return self._attrs

    async def async_update(self):
        """Update the entity."""
        await self.airly.async_update()

        if self.airly.data:
            self.data = self.airly.data
            self._pm_10 = self.data[ATTR_API_PM10]
            self._pm_2_5 = self.data[ATTR_API_PM25]
            self._aqi = self.data[ATTR_API_CAQI]
