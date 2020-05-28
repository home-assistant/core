"""Support for getting statistical data from a Pi-hole system."""
import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import CONF_NAME

from .const import DOMAIN as PIHOLE_DOMAIN, STATUS_ENABLED

LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the pi-hole sensor."""
    pi_hole = hass.data[PIHOLE_DOMAIN][entry.data[CONF_NAME]]
    switches = [PiHoleSwitch(pi_hole, entry.entry_id)]
    async_add_entities(switches, True)


class PiHoleSwitch(SwitchEntity):
    """Switch that enables or disables a Pi-Hole."""

    def __init__(self, pi_hole, server_unique_id):
        """Initialize a Pi-hole switch."""
        LOGGER.debug("Setting up pi-hole switch for %s", server_unique_id)
        if not pi_hole.api.api_token or not pi_hole.disable_seconds:
            LOGGER.error(
                "Pi-hole %s must have an api_key and disable durration provided in "
                "configuration to be enabled",
                pi_hole.name,
            )
            raise ValueError("Cannot enable a Pi-Hole switch without an api_key")
        self.pi_hole = pi_hole
        self._name = pi_hole.name
        self._server_unique_id = server_unique_id
        self._duration = pi_hole.disable_seconds
        self._force_update = False
        self.data = {}

    @property
    def icon(self):
        """Return switch icon."""
        return "mdi:shield-star"

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unique_id(self):
        """Return the unique id of the sensor."""
        return f"{self._server_unique_id}/switch"

    @property
    def device_info(self):
        """Return the device information of the sensor."""
        return {
            "identifiers": {(PIHOLE_DOMAIN, self._server_unique_id)},
            "name": self._name,
            "manufacturer": "Pi-hole",
        }

    @property
    def is_on(self):
        """Return the state of the device."""
        return self.data["status"] == STATUS_ENABLED

    async def async_turn_on(self, **kwargs):
        """Enable the Pi-Hole."""
        await self.pi_hole.api.enable()
        self.data["status"] = STATUS_ENABLED

    async def async_turn_off(self, **kwargs):
        """Disable the Pi-Hole."""
        await self.pi_hole.api.disable(self._duration)
        self.data["status"] = "disabled"

    @property
    def device_state_attributes(self):
        """Return the state attributes of the Pi-Hole."""
        return self.data

    @property
    def available(self):
        """Could the device be accessed during the last update call."""
        return self.pi_hole.available

    async def async_update(self):
        """Get the latest data from the Pi-hole API."""
        LOGGER.debug("Getting updates for pihole switch")
        await self.pi_hole.async_update()
        self.data = self.pi_hole.api.data
