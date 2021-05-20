"""Support for Supla switch."""
import logging
from pprint import pformat

from homeassistant.components.supla import (
    DOMAIN,
    SUPLA_COORDINATORS,
    SUPLA_SERVERS,
    SuplaChannel,
)
from homeassistant.components.switch import SwitchEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Supla switches."""
    if discovery_info is None:
        return

    _LOGGER.debug("Discovery: %s", pformat(discovery_info))

    entities = []
    for device in discovery_info:
        server_name = device["server_name"]

        entities.append(
            SuplaSwitch(
                device,
                hass.data[DOMAIN][SUPLA_SERVERS][server_name],
                hass.data[DOMAIN][SUPLA_COORDINATORS][server_name],
            )
        )

    async_add_entities(entities)


class SuplaSwitch(SuplaChannel, SwitchEntity):
    """Representation of a Supla Switch."""

    async def async_turn_on(self, **kwargs):
        """Turn on the switch."""
        await self.async_action("TURN_ON")

    async def async_turn_off(self, **kwargs):
        """Turn off the switch."""
        await self.async_action("TURN_OFF")

    @property
    def is_on(self):
        """Return true if switch is on."""
        state = self.channel_data.get("state")
        if state:
            return state["on"]
        return False
