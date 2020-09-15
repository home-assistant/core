"""Support for the AirNow air_quality service."""
from homeassistant.components.air_quality import ATTR_AQI, AirQualityEntity
from homeassistant.const import CONF_NAME
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_API_AQI,
    ATTR_API_AQI_DESCRIPTION,
    ATTR_API_AQI_LEVEL,
    ATTR_API_O3,
    ATTR_API_PM25,
    ATTR_API_POLLUTANT,
    ATTR_API_REPORT_DATE,
    ATTR_API_REPORT_HOUR,
    ATTR_API_STATE,
    ATTR_API_STATION,
    ATTR_API_STATION_LATITUDE,
    ATTR_API_STATION_LONGITUDE,
    DOMAIN,
)

ATTRIBUTION = "Data provided by AirNow"

LABEL_AQI_LEVEL = f"{ATTR_AQI}_level"
LABEL_AQI_DESCRIPTION = f"{ATTR_AQI}_description"
LABEL_AQI_POLLUTANT = "aqi_pollutant"
LABEL_REPORT_DATE = "report_date"
LABEL_REPORT_HOUR = "report_hour"
LABEL_REPORTING_AREA = "reporting_area"
LABEL_STATION_LATITUDE = "station_latitude"
LABEL_STATION_LONGITUDE = "station_longitude"

PARALLEL_UPDATES = 1


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Airly air_quality entity based on a config entry."""
    name = config_entry.data[CONF_NAME]
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities([AirNowAirQuality(coordinator, name)], False)


class AirNowAirQuality(CoordinatorEntity, AirQualityEntity):
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
    def air_quality_index(self):
        """Return the air quality index."""
        return self.coordinator.data[ATTR_API_AQI]

    @property
    def particulate_matter_2_5(self):
        """Return the particulate matter 2.5 level."""
        return self.coordinator.data[ATTR_API_PM25]

    @property
    def ozone(self):
        """Return the O3 (ozone) level."""
        return self.coordinator.data[ATTR_API_O3]

    @property
    def attribution(self):
        """Return the attribution."""
        return ATTRIBUTION

    @property
    def unique_id(self):
        """Return a unique_id for this entity."""
        return f"{self.coordinator.latitude}-{self.coordinator.longitude}"

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {
            LABEL_AQI_LEVEL: self.coordinator.data[ATTR_API_AQI_LEVEL],
            LABEL_AQI_DESCRIPTION: self.coordinator.data[ATTR_API_AQI_DESCRIPTION],
            LABEL_AQI_POLLUTANT: self.coordinator.data[ATTR_API_POLLUTANT],
            LABEL_REPORT_DATE: self.coordinator.data[ATTR_API_REPORT_DATE],
            LABEL_REPORT_HOUR: self.coordinator.data[ATTR_API_REPORT_HOUR],
            LABEL_REPORTING_AREA: f"{self.coordinator.data[ATTR_API_STATION]}, {self.coordinator.data[ATTR_API_STATE]}",
            LABEL_STATION_LATITUDE: self.coordinator.data[ATTR_API_STATION_LATITUDE],
            LABEL_STATION_LONGITUDE: self.coordinator.data[ATTR_API_STATION_LONGITUDE],
        }
