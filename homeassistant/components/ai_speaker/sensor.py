"""Support for AI-Speaker sensors."""
from datetime import timedelta
import logging

from aisapi.ws import AisWebService

from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.entity import Entity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(minutes=60)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Perform the setup for AI-Speaker status sensor."""
    _LOGGER.debug("AI-Speaker sensor, async_setup_entry")
    async_add_entities([AisSensor(hass, config_entry.data)], True)


async def async_unload_entry(hass, entry):
    """Clean up when integrations are removed - add code if you need to do more."""
    _LOGGER.debug("AI-Speaker sensor, async_unload_entry")


class AisSensor(Entity):
    """AiSpeakerSensor representation."""

    def __init__(self, hass, config_entry_data):
        """Sensor initialization."""
        self._ais_info = config_entry_data.get("ais_info")
        self._ais_id = self._ais_info.get("ais_id")
        self._ais_url = self._ais_info.get("ais_url")
        self._web_session = aiohttp_client.async_get_clientsession(hass)
        self._ais_gate = AisWebService(hass.loop, self._web_session, self._ais_url)

    @property
    def device_info(self):
        """Device info."""
        return {
            "identifiers": {(DOMAIN, self._ais_id)},
            "name": "AI-Speaker " + self._ais_info["Product"],
            "manufacturer": self._ais_info["Manufacturer"],
            "model": self._ais_info["Model"],
            "sw_version": self._ais_info["OsVersion"],
            "via_device": None,
        }

    @property
    def unique_id(self) -> str:
        """Return a unique, friendly identifier for this entity."""
        return self._ais_id

    @property
    def name(self):
        """Return the name of the sensor."""
        return "AI-Speaker " + self._ais_info["Product"] + " status"

    @property
    def state(self):
        """Return the status of the sensor."""
        return self._ais_info["ApiLevel"]

    @property
    def state_attributes(self):
        """Return the attributes of the sensor."""
        return self._ais_info

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return "mdi:speaker"

    async def async_update(self):
        """Update the sensor."""
        self._ais_info = await self._ais_gate.get_gate_info()
