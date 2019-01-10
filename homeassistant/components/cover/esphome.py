"""Support for ESPHome covers."""
import logging

from typing import TYPE_CHECKING, Optional

from homeassistant.components.cover import CoverDevice, SUPPORT_CLOSE, \
    SUPPORT_OPEN, SUPPORT_STOP
from homeassistant.components.esphome import EsphomeEntity, \
    platform_async_setup_entry
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_CLOSED, STATE_OPEN
from homeassistant.helpers.typing import HomeAssistantType

if TYPE_CHECKING:
    # pylint: disable=unused-import
    from aioesphomeapi import CoverInfo, CoverState  # noqa

DEPENDENCIES = ['esphome']
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistantType,
                            entry: ConfigEntry, async_add_entities) -> None:
    """Set up ESPHome covers based on a config entry."""
    # pylint: disable=redefined-outer-name
    from aioesphomeapi import CoverInfo, CoverState  # noqa

    await platform_async_setup_entry(
        hass, entry, async_add_entities,
        component_key='cover',
        info_type=CoverInfo, entity_type=EsphomeCover,
        state_type=CoverState
    )


COVER_STATE_INT_TO_STR = {
    0: STATE_OPEN,
    1: STATE_CLOSED
}


class EsphomeCover(EsphomeEntity, CoverDevice):
    """A cover implementation for ESPHome."""

    @property
    def _static_info(self) -> 'CoverInfo':
        return super()._static_info

    @property
    def _state(self) -> Optional['CoverState']:
        return super()._state

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return SUPPORT_OPEN | SUPPORT_CLOSE | SUPPORT_STOP

    @property
    def assumed_state(self) -> bool:
        """Return true if we do optimistic updates."""
        return self._static_info.is_optimistic

    @property
    def is_closed(self) -> Optional[bool]:
        """Return if the cover is closed or not."""
        if self._state is None:
            return None
        return COVER_STATE_INT_TO_STR[self._state.state]

    async def async_open_cover(self, **kwargs) -> None:
        """Open the cover."""
        from aioesphomeapi.client import COVER_COMMAND_OPEN

        await self._client.cover_command(key=self._static_info.key,
                                         command=COVER_COMMAND_OPEN)

    async def async_close_cover(self, **kwargs) -> None:
        """Close cover."""
        from aioesphomeapi.client import COVER_COMMAND_CLOSE

        await self._client.cover_command(key=self._static_info.key,
                                         command=COVER_COMMAND_CLOSE)

    async def async_stop_cover(self, **kwargs):
        """Stop the cover."""
        from aioesphomeapi.client import COVER_COMMAND_STOP

        await self._client.cover_command(key=self._static_info.key,
                                         command=COVER_COMMAND_STOP)
