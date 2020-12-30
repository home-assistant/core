"""Support for AI-Speaker sensors."""
from datetime import timedelta
import logging

import async_timeout

from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(minutes=60)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Perform the setup for AI-Speaker sensors."""
    # AI-Speaker status sensor
    async_add_entities([AiSpeakerSensor(hass, "ais_status", config_entry.data)])


async def async_unload_entry(hass, entry):
    """Clean up when integrations are removed - here we will add code if to do more."""
    pass


class AiSpeakerSensor(Entity):
    """AiSpeakerSensor representation."""

    def __init__(self, hass, entity_id, current_state_attr):
        """Sensor initialization."""
        self.hass = hass
        self._entity_id = entity_id
        self._state = current_state_attr["ais_url"]
        self._state_attr = current_state_attr

    @property
    def entity_id(self):
        """Return the sensor ID."""
        return f"sensor.{self._entity_id}"

    @property
    def name(self):
        """Return the name of the sensor."""
        return "AI-Speaker"

    @property
    def state(self):
        """Return the status of the sensor."""
        return self._state

    @property
    def state_attributes(self):
        """Return the attributes of the sensor."""
        return self._state_attr

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return "mdi:speaker"

    async def async_ask_ais_status(self):
        """Update the sensor attributes task."""
        web_session = aiohttp_client.async_get_clientsession(self.hass)
        url = self._state
        try:
            with async_timeout.timeout(5):
                ws_resp = await web_session.get(url)
                json_info = await ws_resp.json()
                self._state = json_info
        except Exception as e:
            _LOGGER.error("Ask AI-Speaker timeout error: " + str(e))

    async def async_update(self):
        """Update the sensor."""
        self._state = await self.async_ask_ais_status()
