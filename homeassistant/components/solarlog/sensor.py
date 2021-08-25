"""Platform for solarlog sensors."""
import logging
from urllib.parse import ParseResult, urlparse

from requests.exceptions import HTTPError, Timeout
from sunwatcher.solarlog.solarlog import SolarLog

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import CONF_HOST
from homeassistant.util import Throttle

from .const import DOMAIN, SCAN_INTERVAL, SENSOR_TYPES, SolarLogSensorEntityDescription

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the solarlog platform."""
    _LOGGER.warning(
        "Configuration of the solarlog platform in configuration.yaml is deprecated "
        "in Home Assistant 0.119. Please remove entry from your configuration"
    )


async def async_setup_entry(hass, entry, async_add_entities):
    """Add solarlog entry."""
    host_entry = entry.data[CONF_HOST]
    device_name = entry.title

    url = urlparse(host_entry, "http")
    netloc = url.netloc or url.path
    path = url.path if url.netloc else ""
    url = ParseResult("http", netloc, path, *url[3:])
    host = url.geturl()

    try:
        api = await hass.async_add_executor_job(SolarLog, host)
        _LOGGER.debug("Connected to Solar-Log device, setting up entries")
    except (OSError, HTTPError, Timeout):
        _LOGGER.error(
            "Could not connect to Solar-Log device at %s, check host ip address", host
        )
        return

    # Create solarlog data service which will retrieve and update the data.
    data = await hass.async_add_executor_job(SolarlogData, hass, api, host)

    # Create a new sensor for each sensor type.
    entities = [
        SolarlogSensor(entry.entry_id, device_name, data, description)
        for description in SENSOR_TYPES
    ]
    async_add_entities(entities, True)
    return True


class SolarlogData:
    """Get and update the latest data."""

    def __init__(self, hass, api, host):
        """Initialize the data object."""
        self.api = api
        self.hass = hass
        self.host = host
        self.update = Throttle(SCAN_INTERVAL)(self._update)
        self.data = {}

    def _update(self):
        """Update the data from the SolarLog device."""
        try:
            self.api = SolarLog(self.host)
            response = self.api.time
            _LOGGER.debug(
                "Connection to Solarlog successful. Retrieving latest Solarlog update of %s",
                response,
            )
        except (OSError, Timeout, HTTPError):
            _LOGGER.error("Connection error, Could not retrieve data, skipping update")
            return

        try:
            self.data["TIME"] = self.api.time
            self.data["powerAC"] = self.api.power_ac
            self.data["powerDC"] = self.api.power_dc
            self.data["voltageAC"] = self.api.voltage_ac
            self.data["voltageDC"] = self.api.voltage_dc
            self.data["yieldDAY"] = self.api.yield_day / 1000
            self.data["yieldYESTERDAY"] = self.api.yield_yesterday / 1000
            self.data["yieldMONTH"] = self.api.yield_month / 1000
            self.data["yieldYEAR"] = self.api.yield_year / 1000
            self.data["yieldTOTAL"] = self.api.yield_total / 1000
            self.data["consumptionAC"] = self.api.consumption_ac
            self.data["consumptionDAY"] = self.api.consumption_day / 1000
            self.data["consumptionYESTERDAY"] = self.api.consumption_yesterday / 1000
            self.data["consumptionMONTH"] = self.api.consumption_month / 1000
            self.data["consumptionYEAR"] = self.api.consumption_year / 1000
            self.data["consumptionTOTAL"] = self.api.consumption_total / 1000
            self.data["totalPOWER"] = self.api.total_power
            self.data["alternatorLOSS"] = self.api.alternator_loss
            self.data["CAPACITY"] = round(self.api.capacity * 100, 0)
            self.data["EFFICIENCY"] = round(self.api.efficiency * 100, 0)
            self.data["powerAVAILABLE"] = self.api.power_available
            self.data["USAGE"] = round(self.api.usage * 100, 0)
            _LOGGER.debug("Updated Solarlog overview data: %s", self.data)
        except AttributeError:
            _LOGGER.error("Missing details data in Solarlog response")


class SolarlogSensor(SensorEntity):
    """Representation of a Sensor."""

    def __init__(
        self,
        entry_id: str,
        device_name: str,
        data: SolarlogData,
        description: SolarLogSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        self.entity_description = description
        self.data = data
        self._attr_name = f"{device_name} {description.name}"
        self._attr_unique_id = f"{entry_id}_{description.key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry_id)},
            "name": device_name,
            "manufacturer": "Solar-Log",
        }

    def update(self):
        """Get the latest data from the sensor and update the state."""
        self.data.update()
        self._attr_native_value = self.data.data[self.entity_description.json_key]
