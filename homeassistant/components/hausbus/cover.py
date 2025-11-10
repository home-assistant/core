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

from .entity import HausbusEntity

if TYPE_CHECKING:
    from . import HausbusConfigEntry

import logging

LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HausbusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up a cover from a config entry."""

    gateway = config_entry.runtime_data

    async def async_add_cover(channel: HausbusEntity) -> None:
        """Add cover entity."""
        if isinstance(channel, HausbusCover):
            async_add_entities([channel])

    gateway.register_platform_add_channel_callback(async_add_cover, COVER_DOMAIN)


class HausbusCover(HausbusEntity, CoverEntity):
    """Representation of a Haus-Bus cover."""

    def __init__(self, channel: Rollladen, device_info: DeviceInfo) -> None:
        """Set up cover."""
        super().__init__(channel, device_info)

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
        LOGGER.debug("%s: opening cover", self.name)
        self._channel.start(EDirection.TO_OPEN)

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Closes the cover."""
        LOGGER.debug("%s: closing cover", self.name)
        self._channel.start(EDirection.TO_CLOSE)

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stops the actual cover movevent."""
        LOGGER.debug("%s: stop cover", self.name)
        self._channel.stop()

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Moves cover to the given position."""
        position = kwargs.get("position")
        LOGGER.debug("%s: set cover position to %s", self.name, position)

        if position is None:
            return

        position = min(position, 100)
        position = max(position, 0)
        self._channel.moveToPosition(100 - position)

    def handle_event(self, data: Any) -> None:
        """Handle haus-bus cover events."""
        if isinstance(data, EvStart):
            direction = data.getDirection()
            if direction is EDirection.TO_OPEN:
                self._is_opening = True
                self._is_closing = False
            elif direction is EDirection.TO_CLOSE:
                self._is_opening = False
                self._is_closing = True
            else:
                LOGGER.debug("unexpected direction %s", direction)
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
