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
    DOMAIN,
)

ATTRIBUTION = "Data provided by Airly"

LABEL_ADVICE = "advice"
LABEL_AQI_DESCRIPTION = f"{ATTR_AQI}_description"
LABEL_AQI_LEVEL = f"{ATTR_AQI}_level"
LABEL_PM_2_5_LIMIT = f"{ATTR_PM_2_5}_limit"
LABEL_PM_2_5_PERCENT = f"{ATTR_PM_2_5}_percent_of_limit"
LABEL_PM_10_LIMIT = f"{ATTR_PM_10}_limit"
LABEL_PM_10_PERCENT = f"{ATTR_PM_10}_percent_of_limit"


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Airly air_quality entity based on a config entry."""
    name = config_entry.data[CONF_NAME]

    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        [AirlyAirQuality(coordinator, name, config_entry.unique_id)], False
    )


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

    def __init__(self, coordinator, name, unique_id):
        """Initialize."""
        self.coordinator = coordinator
        self._name = name
        self._unique_id = unique_id
        self._icon = "mdi:blur"

    @property
    def name(self):
        """Return the name."""
        return self._name

    @property
    def should_poll(self):
        """Return the polling requirement of the entity."""
        return False

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
        return self.coordinator.data[ATTR_API_PM25]

    @property
    @round_state
    def particulate_matter_10(self):
        """Return the particulate matter 10 level."""
        return self.coordinator.data[ATTR_API_PM10]

    @property
    def attribution(self):
        """Return the attribution."""
        return ATTRIBUTION

    @property
    def unique_id(self):
        """Return a unique_id for this entity."""
        return self._unique_id

    @property
    def available(self):
        """Return True if entity is available."""
        return self.coordinator.last_update_success

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {
            LABEL_AQI_DESCRIPTION: self.coordinator.data[ATTR_API_CAQI_DESCRIPTION],
            LABEL_ADVICE: self.coordinator.data[ATTR_API_ADVICE],
            LABEL_AQI_LEVEL: self.coordinator.data[ATTR_API_CAQI_LEVEL],
            LABEL_PM_2_5_LIMIT: self.coordinator.data[ATTR_API_PM25_LIMIT],
            LABEL_PM_2_5_PERCENT: round(self.coordinator.data[ATTR_API_PM25_PERCENT]),
            LABEL_PM_10_LIMIT: self.coordinator.data[ATTR_API_PM10_LIMIT],
            LABEL_PM_10_PERCENT: round(self.coordinator.data[ATTR_API_PM10_PERCENT]),
        }

    async def async_added_to_hass(self):
        """Connect to dispatcher listening for entity data notifications."""
        self.coordinator.async_add_listener(self.async_write_ha_state)

    async def async_will_remove_from_hass(self):
        """Disconnect from update signal."""
        self.coordinator.async_remove_listener(self.async_write_ha_state)

    async def async_update(self):
        """Update Airly entity."""
        await self.coordinator.async_request_refresh()
