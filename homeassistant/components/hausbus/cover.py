"""Support for Haus-Bus cover (Rolladen)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import voluptuous as vol
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

from homeassistant.components.cover import DOMAIN as COVER_DOMAIN
from homeassistant.components.cover import (
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .device import HausbusDevice
from .entity import HausbusEntity

if TYPE_CHECKING:
    from . import HausbusConfigEntry

import logging

LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HausbusConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a cover from a config entry."""
    gateway = config_entry.runtime_data.gateway

    # Services gelten für alle Hausbus-Entities, die die jeweilige Funktion implementieren
    platform = entity_platform.async_get_current_platform()

    platform.async_register_entity_service(
        "cover_toggle",
        {},
        "async_cover_toggle",
    )

    platform.async_register_entity_service(
        "cover_set_configuration",
        {
            vol.Required("close_time", default=30): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=255)
            ),
            vol.Required("open_time", default=30): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=255)
            ),
            vol.Optional("invert_direction", default="FALSE"): vol.All(
                vol.Coerce(bool)
            ),
        },
        "async_cover_set_configuration",
    )

    async def async_add_cover(channel: HausbusEntity) -> None:
        """Add cover entity."""
        if isinstance(channel, HausbusCover):
            async_add_entities([channel])

    gateway.register_platform_add_channel_callback(async_add_cover, COVER_DOMAIN)


class HausbusCover(HausbusEntity, CoverEntity):
    """Representation of a Haus-Bus cover."""

    def __init__(self, channel: Rollladen, device: HausbusDevice) -> None:
        """Set up cover."""
        super().__init__(channel, device)

        self._attr_device_class = CoverDeviceClass.SHUTTER
        self._attr_supported_features = (
            CoverEntityFeature.OPEN
            | CoverEntityFeature.CLOSE
            | CoverEntityFeature.STOP
            | CoverEntityFeature.SET_POSITION
        )
        self._attr_reports_position = (
            True  # Position wird berichtet :contentReference[oaicite:0]{index=0}
        )
        self._position: int | None = None
        self._is_opening: bool | None = None
        self._is_closing: bool | None = None
        self._attr_unit_of_measurement = "%"

    @property
    def current_cover_position(self) -> int | None:
        """Actual position as percent (0 = closed, 100 = open)."""
        return self._position

    @property
    def is_closed(self) -> bool | None:
        """Returns true if cover is closed"""
        if self._position is None:
            return None
        return self._position == 0

    @property
    def is_opening(self) -> bool | None:
        """Returns true if cover is open"""
        return self._is_opening

    @property
    def is_closing(self) -> bool | None:
        """Returns true if cover is actually closing"""
        return self._is_closing

    async def async_open_cover(self, **kwargs):
        """Opens the cover."""
        LOGGER.debug("async_open_cover")
        self._channel.start(EDirection.TO_OPEN)

    async def async_close_cover(self, **kwargs):
        """Closes the cover."""
        LOGGER.debug("async_close_cover")
        self._channel.start(EDirection.TO_CLOSE)

    async def async_stop_cover(self, **kwargs):
        """Stops the actual cover movevent."""
        LOGGER.debug("async_stop_cover")
        self._channel.stop()

    async def async_set_cover_position(self, **kwargs):
        """Moves cover to the given position."""
        position = kwargs.get("position")
        LOGGER.debug(f"async_set_cover_position position {position}")

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
                LOGGER.debug(f"unexpected direction {direction}")
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
            self._attr_extra_state_attributes["close_time"] = data.getCloseTime()
            self._attr_extra_state_attributes["open_time"] = data.getOpenTime()
            self._attr_extra_state_attributes["invert_direction"] = (
                data.getOptions().isInvertDirection()
            )

    async def async_cover_toggle(self):
        """Starts the cover in the opposite direction than last time"""
        LOGGER.debug("async_cover_toggle")
        self._channel.start(EDirection.TOGGLE)

    async def async_cover_set_configuration(
        self, close_time: int, open_time: int, invert_direction: bool
    ):
        """Set cover configuration."""
        LOGGER.debug(
            f"async_cover_set_configuration close_time {close_time}, open_time {open_time}, invert_direction {invert_direction}"
        )

        if not await self.ensure_configuration():
            raise HomeAssistantError(
                "Configuration could not be read. Please repeat command."
            )

        options = self._configuration.getOptions()
        options.setInvertDirection(invert_direction)
        self._channel.setConfiguration(close_time, open_time, options)
        self._channel.getConfiguration()
