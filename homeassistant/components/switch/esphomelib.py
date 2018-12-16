"""Support for esphomelib switches."""
import logging

from typing import TYPE_CHECKING, Optional

from homeassistant.components.esphomelib import EsphomelibEntity, \
    platform_async_setup_entry
from homeassistant.components.switch import SwitchDevice
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import HomeAssistantType

if TYPE_CHECKING:
    # pylint: disable=unused-import
    from aioesphomeapi.client import SwitchInfo, SwitchState

DEPENDENCIES = ['esphomelib']
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistantType,
                            entry: ConfigEntry, async_add_entities) -> None:
    """Set up esphomelib switches based on a config entry."""
    # pylint: disable=redefined-outer-name
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
    def _static_info(self) -> 'SwitchInfo':
        return super()._static_info

    @property
    def _state(self) -> Optional['SwitchState']:
        return super()._state

    @property
    def icon(self) -> str:
        """Return the icon."""
        return self._static_info.icon

    @property
    def is_on(self):
        """Return true if the switch is on."""
        if self._state is None:
            return None
        return self._state.state

    async def async_turn_on(self, **kwargs):
        """Turn the entity on."""
        await self._client.switch_command(self._static_info.key, True)

    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        await self._client.switch_command(self._static_info.key, False)
