"""Support for AI-Speaker sensors."""
from datetime import timedelta
import logging

from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.entity import Entity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(minutes=60)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Perform the setup for AI-Speaker status sensor."""
    async_add_entities([AisSensor(hass, config_entry.data)], True)


async def async_unload_entry(hass, entry):
    """Clean up when integrations are removed - add code if you need to do more."""
    pass


class AisSensor(Entity):
    """AiSpeakerSensor representation."""

    def __init__(self, hass, config_entry_data):
        """Sensor initialization."""
        self._ais_id = config_entry_data.get("ais_id")
        self._ais_ws_url = config_entry_data["ais_url"]
        self._ais_info = config_entry_data.get("ais_info")
        self._web_session = aiohttp_client.async_get_clientsession(hass)

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

    async def async_ask_ais_status(self):
        """Update the sensor attributes task."""

        try:
            ws_resp = await self._web_session.get(self._ais_ws_url, timeout=5)
            json_info = await ws_resp.json()
            return json_info
        except Exception as e:
            _LOGGER.error("Ask AI-Speaker status, error: " + str(e))

    async def async_update(self):
        """Update the sensor."""
        self._ais_info = await self.async_ask_ais_status()
