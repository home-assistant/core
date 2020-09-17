"""Support for hunter douglas shades."""
import asyncio
import logging

from aiopvapi.helpers.constants import ATTR_POSITION1, ATTR_POSITION_DATA
from aiopvapi.resources.shade import (
    ATTR_POSKIND1,
    MAX_POSITION,
    MIN_POSITION,
    factory as PvShade,
)
import async_timeout

from homeassistant.components.cover import (
    ATTR_POSITION,
    DEVICE_CLASS_SHADE,
    SUPPORT_CLOSE,
    SUPPORT_OPEN,
    SUPPORT_SET_POSITION,
    SUPPORT_STOP,
    CoverEntity,
)
from homeassistant.core import callback
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


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the hunter douglas shades."""

    pv_data = hass.data[DOMAIN][entry.entry_id]
    room_data = pv_data[PV_ROOM_DATA]
    shade_data = pv_data[PV_SHADE_DATA]
    pv_request = pv_data[PV_API]
    coordinator = pv_data[COORDINATOR]
    device_info = pv_data[DEVICE_INFO]

    entities = []
    for raw_shade in shade_data.values():
        # The shade may be out of sync with the hub
        # so we force a refresh when we add it if
        # possible
        shade = PvShade(raw_shade, pv_request)
        name_before_refresh = shade.name
        try:
            async with async_timeout.timeout(1):
                await shade.refresh()
        except asyncio.TimeoutError:
            # Forced refresh is not required for setup
            pass
        if ATTR_POSITION_DATA not in shade.raw_data:
            _LOGGER.info(
                "The %s shade was skipped because it is missing position data",
                name_before_refresh,
            )
            continue
        entities.append(
            PowerViewShade(
                shade, name_before_refresh, room_data, coordinator, device_info
            )
        )
    async_add_entities(entities)


def hd_position_to_hass(hd_position):
    """Convert hunter douglas position to hass position."""
    return round((hd_position / MAX_POSITION) * 100)


def hass_position_to_hd(hass_positon):
    """Convert hass position to hunter douglas position."""
    return int(hass_positon / 100 * MAX_POSITION)


class PowerViewShade(ShadeEntity, CoverEntity):
    """Representation of a powerview shade."""

    def __init__(self, shade, name, room_data, coordinator, device_info):
        """Initialize the shade."""
        room_id = shade.raw_data.get(ROOM_ID_IN_SHADE)
        super().__init__(coordinator, device_info, shade, name)
        self._shade = shade
        self._device_info = device_info
        self._is_opening = False
        self._is_closing = False
        self._last_action_timestamp = 0
        self._scheduled_transition_update = None
        self._room_name = room_data.get(room_id, {}).get(ROOM_NAME_UNICODE, "")
        self._current_cover_position = MIN_POSITION

    @property
    def device_state_attributes(self):
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
        return self._current_cover_position == MIN_POSITION

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
        return hd_position_to_hass(self._current_cover_position)

    @property
    def device_class(self):
        """Return device class."""
        return DEVICE_CLASS_SHADE

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
        current_hass_position = hd_position_to_hass(self._current_cover_position)
        steps_to_move = abs(current_hass_position - target_hass_position)
        if not steps_to_move:
            return
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
            self._current_cover_position = position_data[ATTR_POSITION1]
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
        if self._scheduled_transition_update:
            # If a transition in in progress
            # the data will be wrong
            return
        self._async_process_new_shade_data(self.coordinator.data[self._shade.id])
        self.async_write_ha_state()
