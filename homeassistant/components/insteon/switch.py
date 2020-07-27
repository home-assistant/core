"""Support for INSTEON dimmers via PowerLinc Modem."""
import logging

from homeassistant.components.switch import DOMAIN, SwitchEntity

from .insteon_entity import InsteonEntity
from .utils import async_add_insteon_entities

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the INSTEON entity class for the hass platform."""
    async_add_insteon_entities(
        hass, DOMAIN, InsteonSwitchEntity, async_add_entities, discovery_info
    )


class InsteonSwitchEntity(InsteonEntity, SwitchEntity):
    """A Class for an Insteon switch entity."""

    @property
    def is_on(self):
        """Return the boolean response if the node is on."""
        return bool(self._insteon_device_group.value)

    async def async_turn_on(self, **kwargs):
        """Turn switch on."""
        await self._insteon_device.async_on(group=self._insteon_device_group.group)

    async def async_turn_off(self, **kwargs):
        """Turn switch off."""
        await self._insteon_device.async_off(group=self._insteon_device_group.group)
