"""Support for the Airly air_quality service."""
from homeassistant.components.air_quality import (
    ATTR_AQI,
    ATTR_PM_2_5,
    ATTR_PM_10,
    AirQualityEntity,
)
from homeassistant.const import CONF_NAME
from homeassistant.helpers.update_coordinator import CoordinatorEntity

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
    ATTRIBUTION,
    DEFAULT_NAME,
    DOMAIN,
    LABEL_ADVICE,
    MANUFACTURER,
)

LABEL_AQI_DESCRIPTION = f"{ATTR_AQI}_description"
LABEL_AQI_LEVEL = f"{ATTR_AQI}_level"
LABEL_PM_2_5_LIMIT = f"{ATTR_PM_2_5}_limit"
LABEL_PM_2_5_PERCENT = f"{ATTR_PM_2_5}_percent_of_limit"
LABEL_PM_10_LIMIT = f"{ATTR_PM_10}_limit"
LABEL_PM_10_PERCENT = f"{ATTR_PM_10}_percent_of_limit"

PARALLEL_UPDATES = 1


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Airly air_quality entity based on a config entry."""
    name = config_entry.data[CONF_NAME]

    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities([AirlyAirQuality(coordinator, name)], False)


def round_state(func):
    """Round state."""

    def _decorator(self):
        res = func(self)
        if isinstance(res, float):
            return round(res)
        return res

    return _decorator


class AirlyAirQuality(CoordinatorEntity, AirQualityEntity):
    """Define an Airly air quality."""

    def __init__(self, coordinator, name):
        """Initialize."""
        super().__init__(coordinator)
        self._name = name
        self._icon = "mdi:blur"

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
        return self.coordinator.data[ATTR_API_CAQI]

    @property
    @round_state
    def particulate_matter_2_5(self):
        """Return the particulate matter 2.5 level."""
        return self.coordinator.data.get(ATTR_API_PM25)

    @property
    @round_state
    def particulate_matter_10(self):
        """Return the particulate matter 10 level."""
        return self.coordinator.data.get(ATTR_API_PM10)

    @property
    def attribution(self):
        """Return the attribution."""
        return ATTRIBUTION

    @property
    def unique_id(self):
        """Return a unique_id for this entity."""
        return f"{self.coordinator.latitude}-{self.coordinator.longitude}"

    @property
    def device_info(self):
        """Return the device info."""
        return {
            "identifiers": {
                (DOMAIN, self.coordinator.latitude, self.coordinator.longitude)
            },
            "name": DEFAULT_NAME,
            "manufacturer": MANUFACTURER,
            "entry_type": "service",
        }

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        attrs = {
            LABEL_AQI_DESCRIPTION: self.coordinator.data[ATTR_API_CAQI_DESCRIPTION],
            LABEL_ADVICE: self.coordinator.data[ATTR_API_ADVICE],
            LABEL_AQI_LEVEL: self.coordinator.data[ATTR_API_CAQI_LEVEL],
        }
        if ATTR_API_PM25 in self.coordinator.data:
            attrs[LABEL_PM_2_5_LIMIT] = self.coordinator.data[ATTR_API_PM25_LIMIT]
            attrs[LABEL_PM_2_5_PERCENT] = round(
                self.coordinator.data[ATTR_API_PM25_PERCENT]
            )
        if ATTR_API_PM10 in self.coordinator.data:
            attrs[LABEL_PM_10_LIMIT] = self.coordinator.data[ATTR_API_PM10_LIMIT]
            attrs[LABEL_PM_10_PERCENT] = round(
                self.coordinator.data[ATTR_API_PM10_PERCENT]
            )
        return attrs
