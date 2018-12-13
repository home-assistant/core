"""Support for esphomelib covers."""
import logging

from homeassistant.components.cover import CoverDevice, SUPPORT_CLOSE, \
    SUPPORT_OPEN, SUPPORT_STOP
from homeassistant.components.esphomelib import EsphomelibEntity, \
    platform_async_setup_entry
from homeassistant.const import STATE_CLOSED, STATE_OPEN

DEPENDENCIES = ['esphomelib']
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up esphomelib covers based on a config entry."""
    from aioesphomeapi.client import CoverInfo, CoverState

    await platform_async_setup_entry(
        hass, entry, async_add_entities,
        component_key='cover',
        info_type=CoverInfo, entity_type=EsphomelibCover,
        state_type=CoverState
    )


COVER_STATE_STR_TO_INT = {
    STATE_OPEN: 0,
    STATE_CLOSED: 1,
}
COVER_STATE_INT_TO_STR = {v: k for k, v in COVER_STATE_STR_TO_INT.items()}


class EsphomelibCover(EsphomelibEntity, CoverDevice):
    """A cover implementation for esphomelib."""

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_OPEN | SUPPORT_CLOSE | SUPPORT_STOP

    @property
    def assumed_state(self):
        """Return true if we do optimistic updates."""
        return self.info.is_optimistic

    @property
    def is_closed(self):
        """Return if the cover is closed or not."""
        if self._state is None:
            return None
        return COVER_STATE_INT_TO_STR[self._state.state]

    async def async_open_cover(self, **kwargs):
        """Open the cover."""
        from aioesphomeapi.client import COVER_COMMAND_OPEN

        await self._client.cover_command(key=self.info.key,
                                         command=COVER_COMMAND_OPEN)

    async def async_close_cover(self, **kwargs):
        """Close cover."""
        from aioesphomeapi.client import COVER_COMMAND_CLOSE

        await self._client.cover_command(key=self.info.key,
                                         command=COVER_COMMAND_CLOSE)

    async def async_stop_cover(self, **kwargs):
        """Stop the cover."""
        from aioesphomeapi.client import COVER_COMMAND_STOP

        await self._client.cover_command(key=self.info.key,
                                         command=COVER_COMMAND_STOP)
