"""Support for AI-Speaker sensors."""
from datetime import timedelta
import logging

from homeassistant.const import DATA_RATE_KILOBITS_PER_SECOND
from homeassistant.helpers.entity import Entity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(minutes=60)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Perform the setup for AI-Speaker status sensor."""
    _LOGGER.debug("AI-Speaker sensor, async_setup_entry")
    ais_gate_instance = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities([AisSensor(ais_gate_instance)], True)


class AisSensor(Entity):
    """AiSpeakerSensor representation."""

    def __init__(self, ais_gate_instance):
        """Sensor initialization."""
        self._ais_gate = ais_gate_instance
        self._ais_id = None
        self._ais_product = None
        self._ais_manufacturer = None
        self._ais_model = None
        self._ais_os_version = None
        self._ais_api_level = None
        self._ais_ip_address = None
        self._ais_hostname = None
        self._ais_gate_network_speed = None

    @property
    def device_info(self):
        """Device info."""
        return {
            "identifiers": {(DOMAIN, self._ais_id)},
            "name": f"AI-Speaker {self._ais_product}",
            "manufacturer": self._ais_manufacturer,
            "model": self._ais_model,
            "sw_version": self._ais_os_version,
            "via_device": None,
        }

    @property
    def unique_id(self) -> str:
        """Return a unique, friendly identifier for this entity."""
        return self._ais_id

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"AI-Speaker {self._ais_product} status"

    @property
    def state(self):
        """Return the status of the sensor."""
        return self._ais_gate_network_speed

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement of this entity."""
        return DATA_RATE_KILOBITS_PER_SECOND

    @property
    def device_state_attributes(self):
        """Return the attributes of the device."""
        return {
            "ais_id": self._ais_id,
            "ais_api_level": self._ais_api_level,
            "ais_ip_address": self._ais_ip_address,
            "ais_hostname": self._ais_hostname,
        }

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return "mdi:speaker"

    async def async_update(self):
        """Update the sensor."""
        ais_info = await self._ais_gate.get_gate_info()
        self._ais_id = ais_info["ais_id"]
        self._ais_product = ais_info["Product"]
        self._ais_manufacturer = ais_info["Manufacturer"]
        self._ais_model = ais_info["Model"]
        self._ais_os_version = ais_info["OsVersion"]
        self._ais_api_level = ais_info["ApiLevel"]
        self._ais_ip_address = ais_info["IPAddressIPv4"]
        self._ais_hostname = ais_info["Hostname"]
        self._ais_hostname = ais_info["Hostname"]
        self._ais_gate_network_speed = ais_info["NetworkSpeed"]
