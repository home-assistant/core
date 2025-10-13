"""Adds support for generic cover units."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping
from datetime import datetime, timedelta
import logging
import math
from typing import Any

from propcache.api import cached_property

from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    ATTR_CURRENT_TILT_POSITION,
    CoverEntity,
    CoverEntityFeature,
    CoverState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_NAME,
    CONF_UNIQUE_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import (
    DOMAIN as HOMEASSISTANT_DOMAIN,
    Event,
    EventStateChangedData,
    HomeAssistant,
    callback,
)
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import (
    CONF_DURATION,
    CONF_SWITCH_CLOSE,
    CONF_SWITCH_OPEN,
    CONF_TILT_DURATION,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the generic cover platform."""
    if discovery_info:
        config = discovery_info
    await _async_setup_config(
        hass, config, config.get(CONF_UNIQUE_ID), async_add_entities
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Initialize config entry."""

    config = {**config_entry.data, **config_entry.options}

    await _async_setup_config(
        hass,
        config,
        config_entry.entry_id,
        async_add_entities,
    )


async def _async_setup_config(
    hass: HomeAssistant,
    config: Mapping[str, Any],
    unique_id: str | None,
    async_add_entities: AddEntitiesCallback | AddConfigEntryEntitiesCallback,
) -> None:
    name: str = config[CONF_NAME]
    switch_open_entity_id: str = config[CONF_SWITCH_OPEN]
    switch_close_entity_id: str = config[CONF_SWITCH_CLOSE]

    duration: timedelta = timedelta(seconds=5)
    if CONF_DURATION in config:
        duration = timedelta(**(config[CONF_DURATION]))

    tilt_duration: timedelta = timedelta(seconds=1)
    if CONF_TILT_DURATION in config:
        tilt_duration = timedelta(**(config[CONF_TILT_DURATION]))

    async_add_entities(
        [
            GenericCover(
                hass,
                name,
                switch_open_entity_id,
                switch_close_entity_id,
                duration,
                tilt_duration,
                unique_id,
            )
        ]
    )


ATTR_DURATION = "duration"
ATTR_TILT_DURATION = "tilt_duration"
ATTR_SWITCH_OPEN_ENTITY_ID = "switch_open_entity_id"
ATTR_SWITCH_CLOSE_ENTITY_ID = "switch_close_entity_id"


class GenericCover(CoverEntity, RestoreEntity):
    """Representation of a Generic Cover device."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(
        self,
        hass: HomeAssistant,
        name: str,
        switch_open_entity_id: str,
        switch_close_entity_id: str,
        duration: timedelta,
        tilt_duration: timedelta,
        unique_id: str | None,
    ) -> None:
        """Initialize the cover."""
        super().__init__()
        self._attr_name = name
        self._attr_duration = duration
        self._attr_tilt_duration = tilt_duration
        self._attr_switch_open_entity_id = switch_open_entity_id
        self._attr_switch_close_entity_id = switch_close_entity_id
        self._attr_unique_id = unique_id
        self._attr_supported_features = (
            CoverEntityFeature.OPEN
            | CoverEntityFeature.CLOSE
            | CoverEntityFeature.STOP
            | CoverEntityFeature.OPEN_TILT
            | CoverEntityFeature.CLOSE_TILT
        )
        self._cancel_update_cover_position_track_callback: Callable[[], None] | None = (
            None
        )
        self._target_cover_position: int | None = None
        self._tilt_step = math.ceil(
            100
            / math.ceil(
                min(max(self.tilt_duration, self.duration / 100), self.duration)
                / (self.duration / 100)
            )
        )
        self._switch_close_turn_off_event: asyncio.Event | None = None
        self._switch_open_turn_off_event: asyncio.Event | None = None

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Return the extra state attributes."""
        return {
            ATTR_DURATION: str(self._attr_duration),
            ATTR_TILT_DURATION: str(self._attr_tilt_duration),
            ATTR_SWITCH_OPEN_ENTITY_ID: self._attr_switch_open_entity_id,
            ATTR_SWITCH_CLOSE_ENTITY_ID: self._attr_switch_close_entity_id,
        }

    @cached_property
    def duration(self) -> timedelta:
        """Return duration to go from open to close (vice versa)."""
        return self._attr_duration

    @cached_property
    def tilt_duration(self) -> timedelta:
        """Return duration to tilt the cover."""
        return self._attr_tilt_duration

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added."""
        await super().async_added_to_hass()

        if (last_state := await self.async_get_last_state()) is not None:
            self._attr_current_cover_position = last_state.attributes.get(
                ATTR_CURRENT_POSITION, 0
            )
            self._attr_current_cover_tilt_position = last_state.attributes.get(
                ATTR_CURRENT_TILT_POSITION, 0
            )
            self._attr_is_closed = last_state.state == CoverState.CLOSED
            self._attr_is_closing = last_state.state == CoverState.CLOSING
            self._attr_is_opening = last_state.state == CoverState.OPENING
        else:
            self._attr_current_cover_position = 0
            self._attr_current_cover_tilt_position = 0
            self._attr_is_closed = True
            self._attr_is_closing = False
            self._attr_is_opening = False

        self.async_on_remove(
            async_track_state_change_event(
                self.hass,
                self._attr_switch_open_entity_id,
                self._async_switch_open_event,
            )
        )

        self.async_on_remove(
            async_track_state_change_event(
                self.hass,
                self._attr_switch_close_entity_id,
                self._async_switch_close_event,
            )
        )

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity is about to be removed."""
        await super().async_will_remove_from_hass()
        self._cancel_update_cover_position_track()

    @property
    def name(self) -> str:
        """Return the name of the cover."""
        return self._attr_name or "Generic Cover"

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        if (self.current_cover_position or 0) >= 100:
            self._cancel_update_cover_position_track()
            return
        await self._async_switch_open_turn_on(100)

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        if (self.current_cover_position or 0) <= 0:
            self._cancel_update_cover_position_track()
            return
        await self._async_switch_close_turn_on(0)

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        self._target_cover_position = None
        await self._async_switches_turn_off()

    async def async_open_cover_tilt(self, **kwargs: Any) -> None:
        """Open the cover tilt."""
        if (self.current_cover_tilt_position or 0) >= 100:
            self._cancel_update_cover_position_track()
            return
        await self._async_switch_open_turn_on(
            min(
                (self.current_cover_position or 0) + self._steps_to_tilt(100),
                100,
            )
        )

    async def async_close_cover_tilt(self, **kwargs: Any) -> None:
        """Close the cover tilt."""
        if (self.current_cover_tilt_position or 0) <= 0:
            self._cancel_update_cover_position_track()
            return
        await self._async_switch_close_turn_on(
            max(
                (self.current_cover_position or 0) - self._steps_to_tilt(100),
                0,
            )
        )

    @callback
    def _async_switch_open_event(self, event: Event[EventStateChangedData]) -> None:
        new_state = event.data["new_state"]
        if new_state is None:
            return
        if new_state.state == STATE_ON:
            if self.current_cover_position == 100:
                self._cancel_update_cover_position_track()
                self._attr_is_opening = False
                self._attr_is_closed = False
                self.async_write_ha_state()
                return
            self._attr_is_opening = True
            self._attr_is_closing = False
            self._attr_is_closed = False
            if self._target_cover_position is None:
                self._target_cover_position = 100
            elif self._target_cover_position < (self.current_cover_position or 0):
                self._cancel_update_cover_position_track()
                _LOGGER.warning("Cannot open cover while closing operation is active")
                return
            self._track_update_cover_position()
        if new_state.state == STATE_OFF:
            self._attr_is_opening = False
            self._cancel_update_cover_position_track()
            if self._switch_open_turn_off_event is not None:
                self._switch_open_turn_off_event.set()

        self.async_write_ha_state()

    @callback
    def _async_switch_close_event(self, event: Event[EventStateChangedData]) -> None:
        new_state = event.data["new_state"]
        if new_state is None:
            return
        if new_state.state == STATE_ON:
            if self.current_cover_position == 0:
                self._cancel_update_cover_position_track()
                self._attr_is_closing = False
                self._attr_is_closed = True
                self.async_write_ha_state()
                return
            self._attr_is_closing = True
            self._attr_is_opening = False
            if self._target_cover_position is None:
                self._target_cover_position = 0
            elif self._target_cover_position > (self.current_cover_position or 0):
                self._cancel_update_cover_position_track()
                _LOGGER.warning("Cannot close cover while opening operation is active")
                return
            self._track_update_cover_position()
        elif new_state.state == STATE_OFF:
            self._attr_is_closing = False
            self._cancel_update_cover_position_track()
            if self._switch_close_turn_off_event is not None:
                self._switch_close_turn_off_event.set()

        self.async_write_ha_state()

    async def _async_update_current_cover_position(
        self, time: datetime | None = None, force: bool = False
    ) -> None:
        """Update the cover position."""
        # there should be a target position
        if self._target_cover_position is None:
            self._cancel_update_cover_position_track()
            raise RuntimeError("Cover position update called without target position")

        if self.is_opening:
            self._attr_current_cover_position = min(
                (self.current_cover_position or 0) + 1, 100
            )
            self._attr_current_cover_tilt_position = min(
                (self.current_cover_tilt_position or 0) + self._tilt_step, 100
            )
        elif self.is_closing:
            self._attr_current_cover_position = max(
                (self.current_cover_position or 0) - 1, 0
            )
            self._attr_current_cover_tilt_position = max(
                (self.current_cover_tilt_position or 0) - self._tilt_step, 0
            )
        else:
            # it should either be opening or closing
            self._cancel_update_cover_position_track()
            raise RuntimeError(
                "Cover position update called when not opening or closing"
            )

        if self.current_cover_position == self._target_cover_position:
            self._cancel_update_cover_position_track()
            self._attr_is_opening = False
            self._attr_is_closing = False
            self._attr_is_closed = self.current_cover_position == 0
            await self._async_switches_turn_off()
        self.async_write_ha_state()

    def _track_update_cover_position(self) -> None:
        """Track the cover position."""
        if self._cancel_update_cover_position_track_callback is None:
            self._cancel_update_cover_position_track_callback = (
                async_track_time_interval(
                    self.hass,
                    self._async_update_current_cover_position,
                    self.duration / 100,
                )
            )

    def _cancel_update_cover_position_track(self) -> None:
        self._target_cover_position = None
        if self._cancel_update_cover_position_track_callback:
            self._cancel_update_cover_position_track_callback()
        self._cancel_update_cover_position_track_callback = None

    async def _async_switch_open_turn_on(
        self, target_cover_position: None | int = None
    ) -> None:
        """Turn on the open switch."""
        await self._async_switch_close_turn_off()
        if target_cover_position is not None:
            self._target_cover_position = target_cover_position
        await self.hass.services.async_call(
            HOMEASSISTANT_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: self._attr_switch_open_entity_id},
        )

    async def _async_switch_open_turn_off(self) -> None:
        """Turn off the open switch."""
        switch_open_state = self.hass.states.get(self._attr_switch_open_entity_id)
        if switch_open_state is None or switch_open_state.state == STATE_OFF:
            return
        self._switch_open_turn_off_event = asyncio.Event()
        await self.hass.services.async_call(
            HOMEASSISTANT_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: self._attr_switch_open_entity_id},
        )
        try:
            await asyncio.wait_for(self._switch_open_turn_off_event.wait(), timeout=1)
        except TimeoutError:
            _LOGGER.warning("Timeout waiting for open switch to turn off")
            self._switch_open_turn_off_event = None

    async def _async_switch_close_turn_on(
        self, target_cover_position: None | int = None
    ) -> None:
        """Turn on the close switch."""
        await self._async_switch_open_turn_off()
        if target_cover_position is not None:
            self._target_cover_position = target_cover_position
        await self.hass.services.async_call(
            HOMEASSISTANT_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: self._attr_switch_close_entity_id},
        )

    async def _async_switch_close_turn_off(self) -> None:
        """Turn off the close switch."""
        switch_close_state = self.hass.states.get(self._attr_switch_close_entity_id)
        if switch_close_state is None or switch_close_state.state == STATE_OFF:
            return
        self._switch_close_turn_off_event = asyncio.Event()
        await self.hass.services.async_call(
            HOMEASSISTANT_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: self._attr_switch_close_entity_id},
        )
        try:
            await asyncio.wait_for(self._switch_close_turn_off_event.wait(), timeout=1)
        except TimeoutError:
            _LOGGER.warning("Timeout waiting for close switch to turn off")
            self._switch_close_turn_off_event = None

    async def _async_switches_turn_off(self) -> None:
        """Turn off both switches."""
        await asyncio.gather(
            self._async_switch_open_turn_off(),
            self._async_switch_close_turn_off(),
        )

    def _steps_to_tilt(
        self,
        target_tilt_position: int,
    ) -> int:
        return math.ceil(
            (
                math.ceil(
                    min(max(self.tilt_duration, self.duration / 100.0), self.duration)
                    / (self.duration / 100.0)
                )
                / 100
            )
            * abs(target_tilt_position - (self.current_cover_tilt_position or 0))
        )
