"""Support for AirVisual Node/Pro units."""
from homeassistant.components.air_quality import AirQualityEntity
from homeassistant.const import CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
from homeassistant.core import callback

from . import AirVisualEntity
from .const import (
    CONF_INTEGRATION_TYPE,
    DATA_COORDINATOR,
    DOMAIN,
    INTEGRATION_TYPE_NODE_PRO,
)

ATTR_HUMIDITY = "humidity"
ATTR_SENSOR_LIFE = "{0}_sensor_life"
ATTR_VOC = "voc"


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up AirVisual air quality entities based on a config entry."""
    # Geography-based AirVisual integrations don't utilize this platform:
    if config_entry.data[CONF_INTEGRATION_TYPE] != INTEGRATION_TYPE_NODE_PRO:
        return

    coordinator = hass.data[DOMAIN][DATA_COORDINATOR][config_entry.entry_id]

    async_add_entities([AirVisualNodeProSensor(coordinator)], True)


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
        if self.coordinator.data["settings"]["is_aqi_usa"]:
            return self.coordinator.data["measurements"]["aqi_us"]
        return self.coordinator.data["measurements"]["aqi_cn"]

    @property
    def available(self):
        """Return True if entity is available."""
        return bool(self.coordinator.data)

    @property
    def carbon_dioxide(self):
        """Return the CO2 (carbon dioxide) level."""
        return self.coordinator.data["measurements"].get("co2")

    @property
    def device_info(self):
        """Return device registry information for this entity."""
        return {
            "identifiers": {(DOMAIN, self.coordinator.data["serial_number"])},
            "name": self.coordinator.data["settings"]["node_name"],
            "manufacturer": "AirVisual",
            "model": f'{self.coordinator.data["status"]["model"]}',
            "sw_version": (
                f'Version {self.coordinator.data["status"]["system_version"]}'
                f'{self.coordinator.data["status"]["app_version"]}'
            ),
        }

    @property
    def name(self):
        """Return the name."""
        node_name = self.coordinator.data["settings"]["node_name"]
        return f"{node_name} Node/Pro: Air Quality"

    @property
    def particulate_matter_2_5(self):
        """Return the particulate matter 2.5 level."""
        return self.coordinator.data["measurements"].get("pm2_5")

    @property
    def particulate_matter_10(self):
        """Return the particulate matter 10 level."""
        return self.coordinator.data["measurements"].get("pm1_0")

    @property
    def particulate_matter_0_1(self):
        """Return the particulate matter 0.1 level."""
        return self.coordinator.data["measurements"].get("pm0_1")

    @property
    def unique_id(self):
        """Return a unique, Home Assistant friendly identifier for this entity."""
        return self.coordinator.data["serial_number"]

    @callback
    def update_from_latest_data(self):
        """Update the entity from the latest data."""
        self._attrs.update(
            {
                ATTR_VOC: self.coordinator.data["measurements"].get("voc"),
                **{
                    ATTR_SENSOR_LIFE.format(pollutant): lifespan
                    for pollutant, lifespan in self.coordinator.data["status"][
                        "sensor_life"
                    ].items()
                },
            }
        )
