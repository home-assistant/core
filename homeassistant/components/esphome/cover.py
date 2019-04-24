"""Support for ESPHome covers."""
import logging
from typing import TYPE_CHECKING, Optional

from homeassistant.components.cover import (
    ATTR_POSITION, ATTR_TILT_POSITION, SUPPORT_CLOSE, SUPPORT_CLOSE_TILT,
    SUPPORT_OPEN, SUPPORT_OPEN_TILT, SUPPORT_SET_POSITION,
    SUPPORT_SET_TILT_POSITION, SUPPORT_STOP, CoverDevice)
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import HomeAssistantType

from . import EsphomeEntity, platform_async_setup_entry, esphome_state_property

if TYPE_CHECKING:
    # pylint: disable=unused-import
    from aioesphomeapi import CoverInfo, CoverState  # noqa

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


class EsphomeCover(EsphomeEntity, CoverDevice):
    """A cover implementation for ESPHome."""

    @property
    def _static_info(self) -> 'CoverInfo':
        return super()._static_info

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        flags = SUPPORT_OPEN | SUPPORT_CLOSE | SUPPORT_STOP
        if self._static_info.supports_position:
            flags |= SUPPORT_SET_POSITION
        if self._static_info.supports_tilt:
            flags |= (SUPPORT_OPEN_TILT | SUPPORT_CLOSE_TILT |
                      SUPPORT_SET_TILT_POSITION)
        return flags

    @property
    def device_class(self) -> str:
        """Return the class of this device, from component DEVICE_CLASSES."""
        return self._static_info.device_class

    @property
    def assumed_state(self) -> bool:
        """Return true if we do optimistic updates."""
        return self._static_info.assumed_state

    @property
    def _state(self) -> Optional['CoverState']:
        return super()._state

    @esphome_state_property
    def is_closed(self) -> Optional[bool]:
        """Return if the cover is closed or not."""
        # Check closed state with api version due to a protocol change
        return self._state.is_closed(self._client.api_version)

    @esphome_state_property
    def is_opening(self) -> bool:
        """Return if the cover is opening or not."""
        from aioesphomeapi import CoverOperation
        return self._state.current_operation == CoverOperation.IS_OPENING

    @esphome_state_property
    def is_closing(self) -> bool:
        """Return if the cover is closing or not."""
        from aioesphomeapi import CoverOperation
        return self._state.current_operation == CoverOperation.IS_CLOSING

    @esphome_state_property
    def current_cover_position(self) -> Optional[float]:
        """Return current position of cover. 0 is closed, 100 is open."""
        if not self._static_info.supports_position:
            return None
        return self._state.position * 100.0

    @esphome_state_property
    def current_cover_tilt_position(self) -> Optional[float]:
        """Return current position of cover tilt. 0 is closed, 100 is open."""
        if not self._static_info.supports_tilt:
            return None
        return self._state.tilt * 100.0

    async def async_open_cover(self, **kwargs) -> None:
        """Open the cover."""
        await self._client.cover_command(key=self._static_info.key,
                                         position=1.0)

    async def async_close_cover(self, **kwargs) -> None:
        """Close cover."""
        await self._client.cover_command(key=self._static_info.key,
                                         position=0.0)

    async def async_stop_cover(self, **kwargs) -> None:
        """Stop the cover."""
        await self._client.cover_command(key=self._static_info.key, stop=True)

    async def async_set_cover_position(self, **kwargs) -> None:
        """Move the cover to a specific position."""
        await self._client.cover_command(key=self._static_info.key,
                                         position=kwargs[ATTR_POSITION] / 100)

    async def async_open_cover_tilt(self, **kwargs) -> None:
        """Open the cover tilt."""
        await self._client.cover_command(key=self._static_info.key, tilt=1.0)

    async def async_close_cover_tilt(self, **kwargs) -> None:
        """Close the cover tilt."""
        await self._client.cover_command(key=self._static_info.key, tilt=0.0)

    async def async_set_cover_tilt_position(self, **kwargs) -> None:
        """Move the cover tilt to a specific position."""
        await self._client.cover_command(key=self._static_info.key,
                                         tilt=kwargs[ATTR_TILT_POSITION] / 100)
