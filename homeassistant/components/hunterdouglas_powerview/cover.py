"""Support for hunter douglas shades."""
from __future__ import annotations

import asyncio
from contextlib import suppress
from datetime import datetime, timedelta
import logging

from aiopvapi.helpers.constants import (
    ATTR_POSITION1,
    ATTR_POSITION2,
    ATTR_POSITION_DATA,
)
from aiopvapi.resources.shade import (
    ATTR_POSKIND1,
    ATTR_POSKIND2,
    MAX_POSITION,
    MIN_POSITION,
    ShadeTdbu,
    factory as PvShade,
)
import async_timeout

from homeassistant.components.cover import (
    ATTR_POSITION,
    SUPPORT_CLOSE,
    SUPPORT_OPEN,
    SUPPORT_SET_POSITION,
    SUPPORT_STOP,
    CoverDeviceClass,
    CoverEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_call_later

from .const import (
    COORDINATOR,
    DEVICE_INFO,
    DEVICE_MODEL,
    DOMAIN,
    LEGACY_DEVICE_MODEL,
    PV_API,
    PV_ROOM_DATA,
    PV_SHADE_DATA,
    ROOM_ID_IN_SHADE,
    ROOM_NAME_UNICODE,
    SHADE_RESPONSE,
    STATE_ATTRIBUTE_ROOM_NAME,
)
from .entity import ShadeEntity

_LOGGER = logging.getLogger(__name__)

# Estimated time it takes to complete a transition
# from one state to another
TRANSITION_COMPLETE_DURATION = 30

PARALLEL_UPDATES = 1

# this equates to 0.75/100 in terms of blind position
# found blinds that were closed reporting less that 655.35 (1%) even though clearly closed
# so we find 1 percent of the maximum position, add that to the minimum to calculate 1%
# then we find 75% of that number (currently 491.51) to use as the bottom of the blind
# this has more effect on top/down shades, but also works fine with normal shades
SHADE_CLOSED_POSITION = ((MIN_POSITION + (MAX_POSITION / 100)) / 100) * 75

# minutes between forced refresh of data - only used when a shade is moved
FORCED_REFRESH_TIMEFRAME = 5


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the hunter douglas shades."""

    pv_data = hass.data[DOMAIN][entry.entry_id]
    room_data = pv_data[PV_ROOM_DATA]
    shade_data = pv_data[PV_SHADE_DATA]
    pv_request = pv_data[PV_API]
    coordinator = pv_data[COORDINATOR]
    device_info = pv_data[DEVICE_INFO]

    entities = []
    for raw_shade in shade_data.values():
        # The shade may be out of sync with the hub so we force a refresh
        # when we add it if possible
        shade = PvShade(raw_shade, pv_request)
        name_before_refresh = shade.name
        with suppress(asyncio.TimeoutError):
            async with async_timeout.timeout(1):
                await shade.refresh()

        if ATTR_POSITION_DATA not in shade.raw_data:
            _LOGGER.info(
                "The %s shade was skipped because it is missing position data",
                name_before_refresh,
            )
            continue
        room_id = shade.raw_data.get(ROOM_ID_IN_SHADE)
        room_name = room_data.get(room_id, {}).get(ROOM_NAME_UNICODE, "")
        entities.extend(
            create_powerview_shade_entity(
                coordinator, device_info, room_name, shade, name_before_refresh
            )
        )
        async_add_entities(entities)


def create_powerview_shade_entity(
    coordinator, device_info, room_name, shade, name_before_refresh
):
    """Create a PowerViewShade entity."""

    if isinstance(shade, ShadeTdbu):
        return (
            PowerViewTDBUShadeTop(
                coordinator, device_info, room_name, shade, name_before_refresh
            ),
            PowerViewTDBUShadeBottom(
                coordinator, device_info, room_name, shade, name_before_refresh
            ),
        )

    return PowerViewShade(
        coordinator, device_info, room_name, shade, name_before_refresh
    )


def hd_position_to_hass(hd_position):
    """Convert hunter douglas position to hass position."""
    return round((hd_position / MAX_POSITION) * 100)


def hass_position_to_hd(hass_position):
    """Convert hass position to hunter douglas position."""
    return int(hass_position / 100 * MAX_POSITION)


class PowerViewShade(ShadeEntity, CoverEntity):
    """Representation of a powerview shade."""

    _attr_device_class = CoverDeviceClass.SHADE

    def __init__(self, coordinator, device_info, room_name, shade, name):
        """Initialize the shade."""
        super().__init__(coordinator, device_info, room_name, shade, name)
        self._shade = shade
        self._is_opening = False
        self._is_closing = False
        self._scheduled_transition_update = None
        self._current_cover_position_bottom = MIN_POSITION
        self._current_cover_position_top = MIN_POSITION

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {STATE_ATTRIBUTE_ROOM_NAME: self._room_name}

    @property
    def supported_features(self):
        """Flag supported features."""
        supported_features = SUPPORT_OPEN | SUPPORT_CLOSE | SUPPORT_SET_POSITION
        if self._device_info[DEVICE_MODEL] != LEGACY_DEVICE_MODEL:
            supported_features |= SUPPORT_STOP
        return supported_features

    @property
    def is_closed(self):
        """Return if the cover is closed."""
        # treat anything below 75% of 1% of total position as closed due to conversion of powerview to hass
        cover_position = self._current_cover_position_bottom
        return cover_position <= SHADE_CLOSED_POSITION

    @property
    def is_opening(self):
        """Return if the cover is opening."""
        return self._is_opening

    @property
    def is_closing(self):
        """Return if the cover is closing."""
        return self._is_closing

    @property
    def current_cover_position(self):
        """Return the current position of cover."""
        return hd_position_to_hass(self._current_cover_position_bottom)

    @property
    def name(self):
        """Return the name of the shade."""
        return self._shade_name

    async def async_close_cover(self, **kwargs):
        """Close the cover."""
        await self._async_move(0)

    async def async_open_cover(self, **kwargs):
        """Open the cover."""
        await self._async_move(100)

    async def async_stop_cover(self, **kwargs):
        """Stop the cover."""
        # Cancel any previous updates
        self._async_cancel_scheduled_transition_update()
        self._async_update_from_command(await self._shade.stop())
        await self._async_force_refresh_state()

    async def async_set_cover_position(self, **kwargs):
        """Move the shade to a specific position."""
        if ATTR_POSITION not in kwargs:
            return
        await self._async_move(kwargs[ATTR_POSITION])

    async def _async_move(self, target_hass_position):
        """Move the shade to a position."""

        current_hass_position = self.current_cover_position
        steps_to_move = abs(current_hass_position - target_hass_position)

        self._async_schedule_update_for_transition(steps_to_move)

        self._async_update_from_command(
            await self._shade.move(
                {
                    ATTR_POSITION1: hass_position_to_hd(target_hass_position),
                    ATTR_POSKIND1: 1,
                }
            )
        )

        self._is_opening = False
        self._is_closing = False
        if target_hass_position > current_hass_position:
            self._is_opening = True
        elif target_hass_position < current_hass_position:
            self._is_closing = True
        self.async_write_ha_state()

    @callback
    def _async_update_from_command(self, raw_data):
        """Update the shade state after a command."""
        if not raw_data or SHADE_RESPONSE not in raw_data:
            return
        self._async_process_new_shade_data(raw_data[SHADE_RESPONSE])

    @callback
    def _async_process_new_shade_data(self, data):
        """Process new data from an update."""
        self._shade.raw_data = data
        self._async_update_current_cover_position()

    @callback
    def _async_update_current_cover_position(self):
        """Update the current cover position from the data."""
        _LOGGER.debug("Raw data update: %s", self._shade.raw_data)
        position_data = self._shade.raw_data.get(ATTR_POSITION_DATA, {})
        if ATTR_POSITION1 in position_data:
            if position_data[ATTR_POSKIND1] == 1:
                self._current_cover_position_bottom = int(position_data[ATTR_POSITION1])
            if position_data[ATTR_POSKIND1] == 2:
                self._current_cover_position_top = int(position_data[ATTR_POSITION1])
            # if position_data[ATTR_POSKIND1] == 3:
            #    self._current_cover_tilt_position = int(position_data[ATTR_POSITION1])
        if ATTR_POSITION2 in position_data:
            if position_data[ATTR_POSKIND2] == 1:
                self._current_cover_position_bottom = int(position_data[ATTR_POSITION2])
            if position_data[ATTR_POSKIND2] == 2:
                self._current_cover_position_top = int(position_data[ATTR_POSITION2])
            # if position_data[ATTR_POSKIND2] == 3:
            #    self._current_cover_tilt_position = int(position_data[ATTR_POSITION2])
        self._is_opening = False
        self._is_closing = False

    @callback
    def _async_cancel_scheduled_transition_update(self):
        """Cancel any previous updates."""
        if not self._scheduled_transition_update:
            return
        self._scheduled_transition_update()
        self._scheduled_transition_update = None

    @callback
    def _async_schedule_update_for_transition(self, steps):
        self.async_write_ha_state()

        # Cancel any previous updates
        self._async_cancel_scheduled_transition_update()

        est_time_to_complete_transition = 1 + int(
            TRANSITION_COMPLETE_DURATION * (steps / 100)
        )

        _LOGGER.debug(
            "Estimated time to complete transition of %s steps for %s: %s",
            steps,
            self.name,
            est_time_to_complete_transition,
        )

        # Schedule an update for when we expect the transition
        # to be completed.
        self._scheduled_transition_update = async_call_later(
            self.hass,
            est_time_to_complete_transition,
            self._async_complete_schedule_update,
        )

    async def _async_complete_schedule_update(self, _):
        """Update status of the cover."""
        _LOGGER.debug("Processing scheduled update for %s", self.name)
        self._scheduled_transition_update = None
        await self._async_force_refresh_state()

    async def _async_force_refresh_state(self):
        """Refresh the cover state and force the device cache to be bypassed."""
        await self._shade.refresh()
        self._async_update_current_cover_position()
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        self._async_update_current_cover_position()
        self.async_on_remove(
            self.coordinator.async_add_listener(self._async_update_shade_from_group)
        )

    @callback
    def _async_update_shade_from_group(self):
        """Update with new data from the coordinator."""
        if self._scheduled_transition_update or self.coordinator.data is None:
            # If a transition is in progress the data will be wrong
            # or empty data as result of 204/423 return
            return
        self._async_process_new_shade_data(self.coordinator.data[self._shade.id])
        self.async_write_ha_state()


class PowerViewTDBUShade(PowerViewShade):
    """Representation of a top down bottom up powerview shade."""

    def __init__(self, coordinator, device_info, room_name, shade, name):
        """Initialize the shade."""
        super().__init__(coordinator, device_info, room_name, shade, name)
        self._current_cover_position_bottom = MIN_POSITION
        self._current_cover_position_top = MIN_POSITION
        self._last_forced_refresh = None

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {
            STATE_ATTRIBUTE_ROOM_NAME: self._room_name,
            "topMotor": hd_position_to_hass(self._current_cover_position_top),
            "bottomMotor": hd_position_to_hass(self._current_cover_position_bottom),
            "topMotorHD": self._current_cover_position_top,
            "bottomMotorHD": self._current_cover_position_bottom,
        }

    async def _async_force_refresh_state(self):
        """Refresh the cover state and force the device cache to be bypassed."""
        # TO DO: DELETE
        await self._shade.refresh()
        self._async_update_current_cover_position()
        self._last_forced_refresh = datetime.now(tz=None)
        self.async_write_ha_state()


class PowerViewTDBUShadeBottom(PowerViewTDBUShade):
    """Representation of a top down bottom up powerview shade."""

    def __init__(self, coordinator, device_info, room_name, shade, name):
        """Initialize the shade."""
        super().__init__(coordinator, device_info, room_name, shade, name)
        self._unique_id = f"{self._shade.id}-bottom"

    @property
    def name(self):
        """Return the name of the shade."""
        name = f"{self._shade_name} Bottom"
        return name

    @property
    def is_closed(self):
        """Return if the cover is closed."""
        # treat anything below 75% of 1% of total position as closed due to conversion of powerview to hass
        cover_position = self._current_cover_position_bottom
        return cover_position <= SHADE_CLOSED_POSITION

    @property
    def current_cover_position(self):
        """Return the current position of cover."""
        return hd_position_to_hass(self._current_cover_position_bottom)

    async def _async_move(self, target_hass_position):
        """Move the shade to a position."""

        # we will limit force update to 5 minutes to prevent spamming hub
        time_delta = datetime.now(tz=None) - timedelta(minutes=FORCED_REFRESH_TIMEFRAME)
        force_refresh = False
        if self._last_forced_refresh is not None:
            force_refresh = self._last_forced_refresh < time_delta

        # force a refresh to ensure we dont push a blind past the limit of its counter part
        # this does result in a slightly slower response from tdbu but protects the motor
        if force_refresh is True:
            _LOGGER.debug("Cover %s - Force refresh on move", self.name)
            await self._async_force_refresh_state()

        # get position of top and bottom rails independently
        # cover_bottom = hd_position_to_hass(self._current_cover_position_bottom)
        cover_top = 100 - hd_position_to_hass(self._current_cover_position_top)

        # dont allow a cover to go past the position of the opposite motor
        if target_hass_position > cover_top:
            target_hass_position = cover_top - 1

        current_hass_position = self.current_cover_position
        steps_to_move = abs(current_hass_position - target_hass_position)

        # if not steps_to_move:
        #    return

        self._async_schedule_update_for_transition(steps_to_move)

        position_bottom = hass_position_to_hd(target_hass_position)
        postion_top = self._current_cover_position_top

        self._async_update_from_command(
            await self._shade.move(
                {
                    ATTR_POSITION1: position_bottom,
                    ATTR_POSITION2: postion_top,
                    ATTR_POSKIND1: 1,
                    ATTR_POSKIND2: 2,
                }
            )
        )

        self._is_opening = False
        self._is_closing = False
        if target_hass_position > current_hass_position:
            self._is_opening = True
        elif target_hass_position < current_hass_position:
            self._is_closing = True
        self.async_write_ha_state()


class PowerViewTDBUShadeTop(PowerViewTDBUShade):
    """Representation of a top down bottom up powerview shade."""

    def __init__(self, coordinator, device_info, room_name, shade, name):
        """Initialize the shade."""
        super().__init__(coordinator, device_info, room_name, shade, name)
        self._unique_id = f"{self._shade.id}-top"

    @property
    def name(self):
        """Return the name of the shade."""
        name = f"{self._shade_name} Top"
        return name

    @property
    def is_closed(self):
        """Return if the cover is closed."""
        # treat anything below 75% of 1% of total position as closed due to conversion of powerview to hass
        cover_position = self._current_cover_position_top
        return cover_position <= SHADE_CLOSED_POSITION

    @property
    def current_cover_position(self):
        """Return the current position of cover."""
        return hd_position_to_hass(self._current_cover_position_top)

    async def _async_move(self, target_hass_position):
        """Move the shade to a position."""

        # we will limit force update to 5 minutes to prevent spamming hub
        time_delta = datetime.now(tz=None) - timedelta(minutes=FORCED_REFRESH_TIMEFRAME)
        force_refresh = False
        if self._last_forced_refresh is not None:
            force_refresh = self._last_forced_refresh < time_delta

        # force a refresh to ensure we dont push a blind past the limit of its counter part
        # this does result in a slightly slower response from tdbu but protects the motor
        if force_refresh is True:
            _LOGGER.debug("Cover %s - Force refresh on move", self.name)
            await self._async_force_refresh_state()

        # get position of top and bottom rails independently
        cover_bottom = hd_position_to_hass(self._current_cover_position_bottom)
        # cover_top = 100 - hd_position_to_hass(self._current_cover_position_top)

        # dont allow a cover to go past the position of the opposite motor
        if (100 - target_hass_position) < cover_bottom:
            target_hass_position = (100 - cover_bottom) - 1

        current_hass_position = self.current_cover_position
        steps_to_move = abs(current_hass_position - target_hass_position)

        # if not steps_to_move:
        #    return

        self._async_schedule_update_for_transition(steps_to_move)

        position_bottom = self._current_cover_position_bottom
        postion_top = hass_position_to_hd(target_hass_position)

        self._async_update_from_command(
            await self._shade.move(
                {
                    ATTR_POSITION1: position_bottom,
                    ATTR_POSITION2: postion_top,
                    ATTR_POSKIND1: 1,
                    ATTR_POSKIND2: 2,
                }
            )
        )

        self._is_opening = False
        self._is_closing = False
        if target_hass_position > current_hass_position:
            self._is_opening = True
        elif target_hass_position < current_hass_position:
            self._is_closing = True
        self.async_write_ha_state()
