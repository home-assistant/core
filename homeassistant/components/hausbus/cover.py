"""Support for Haus-Bus cover (Rolladen)."""

import logging
from typing import TYPE_CHECKING, Any, override

from pyhausbus.de.hausbus.homeassistant.proxy.Rollladen import Rollladen
from pyhausbus.de.hausbus.homeassistant.proxy.rollladen.data.EvClosed import EvClosed
from pyhausbus.de.hausbus.homeassistant.proxy.rollladen.data.EvOpen import EvOpen
from pyhausbus.de.hausbus.homeassistant.proxy.rollladen.data.EvStart import EvStart
from pyhausbus.de.hausbus.homeassistant.proxy.rollladen.data.Status import Status
from pyhausbus.de.hausbus.homeassistant.proxy.rollladen.params.EDirection import (
    EDirection,
)

from homeassistant.components.cover import (
    ATTR_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import NEW_CHANNEL_ADDED
from .entity import HausbusEntity

if TYPE_CHECKING:
    from . import HausbusConfigEntry

# Cover actions are fire-and-forget UDP sends to the Haus-Bus network; the
# shared socket handles concurrent calls fine, so there is no need to limit
# parallel entity actions.
PARALLEL_UPDATES = 0

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HausbusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up a cover from a config entry."""

    @callback
    def _handle_channel_added(channel: Any, device_info: DeviceInfo) -> None:
        if isinstance(channel, Rollladen):
            _LOGGER.debug("creating new COVER entity for %s", channel)
            async_add_entities([HausbusCover(channel, device_info)])

    config_entry.async_on_unload(
        async_dispatcher_connect(hass, NEW_CHANNEL_ADDED, _handle_channel_added)
    )


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
        self._position: int | None = None

    @property
    @override
    def current_cover_position(self) -> int | None:
        """Actual position as percent (0 = closed, 100 = open)."""
        return self._position

    @property
    @override
    def is_closed(self) -> bool | None:
        """Return true if cover is closed."""
        if self._position is None:
            return None
        return self._position == 0

    @override
    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        _LOGGER.debug("opening cover %s", self._debug_identifier)
        await self.hass.async_add_executor_job(self._channel.start, EDirection.TO_OPEN)

    @override
    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        _LOGGER.debug("closing cover %s", self._debug_identifier)
        await self.hass.async_add_executor_job(self._channel.start, EDirection.TO_CLOSE)

    @override
    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover movement."""
        _LOGGER.debug("stop cover %s", self._debug_identifier)
        await self.hass.async_add_executor_job(self._channel.stop)
        self._attr_is_opening = False
        self._attr_is_closing = False
        self.async_write_ha_state()

    @override
    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move cover to the given position."""
        position = kwargs[ATTR_POSITION]
        _LOGGER.debug(
            "set cover position to %s for %s", position, self._debug_identifier
        )
        await self.hass.async_add_executor_job(
            self._channel.moveToPosition, 100 - position
        )

    @callback
    @override
    def handle_event(self, data: Any) -> None:
        """Handle haus-bus cover events."""
        super().handle_event(data)

        if isinstance(data, EvStart):
            direction = data.getDirection()
            if direction is EDirection.TO_OPEN:
                self._attr_is_opening = True
                self._attr_is_closing = False
            elif direction is EDirection.TO_CLOSE:
                self._attr_is_opening = False
                self._attr_is_closing = True
            else:
                _LOGGER.debug("unexpected direction %s", direction)
            self.async_write_ha_state()

        elif isinstance(data, EvClosed):
            self._attr_is_opening = False
            self._attr_is_closing = False
            self._position = 100 - data.getPosition()
            self.async_write_ha_state()

        elif isinstance(data, EvOpen):
            self._attr_is_opening = False
            self._attr_is_closing = False
            self._position = 100
            self.async_write_ha_state()

        elif isinstance(data, Status):
            self._position = 100 - data.getPosition()
            self.async_write_ha_state()
