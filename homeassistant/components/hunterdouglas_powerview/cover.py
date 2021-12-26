"""Support for hunter douglas shades."""
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
from homeassistant.core import callback
from homeassistant.helpers.event import async_call_later

from .const import (
    CONF_CREATE_TOPDOWN_ENTITIES,
    COORDINATOR,
    DEFAULT_CREATE_TOPDOWN_ENTITIES,
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
    TOPDOWN_SHADES,
)
from .entity import ShadeEntity

_LOGGER = logging.getLogger(__name__)

# Estimated time it takes to complete a transition
# from one state to another
TRANSITION_COMPLETE_DURATION = 30

PARALLEL_UPDATES = 1


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the hunter douglas shades."""

    pv_data = hass.data[DOMAIN][entry.entry_id]
    room_data = pv_data[PV_ROOM_DATA]
    shade_data = pv_data[PV_SHADE_DATA]
    pv_request = pv_data[PV_API]
    coordinator = pv_data[COORDINATOR]
    device_info = pv_data[DEVICE_INFO]

    create_topdown = entry.options.get(
        CONF_CREATE_TOPDOWN_ENTITIES, DEFAULT_CREATE_TOPDOWN_ENTITIES
    )

    if create_topdown is False:
        _LOGGER.debug("Top/Down covers will have a single entity based on config")

    entities = []
    for raw_shade in shade_data.values():
        # The shade may be out of sync with the hub
        # so we force a refresh when we add it if
        # possible
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

        if create_topdown is True and shade.shade_type.shade_type in TOPDOWN_SHADES:
            entities.append(
                PowerViewShade(
                    coordinator,
                    device_info,
                    room_name,
                    shade,
                    name_before_refresh,
                    "Top",
                )
            )
            entities.append(
                PowerViewShade(
                    coordinator,
                    device_info,
                    room_name,
                    shade,
                    name_before_refresh,
                    "Bottom",
                )
            )
        else:
            entities.append(
                PowerViewShade(
                    coordinator,
                    device_info,
                    room_name,
                    shade,
                    name_before_refresh,
                    "Standard",
                )
            )
    async_add_entities(entities)


def hd_position_to_hass(hd_position):
    """Convert hunter douglas position to hass position."""
    return round((hd_position / MAX_POSITION) * 100)


def hass_position_to_hd(hass_position):
    """Convert hass position to hunter douglas position."""
    return int(hass_position / 100 * MAX_POSITION)


class PowerViewShade(ShadeEntity, CoverEntity):
    """Representation of a powerview shade."""

    def __init__(self, coordinator, device_info, room_name, shade, name, motor):
        """Initialize the shade."""
        super().__init__(coordinator, device_info, room_name, shade, name)
        self._shade = shade
        self._motor = motor
        self._is_opening = False
        self._is_closing = False
        self._last_action_timestamp = 0
        self._scheduled_transition_update = None
        self._current_cover_position_bottom = MIN_POSITION
        self._current_cover_position_top = MIN_POSITION
        self._last_forced_refresh = None
        if self._motor in ["Top", "Bottom"]:
            self._unique_id = f"{self._shade.id}-{self._motor}"

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
        # found blinds that were closed reporting less that 655.35 (1%) even though clearly closed
        # so we find 1 percent of the maximum position, add that to the minimum in case of future change
        # then we find 75% of that number (491.51) to use as the bottom of the blind
        # this has more effect on top/down shades, but also works fine with normal shades
        one_percent = MIN_POSITION + (MAX_POSITION / 100)
        treat_as_bottom = (one_percent / 100) * 75
        cover_position = self._current_cover_position_bottom
        if self._motor in ["Top"]:
            cover_position = self._current_cover_position_top
        return cover_position <= treat_as_bottom

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
        position = self._current_cover_position_bottom
        if self._motor in ["Top"]:
            position = self._current_cover_position_top
        return hd_position_to_hass(position)

    @property
    def device_class(self):
        """Return device class."""
        return CoverDeviceClass.SHADE

    @property
    def name(self):
        """Return the name of the shade."""
        name = self._shade_name
        if self._motor != "Standard":
            name = f"{self._shade_name} {self._motor}"
        return name

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
        time_delta = datetime.now(tz=None) - timedelta(minutes=5)
        # we will limit force update to 5 minutes to prevent spamming hub
        force_refresh = False
        if self._last_forced_refresh is not None:
            force_refresh = self._last_forced_refresh < time_delta

        if self._motor in ["Top", "Bottom"]:
            # force a refresh to ensure we dont push a blind past the limit of its counter part
            # this does result in a slightly slower response from tdbu but protects the motor
            if force_refresh is True:
                _LOGGER.debug("Cover %s - Force refresh on move", self.name)
                await self._async_force_refresh_state()

            cover_bottom = hd_position_to_hass(self._current_cover_position_bottom)
            cover_top = 100 - hd_position_to_hass(self._current_cover_position_top)
            # dont allow a cover to go past the position of the opposite motor
            if self._motor in ["Top"] and (100 - target_hass_position) < cover_bottom:
                target_hass_position = (100 - cover_bottom) - 1
            if self._motor in ["Bottom"] and target_hass_position > cover_top:
                target_hass_position = cover_top - 1

        current_hass_position = self.current_cover_position
        steps_to_move = abs(current_hass_position - target_hass_position)

        if not steps_to_move:
            # force a refresh in case hass was out of date and a move is needed
            # dont refresh if top/down as we already refreshed above
            if self._motor not in ["Top", "Bottom"] and force_refresh is True:
                _LOGGER.debug("Cover %s - Force refresh on move", self.name)
                await self._async_force_refresh_state()
                current_hass_position = self.current_cover_position
                steps_to_move = abs(current_hass_position - target_hass_position)
            if not steps_to_move:
                return

        self._async_schedule_update_for_transition(steps_to_move)

        if self._motor == "Top":
            self._async_update_from_command(
                await self._shade.move(
                    {
                        ATTR_POSITION1: self._current_cover_position_bottom,
                        ATTR_POSITION2: hass_position_to_hd(target_hass_position),
                        ATTR_POSKIND1: 1,
                        ATTR_POSKIND2: 2,
                    }
                )
            )
        elif self._motor == "Bottom":
            self._async_update_from_command(
                await self._shade.move(
                    {
                        ATTR_POSITION1: hass_position_to_hd(target_hass_position),
                        ATTR_POSITION2: self._current_cover_position_top,
                        ATTR_POSKIND1: 1,
                        ATTR_POSKIND2: 2,
                    }
                )
            )
        else:
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
            self._current_cover_position_bottom = int(position_data[ATTR_POSITION1])
        if self._motor in ["Top", "Bottom"] and ATTR_POSITION2 in position_data:
            self._current_cover_position_top = int(position_data[ATTR_POSITION2])
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
        self._last_forced_refresh = datetime.now(tz=None)
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
        if self._scheduled_transition_update:
            # If a transition is in progress
            # the data will be wrong
            return
        self._async_process_new_shade_data(self.coordinator.data[self._shade.id])
        self.async_write_ha_state()
