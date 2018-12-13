"""Support for esphomelib switches."""
import logging

from homeassistant.components.esphomelib import EsphomelibEntity, \
    platform_async_setup_entry
from homeassistant.components.switch import SwitchDevice

DEPENDENCIES = ['esphomelib']
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up esphomelib switches based on a config entry."""
    from aioesphomeapi.client import SwitchInfo, SwitchState

    await platform_async_setup_entry(
        hass, entry, async_add_entities,
        component_key='switch',
        info_type=SwitchInfo, entity_type=EsphomelibSwitch,
        state_type=SwitchState
    )


class EsphomelibSwitch(EsphomelibEntity, SwitchDevice):
    """A switch implementation for esphomelib."""

    @property
    def icon(self) -> str:
        """Return the icon."""
        return self.info.icon

    @property
    def is_on(self):
        """Return true if the switch is on."""
        if self._state is None:
            return None
        return self._state.state

    async def async_turn_on(self, **kwargs):
        """Turn the entity on."""
        await self._client.switch_command(self.info.key, True)

    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        await self._client.switch_command(self.info.key, False)
