"""Support for ESPHome switches."""
import logging
from typing import TYPE_CHECKING, Optional

from homeassistant.components.switch import SwitchDevice
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import HomeAssistantType

from . import EsphomeEntity, platform_async_setup_entry, esphome_state_property

if TYPE_CHECKING:
    # pylint: disable=unused-import
    from aioesphomeapi import SwitchInfo, SwitchState  # noqa

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistantType,
                            entry: ConfigEntry, async_add_entities) -> None:
    """Set up ESPHome switches based on a config entry."""
    # pylint: disable=redefined-outer-name
    from aioesphomeapi import SwitchInfo, SwitchState  # noqa

    await platform_async_setup_entry(
        hass, entry, async_add_entities,
        component_key='switch',
        info_type=SwitchInfo, entity_type=EsphomeSwitch,
        state_type=SwitchState
    )


class EsphomeSwitch(EsphomeEntity, SwitchDevice):
    """A switch implementation for ESPHome."""

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
    def assumed_state(self) -> bool:
        """Return true if we do optimistic updates."""
        return self._static_info.assumed_state

    @esphome_state_property
    def is_on(self) -> Optional[bool]:
        """Return true if the switch is on."""
        return self._state.state

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the entity on."""
        await self._client.switch_command(self._static_info.key, True)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the entity off."""
        await self._client.switch_command(self._static_info.key, False)
