"""Platform for cover integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.cover import (
    STATE_CLOSED,
    STATE_CLOSING,
    STATE_OPEN,
    STATE_OPENING,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo

# Import the device class from the component that you want to support
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONTROLLER, DOMAIN
from .controller import ZimiController


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Zimi Cover platform."""

    debug = config_entry.data.get("debug", False)

    controller: ZimiController = hass.data[CONTROLLER]

    entities = []

    # for key, device in controller.api.devices.items().:
    for device in controller.controller.doors:
        entities.append(ZimiCover(device, debug=debug))  # noqa: PERF401

    async_add_entities(entities)


class ZimiCover(CoverEntity):
    """Representation of a Zimi cover."""

    def __init__(self, cover, debug=False) -> None:
        """Initialize an Zimicover."""

        self.logger = logging.getLogger(__name__)
        if debug:
            self.logger.setLevel(logging.DEBUG)

        self._attr_unique_id = cover.identifier
        self._attr_should_poll = False
        self._attr_device_class = CoverDeviceClass.GARAGE
        self._attr_supported_features = CoverEntityFeature.SET_TILT_POSITION

        self._cover = cover
        self._cover.subscribe(self)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, cover.identifier)},
            name=self._cover.name,
            suggested_area=self._cover.room,
        )
        self._state = STATE_CLOSED
        self._position = None
        self.update()
        self.logger.debug("__init__(%s) in %s", self.name, self._cover.room)

    def __del__(self):
        """Cleanup ZimiCover with removal of notification."""
        self._cover.unsubscribe(self)

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover/door."""
        self.logger.debug("close_cover() for %s", self.name)
        await self._cover.close_door()

        self.schedule_update_ha_state()

    @property
    def available(self) -> bool:
        """Return True if Home Assistant is able to read the state and control the underlying device."""
        return self._cover.is_connected

    @property
    def current_cover_position(self) -> int | None:
        """Return the current cover/door position."""
        return self._position

    @property
    def is_closed(self) -> bool | None:
        """Return true if cover is closed."""
        return self._state == STATE_CLOSED

    @property
    def is_closing(self) -> bool | None:
        """Return true if cover is closing."""
        return self._state == STATE_CLOSING

    @property
    def is_opening(self) -> bool | None:
        """Return true if cover is opening."""
        return self._state == STATE_OPENING

    @property
    def is_open(self) -> bool | None:
        """Return true if cover is open."""
        return self._state == STATE_OPEN

    @property
    def name(self) -> str:
        """Return the display name of this cover."""
        return self._name.strip()

    def notify(self, _observable):
        """Receive notification from cover device that state has changed."""

        self.logger.debug("notification() for %s received", self.name)
        self.schedule_update_ha_state(force_refresh=True)

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover/door."""
        self.logger.debug("open_cover() for %s", self.name)
        await self._cover.open_door()

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Open the cover/door to a specified percentage."""
        position = kwargs.get("position", None)
        if position:
            self.logger.debug("set_cover_position(%d) for %s", position, self.name)
            await self._cover.open_to_percentage(position)

    def update(self) -> None:
        """Fetch new state data for this cover."""

        self._name = self._cover.name
        self._position = self._cover.percentage
        if self._cover.is_closed:
            self._state = STATE_CLOSED
        elif self._cover.is_open:
            self._state = STATE_OPEN
        elif self._cover.is_opening:
            self._state = STATE_OPENING
        else:
            self._state = STATE_CLOSING
