"""Support for Haus-Bus cover (Rolladen)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pyhausbus.de.hausbus.homeassistant.proxy.Rollladen import Rollladen
from pyhausbus.de.hausbus.homeassistant.proxy.rollladen.data.Configuration import (
    Configuration,
)
from pyhausbus.de.hausbus.homeassistant.proxy.rollladen.data.EvClosed import EvClosed
from pyhausbus.de.hausbus.homeassistant.proxy.rollladen.data.EvOpen import EvOpen
from pyhausbus.de.hausbus.homeassistant.proxy.rollladen.data.EvStart import EvStart
from pyhausbus.de.hausbus.homeassistant.proxy.rollladen.data.Status import Status
from pyhausbus.de.hausbus.homeassistant.proxy.rollladen.params.EDirection import (
    EDirection,
)

from homeassistant.components.cover import (
    DOMAIN as COVER_DOMAIN,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .entity import HausbusEntity
from .const import NEW_CHANNEL_ADDED

if TYPE_CHECKING:
  from . import HausbusConfigEntry

import logging

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HausbusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up a cover from a config entry."""
    
    def _handle_channel_added(channel, device_info):
        if isinstance(channel, Rollladen):
            _LOGGER.debug("creating new COVER entity for %s", channel)
            hass.loop.call_soon_threadsafe(
              async_add_entities,
              [HausbusCover(channel, device_info)],
            )
            
    config_entry.async_on_unload(
        async_dispatcher_connect(hass, NEW_CHANNEL_ADDED, _handle_channel_added)
    )


class HausbusCover(HausbusEntity, CoverEntity):
    """Representation of a Haus-Bus cover."""

    def __init__(self, channel: Rollladen, device_info: DeviceInfo) -> None:
        """Set up cover."""

        super().__init__(channel, COVER_DOMAIN, device_info)

        self._attr_device_class = CoverDeviceClass.SHUTTER
        self._attr_supported_features = (
            CoverEntityFeature.OPEN
            | CoverEntityFeature.CLOSE
            | CoverEntityFeature.STOP
            | CoverEntityFeature.SET_POSITION
        )
        self._attr_reports_position = True  # Position is reported
        self._position: int | None = None
        self._is_opening: bool | None = None
        self._is_closing: bool | None = None
        self.get_hardware_status();

    @property
    def current_cover_position(self) -> int | None:
        """Actual position as percent (0 = closed, 100 = open)."""
        return self._position

    @property
    def is_closed(self) -> bool | None:
        """Returns true if cover is closed."""
        if self._position is None:
            return None
        return self._position == 0

    @property
    def is_opening(self) -> bool | None:
        """Returns true if cover is open."""
        return self._is_opening

    @property
    def is_closing(self) -> bool | None:
        """Returns true if cover is actually closing."""
        return self._is_closing

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Opens the cover."""
        _LOGGER.debug("opening cover %s", self._debug_identifier)
        self._channel.start(EDirection.TO_OPEN)

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Closes the cover."""
        _LOGGER.debug("closing cover %s", self._debug_identifier)
        self._channel.start(EDirection.TO_CLOSE)

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stops the actual cover movevent."""
        _LOGGER.debug("stop cover %s", self._debug_identifier)
        self._channel.stop()

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Moves cover to the given position."""
        position = kwargs.get("position")
        _LOGGER.debug(
            "set cover position to %s for %s", position, self._debug_identifier
        )

        if position is None:
            return

        position = min(position, 100)
        position = max(position, 0)
        self._channel.moveToPosition(100 - position)

    def handle_event(self, data: Any) -> None:
        """Handle haus-bus cover events."""

        super().handle_event(data)

        if isinstance(data, EvStart):
            direction = data.getDirection()
            if direction is EDirection.TO_OPEN:
                self._is_opening = True
                self._is_closing = False
            elif direction is EDirection.TO_CLOSE:
                self._is_opening = False
                self._is_closing = True
            else:
                _LOGGER.debug("unexpected direction %s", direction)
            self.schedule_update_ha_state()

        elif isinstance(data, EvClosed):
            self._is_opening = False
            self._is_closing = False
            self._position = 100 - data.getPosition()
            self.schedule_update_ha_state()

        elif isinstance(data, EvOpen):
            self._is_opening = False
            self._is_closing = False
            self._position = 100
            self.schedule_update_ha_state()

        elif isinstance(data, Status):
            self._position = 100 - data.getPosition()
            self.schedule_update_ha_state()

        elif isinstance(data, Configuration):
            self._configuration = data
