"""Support for hunter douglas shades."""
from __future__ import annotations

import asyncio
from collections.abc import Iterable
from contextlib import suppress
from datetime import timedelta
import logging
from math import ceil
from typing import Any

from aiopvapi.helpers.constants import (
    ATTR_POSITION1,
    ATTR_POSITION2,
    ATTR_POSITION_DATA,
    ATTR_POSKIND1,
    ATTR_POSKIND2,
    MAX_POSITION,
    MIN_POSITION,
)
from aiopvapi.resources.shade import BaseShade, factory as PvShade
import async_timeout

from homeassistant.components.cover import (
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_call_later

from .const import (
    DOMAIN,
    LEGACY_DEVICE_MODEL,
    POS_KIND_PRIMARY,
    POS_KIND_SECONDARY,
    POS_KIND_VANE,
    ROOM_ID_IN_SHADE,
    ROOM_NAME_UNICODE,
    STATE_ATTRIBUTE_ROOM_NAME,
)
from .coordinator import PowerviewShadeUpdateCoordinator
from .entity import ShadeEntity
from .model import PowerviewDeviceInfo, PowerviewEntryData
from .shade_data import PowerviewShadeMove

_LOGGER = logging.getLogger(__name__)

# Estimated time it takes to complete a transition
# from one state to another
TRANSITION_COMPLETE_DURATION = 40

PARALLEL_UPDATES = 1

RESYNC_DELAY = 60

# this equates to 0.75/100 in terms of hass blind position
# some blinds in a closed position report less than 655.35 (1%)
# but larger than 0 even though they are clearly closed
# Find 1 percent of MAX_POSITION, then find 75% of that number
# The means currently 491.5125 or less is closed position
# implemented for top/down shades, but also works fine with normal shades
CLOSED_POSITION = (0.75 / 100) * (MAX_POSITION - MIN_POSITION)

SCAN_INTERVAL = timedelta(minutes=10)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the hunter douglas shades."""

    pv_entry: PowerviewEntryData = hass.data[DOMAIN][entry.entry_id]
    coordinator: PowerviewShadeUpdateCoordinator = pv_entry.coordinator

    entities: list[ShadeEntity] = []
    for raw_shade in pv_entry.shade_data.values():
        # The shade may be out of sync with the hub
        # so we force a refresh when we add it if possible
        shade: BaseShade = PvShade(raw_shade, pv_entry.api)
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
        coordinator.data.update_shade_positions(shade.raw_data)
        room_id = shade.raw_data.get(ROOM_ID_IN_SHADE)
        room_name = pv_entry.room_data.get(room_id, {}).get(ROOM_NAME_UNICODE, "")
        entities.extend(
            create_powerview_shade_entity(
                coordinator, pv_entry.device_info, room_name, shade, name_before_refresh
            )
        )
    async_add_entities(entities)


def hd_position_to_hass(hd_position: int, max_val: int = MAX_POSITION) -> int:
    """Convert hunter douglas position to hass position."""
    return round((hd_position / max_val) * 100)


def hass_position_to_hd(hass_position: int, max_val: int = MAX_POSITION) -> int:
    """Convert hass position to hunter douglas position."""
    return int(hass_position / 100 * max_val)


class PowerViewShadeBase(ShadeEntity, CoverEntity):
    """Representation of a powerview shade."""

    _attr_device_class = CoverDeviceClass.SHADE
    _attr_supported_features = CoverEntityFeature(0)

    def __init__(
        self,
        coordinator: PowerviewShadeUpdateCoordinator,
        device_info: PowerviewDeviceInfo,
        room_name: str,
        shade: BaseShade,
        name: str,
    ) -> None:
        """Initialize the shade."""
        super().__init__(coordinator, device_info, room_name, shade, name)
        self._shade: BaseShade = shade
        self._attr_name = self._shade_name
        self._scheduled_transition_update: CALLBACK_TYPE | None = None
        if self._device_info.model != LEGACY_DEVICE_MODEL:
            self._attr_supported_features |= CoverEntityFeature.STOP
        self._forced_resync = None

    @property
    def assumed_state(self) -> bool:
        """If the device is hard wired we are polling state.

        The hub will frequently provide the wrong state
        for battery power devices so we set assumed
        state in this case.
        """
        return not self._is_hard_wired

    @property
    def should_poll(self) -> bool:
        """Only poll if the device is hard wired.

        We cannot poll battery powered devices
        as it would drain their batteries in a matter
        of days.
        """
        return self._is_hard_wired

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Return the state attributes."""
        return {STATE_ATTRIBUTE_ROOM_NAME: self._room_name}

    @property
    def is_closed(self) -> bool:
        """Return if the cover is closed."""
        return self.positions.primary <= CLOSED_POSITION

    @property
    def current_cover_position(self) -> int:
        """Return the current position of cover."""
        return hd_position_to_hass(self.positions.primary, MAX_POSITION)

    @property
    def transition_steps(self) -> int:
        """Return the steps to make a move."""
        return hd_position_to_hass(self.positions.primary, MAX_POSITION)

    @property
    def open_position(self) -> PowerviewShadeMove:
        """Return the open position and required additional positions."""
        return PowerviewShadeMove(self._shade.open_position, {})

    @property
    def close_position(self) -> PowerviewShadeMove:
        """Return the close position and required additional positions."""
        return PowerviewShadeMove(self._shade.close_position, {})

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        self._async_schedule_update_for_transition(self.transition_steps)
        await self._async_execute_move(self.close_position)
        self._attr_is_opening = False
        self._attr_is_closing = True
        self.async_write_ha_state()

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        self._async_schedule_update_for_transition(100 - self.transition_steps)
        await self._async_execute_move(self.open_position)
        self._attr_is_opening = True
        self._attr_is_closing = False
        self.async_write_ha_state()

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        self._async_cancel_scheduled_transition_update()
        self.data.update_from_response(await self._shade.stop())
        await self._async_force_refresh_state()

    @callback
    def _clamp_cover_limit(self, target_hass_position: int) -> int:
        """Dont allow a cover to go into an impossbile position."""
        # no override required in base
        return target_hass_position

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the shade to a specific position."""
        await self._async_set_cover_position(kwargs[ATTR_POSITION])

    @callback
    def _get_shade_move(self, target_hass_position: int) -> PowerviewShadeMove:
        position_one = hass_position_to_hd(target_hass_position)
        return PowerviewShadeMove(
            {ATTR_POSITION1: position_one, ATTR_POSKIND1: POS_KIND_PRIMARY}, {}
        )

    async def _async_execute_move(self, move: PowerviewShadeMove) -> None:
        """Execute a move that can affect multiple positions."""
        response = await self._shade.move(move.request)
        # Process any positions we know will update as result
        # of the request since the hub won't return them
        for kind, position in move.new_positions.items():
            self.data.update_shade_position(self._shade.id, position, kind)
        # Finally process the response
        self.data.update_from_response(response)

    async def _async_set_cover_position(self, target_hass_position: int) -> None:
        """Move the shade to a position."""
        target_hass_position = self._clamp_cover_limit(target_hass_position)
        current_hass_position = self.current_cover_position
        self._async_schedule_update_for_transition(
            abs(current_hass_position - target_hass_position)
        )
        await self._async_execute_move(self._get_shade_move(target_hass_position))
        self._attr_is_opening = target_hass_position > current_hass_position
        self._attr_is_closing = target_hass_position < current_hass_position
        self.async_write_ha_state()

    @callback
    def _async_update_shade_data(self, shade_data: dict[str | int, Any]) -> None:
        """Update the current cover position from the data."""
        self.data.update_shade_positions(shade_data)
        self._attr_is_opening = False
        self._attr_is_closing = False

    @callback
    def _async_cancel_scheduled_transition_update(self) -> None:
        """Cancel any previous updates."""
        if self._scheduled_transition_update:
            self._scheduled_transition_update()
            self._scheduled_transition_update = None
        if self._forced_resync:
            self._forced_resync()
            self._forced_resync = None

    @callback
    def _async_schedule_update_for_transition(self, steps: int) -> None:
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

        # Schedule an forced update for when we expect the transition
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
        self._forced_resync = async_call_later(
            self.hass, RESYNC_DELAY, self._async_force_resync
        )

    async def _async_force_resync(self, *_: Any) -> None:
        """Force a resync after an update since the hub may have stale state."""
        self._forced_resync = None
        _LOGGER.debug("Force resync of shade %s", self.name)
        await self._async_force_refresh_state()

    async def _async_force_refresh_state(self) -> None:
        """Refresh the cover state and force the device cache to be bypassed."""
        await self.async_update()
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self._async_update_shade_from_group)
        )

    async def async_will_remove_from_hass(self) -> None:
        """Cancel any pending refreshes."""
        self._async_cancel_scheduled_transition_update()

    @property
    def _update_in_progress(self) -> bool:
        """Check if an update is already in progress."""
        return bool(self._scheduled_transition_update or self._forced_resync)

    @callback
    def _async_update_shade_from_group(self) -> None:
        """Update with new data from the coordinator."""
        if self._update_in_progress:
            # If a transition is in progress the data will be wrong
            return
        self.data.update_from_group_data(self._shade.id)
        self.async_write_ha_state()

    async def async_update(self) -> None:
        """Refresh shade position."""
        if self._update_in_progress:
            # The update will likely timeout and
            # error if are already have one in flight
            return
        await self._shade.refresh()
        self._async_update_shade_data(self._shade.raw_data)


class PowerViewShade(PowerViewShadeBase):
    """Represent a standard shade."""

    def __init__(
        self,
        coordinator: PowerviewShadeUpdateCoordinator,
        device_info: PowerviewDeviceInfo,
        room_name: str,
        shade: BaseShade,
        name: str,
    ) -> None:
        """Initialize the shade."""
        super().__init__(coordinator, device_info, room_name, shade, name)
        self._attr_supported_features |= (
            CoverEntityFeature.OPEN
            | CoverEntityFeature.CLOSE
            | CoverEntityFeature.SET_POSITION
        )


class PowerViewShadeWithTiltBase(PowerViewShade):
    """Representation for PowerView shades with tilt capabilities."""

    def __init__(
        self,
        coordinator: PowerviewShadeUpdateCoordinator,
        device_info: PowerviewDeviceInfo,
        room_name: str,
        shade: BaseShade,
        name: str,
    ) -> None:
        """Initialize the shade."""
        super().__init__(coordinator, device_info, room_name, shade, name)
        self._attr_supported_features |= (
            CoverEntityFeature.OPEN_TILT
            | CoverEntityFeature.CLOSE_TILT
            | CoverEntityFeature.SET_TILT_POSITION
        )
        if self._device_info.model != LEGACY_DEVICE_MODEL:
            self._attr_supported_features |= CoverEntityFeature.STOP_TILT
        self._max_tilt = self._shade.shade_limits.tilt_max

    @property
    def current_cover_tilt_position(self) -> int:
        """Return the current cover tile position."""
        return hd_position_to_hass(self.positions.vane, self._max_tilt)

    @property
    def transition_steps(self):
        """Return the steps to make a move."""
        return hd_position_to_hass(
            self.positions.primary, MAX_POSITION
        ) + hd_position_to_hass(self.positions.vane, self._max_tilt)

    @property
    def open_tilt_position(self) -> PowerviewShadeMove:
        """Return the open tilt position and required additional positions."""
        return PowerviewShadeMove(self._shade.open_position_tilt, {})

    @property
    def close_tilt_position(self) -> PowerviewShadeMove:
        """Return the close tilt position and required additional positions."""
        return PowerviewShadeMove(self._shade.close_position_tilt, {})

    async def async_close_cover_tilt(self, **kwargs: Any) -> None:
        """Close the cover tilt."""
        self._async_schedule_update_for_transition(self.transition_steps)
        await self._async_execute_move(self.close_tilt_position)
        self.async_write_ha_state()

    async def async_open_cover_tilt(self, **kwargs: Any) -> None:
        """Open the cover tilt."""
        self._async_schedule_update_for_transition(100 - self.transition_steps)
        await self._async_execute_move(self.open_tilt_position)
        self.async_write_ha_state()

    async def async_set_cover_tilt_position(self, **kwargs: Any) -> None:
        """Move the vane to a specific position."""
        await self._async_set_cover_tilt_position(kwargs[ATTR_TILT_POSITION])

    async def _async_set_cover_tilt_position(
        self, target_hass_tilt_position: int
    ) -> None:
        """Move the vane to a specific position."""
        final_position = self.current_cover_position + target_hass_tilt_position
        self._async_schedule_update_for_transition(
            abs(self.transition_steps - final_position)
        )
        await self._async_execute_move(self._get_shade_tilt(target_hass_tilt_position))
        self.async_write_ha_state()

    @callback
    def _get_shade_tilt(self, target_hass_tilt_position: int) -> PowerviewShadeMove:
        """Return a PowerviewShadeMove."""
        position_vane = hass_position_to_hd(target_hass_tilt_position, self._max_tilt)
        return PowerviewShadeMove(
            {ATTR_POSITION1: position_vane, ATTR_POSKIND1: POS_KIND_VANE}, {}
        )

    async def async_stop_cover_tilt(self, **kwargs: Any) -> None:
        """Stop the cover tilting."""
        await self.async_stop_cover()


class PowerViewShadeWithTiltOnClosed(PowerViewShadeWithTiltBase):
    """Representation of a PowerView shade with tilt when closed capabilities.

    API Class: ShadeBottomUpTiltOnClosed + ShadeBottomUpTiltOnClosed90

    Type 1 - Bottom Up w/ 90° Tilt
    Shade 44 - a shade thought to have been a firmware issue (type 0 usually dont tilt)
    """

    @property
    def open_position(self) -> PowerviewShadeMove:
        """Return the open position and required additional positions."""
        return PowerviewShadeMove(
            self._shade.open_position, {POS_KIND_VANE: MIN_POSITION}
        )

    @property
    def close_position(self) -> PowerviewShadeMove:
        """Return the close position and required additional positions."""
        return PowerviewShadeMove(
            self._shade.close_position, {POS_KIND_VANE: MIN_POSITION}
        )

    @property
    def open_tilt_position(self) -> PowerviewShadeMove:
        """Return the open tilt position and required additional positions."""
        return PowerviewShadeMove(
            self._shade.open_position_tilt, {POS_KIND_PRIMARY: MIN_POSITION}
        )

    @property
    def close_tilt_position(self) -> PowerviewShadeMove:
        """Return the close tilt position and required additional positions."""
        return PowerviewShadeMove(
            self._shade.close_position_tilt, {POS_KIND_PRIMARY: MIN_POSITION}
        )

    @callback
    def _get_shade_move(self, target_hass_position: int) -> PowerviewShadeMove:
        """Return a PowerviewShadeMove."""
        position_shade = hass_position_to_hd(target_hass_position)
        return PowerviewShadeMove(
            {ATTR_POSITION1: position_shade, ATTR_POSKIND1: POS_KIND_PRIMARY},
            {POS_KIND_VANE: MIN_POSITION},
        )

    @callback
    def _get_shade_tilt(self, target_hass_tilt_position: int) -> PowerviewShadeMove:
        """Return a PowerviewShadeMove."""
        position_vane = hass_position_to_hd(target_hass_tilt_position, self._max_tilt)
        return PowerviewShadeMove(
            {ATTR_POSITION1: position_vane, ATTR_POSKIND1: POS_KIND_VANE},
            {POS_KIND_PRIMARY: MIN_POSITION},
        )


class PowerViewShadeWithTiltAnywhere(PowerViewShadeWithTiltBase):
    """Representation of a PowerView shade with tilt anywhere capabilities.

    API Class: ShadeBottomUpTiltAnywhere, ShadeVerticalTiltAnywhere

    Type 2 - Bottom Up w/ 180° Tilt
    Type 4 - Vertical (Traversing) w/ 180° Tilt
    """

    @callback
    def _get_shade_move(self, target_hass_position: int) -> PowerviewShadeMove:
        position_shade = hass_position_to_hd(target_hass_position, MAX_POSITION)
        position_vane = self.positions.vane
        return PowerviewShadeMove(
            {
                ATTR_POSITION1: position_shade,
                ATTR_POSITION2: position_vane,
                ATTR_POSKIND1: POS_KIND_PRIMARY,
                ATTR_POSKIND2: POS_KIND_VANE,
            },
            {},
        )

    @callback
    def _get_shade_tilt(self, target_hass_tilt_position: int) -> PowerviewShadeMove:
        """Return a PowerviewShadeMove."""
        position_shade = self.positions.primary
        position_vane = hass_position_to_hd(target_hass_tilt_position, self._max_tilt)
        return PowerviewShadeMove(
            {
                ATTR_POSITION1: position_shade,
                ATTR_POSITION2: position_vane,
                ATTR_POSKIND1: POS_KIND_PRIMARY,
                ATTR_POSKIND2: POS_KIND_VANE,
            },
            {},
        )


class PowerViewShadeTiltOnly(PowerViewShadeWithTiltBase):
    """Representation of a shade with tilt only capability, no move.

    API Class: ShadeTiltOnly

    Type 5 - Tilt Only 180°
    """

    def __init__(
        self,
        coordinator: PowerviewShadeUpdateCoordinator,
        device_info: PowerviewDeviceInfo,
        room_name: str,
        shade: BaseShade,
        name: str,
    ) -> None:
        """Initialize the shade."""
        super().__init__(coordinator, device_info, room_name, shade, name)
        self._attr_supported_features = (
            CoverEntityFeature.OPEN_TILT
            | CoverEntityFeature.CLOSE_TILT
            | CoverEntityFeature.SET_TILT_POSITION
        )
        if self._device_info.model != LEGACY_DEVICE_MODEL:
            self._attr_supported_features |= CoverEntityFeature.STOP_TILT
        self._max_tilt = self._shade.shade_limits.tilt_max


class PowerViewShadeTopDown(PowerViewShade):
    """Representation of a shade that lowers from the roof to the floor.

    These shades are inverted where MAX_POSITION equates to closed and MIN_POSITION is open
    API Class: ShadeTopDown

    Type 6 - Top Down
    """

    @property
    def current_cover_position(self) -> int:
        """Return the current position of cover."""
        return hd_position_to_hass(MAX_POSITION - self.positions.primary, MAX_POSITION)

    @property
    def is_closed(self) -> bool:
        """Return if the cover is closed."""
        return (MAX_POSITION - self.positions.primary) <= CLOSED_POSITION

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the shade to a specific position."""
        await self._async_set_cover_position(100 - kwargs[ATTR_POSITION])


class PowerViewShadeDualRailBase(PowerViewShade):
    """Representation of a shade with top/down bottom/up capabilities.

    Base methods shared between the two shades created
    Child Classes: PowerViewShadeTDBUBottom / PowerViewShadeTDBUTop
    API Class: ShadeTopDownBottomUp
    """

    @property
    def transition_steps(self) -> int:
        """Return the steps to make a move."""
        return hd_position_to_hass(
            self.positions.primary, MAX_POSITION
        ) + hd_position_to_hass(self.positions.secondary, MAX_POSITION)


class PowerViewShadeTDBUBottom(PowerViewShadeDualRailBase):
    """Representation of the bottom PowerViewShadeDualRailBase shade.

    These shades have top/down bottom up functionality and two entiites.
    Sibling Class: PowerViewShadeTDBUTop
    API Class: ShadeTopDownBottomUp
    """

    def __init__(
        self,
        coordinator: PowerviewShadeUpdateCoordinator,
        device_info: PowerviewDeviceInfo,
        room_name: str,
        shade: BaseShade,
        name: str,
    ) -> None:
        """Initialize the shade."""
        super().__init__(coordinator, device_info, room_name, shade, name)
        self._attr_unique_id = f"{self._shade.id}_bottom"
        self._attr_name = f"{self._shade_name} Bottom"

    @callback
    def _clamp_cover_limit(self, target_hass_position: int) -> int:
        """Dont allow a cover to go into an impossbile position."""
        cover_top = hd_position_to_hass(self.positions.secondary, MAX_POSITION)
        return min(target_hass_position, (100 - cover_top))

    @callback
    def _get_shade_move(self, target_hass_position: int) -> PowerviewShadeMove:
        position_bottom = hass_position_to_hd(target_hass_position)
        position_top = self.positions.secondary
        return PowerviewShadeMove(
            {
                ATTR_POSITION1: position_bottom,
                ATTR_POSITION2: position_top,
                ATTR_POSKIND1: POS_KIND_PRIMARY,
                ATTR_POSKIND2: POS_KIND_SECONDARY,
            },
            {},
        )


class PowerViewShadeTDBUTop(PowerViewShadeDualRailBase):
    """Representation of the top PowerViewShadeDualRailBase shade.

    These shades have top/down bottom up functionality and two entiites.
    Sibling Class: PowerViewShadeTDBUBottom
    API Class: ShadeTopDownBottomUp
    """

    def __init__(
        self,
        coordinator: PowerviewShadeUpdateCoordinator,
        device_info: PowerviewDeviceInfo,
        room_name: str,
        shade: BaseShade,
        name: str,
    ) -> None:
        """Initialize the shade."""
        super().__init__(coordinator, device_info, room_name, shade, name)
        self._attr_unique_id = f"{self._shade.id}_top"
        self._attr_name = f"{self._shade_name} Top"

    @property
    def should_poll(self) -> bool:
        """Certain shades create multiple entities.

        Do not poll shade multiple times. One shade will return data
        for both and multiple polling will cause timeouts.
        """
        return False

    @property
    def is_closed(self) -> bool:
        """Return if the cover is closed."""
        # top shade needs to check other motor
        return self.positions.secondary <= CLOSED_POSITION

    @property
    def current_cover_position(self) -> int:
        """Return the current position of cover."""
        # these need to be inverted to report state correctly in HA
        return hd_position_to_hass(self.positions.secondary, MAX_POSITION)

    @property
    def open_position(self) -> PowerviewShadeMove:
        """Return the open position and required additional positions."""
        # these shades share a class in parent API
        # override open position for top shade
        return PowerviewShadeMove(
            {
                ATTR_POSITION1: MIN_POSITION,
                ATTR_POSITION2: MAX_POSITION,
                ATTR_POSKIND1: POS_KIND_PRIMARY,
                ATTR_POSKIND2: POS_KIND_SECONDARY,
            },
            {},
        )

    @callback
    def _clamp_cover_limit(self, target_hass_position: int) -> int:
        """Dont allow a cover to go into an impossbile position."""
        cover_bottom = hd_position_to_hass(self.positions.primary, MAX_POSITION)
        return min(target_hass_position, (100 - cover_bottom))

    @callback
    def _get_shade_move(self, target_hass_position: int) -> PowerviewShadeMove:
        position_bottom = self.positions.primary
        position_top = hass_position_to_hd(target_hass_position, MAX_POSITION)
        return PowerviewShadeMove(
            {
                ATTR_POSITION1: position_bottom,
                ATTR_POSITION2: position_top,
                ATTR_POSKIND1: POS_KIND_PRIMARY,
                ATTR_POSKIND2: POS_KIND_SECONDARY,
            },
            {},
        )


class PowerViewShadeDualOverlappedBase(PowerViewShade):
    """Represent a shade that has a front sheer and rear opaque panel.

    This equates to two shades being controlled by one motor
    """

    @property
    def transition_steps(self) -> int:
        """Return the steps to make a move."""
        # poskind 1 represents the second half of the shade in hass
        # front must be fully closed before rear can move
        # 51 - 100 is equiv to 1-100 on other shades - one motor, two shades
        primary = (hd_position_to_hass(self.positions.primary, MAX_POSITION) / 2) + 50
        # poskind 2 represents the shade first half of the shade in hass
        # rear (opaque) must be fully open before front can move
        # 51 - 100 is equiv to 1-100 on other shades - one motor, two shades
        secondary = hd_position_to_hass(self.positions.secondary, MAX_POSITION) / 2
        return ceil(primary + secondary)

    @property
    def open_position(self) -> PowerviewShadeMove:
        """Return the open position and required additional positions."""
        return PowerviewShadeMove(
            {
                ATTR_POSITION1: MAX_POSITION,
                ATTR_POSKIND1: POS_KIND_PRIMARY,
            },
            {POS_KIND_SECONDARY: MIN_POSITION, POS_KIND_VANE: MIN_POSITION},
        )

    @property
    def close_position(self) -> PowerviewShadeMove:
        """Return the open position and required additional positions."""
        return PowerviewShadeMove(
            {
                ATTR_POSITION1: MIN_POSITION,
                ATTR_POSKIND1: POS_KIND_SECONDARY,
            },
            {POS_KIND_PRIMARY: MIN_POSITION, POS_KIND_VANE: MIN_POSITION},
        )


class PowerViewShadeDualOverlappedCombined(PowerViewShadeDualOverlappedBase):
    """Represent a shade that has a front sheer and rear opaque panel.

    This equates to two shades being controlled by one motor.
    The front shade must be completely down before the rear shade will move.
    Sibling Class: PowerViewShadeDualOverlappedFront, PowerViewShadeDualOverlappedRear
    API Class: ShadeDualOverlapped

    Type 8 - Duolite (front and rear shades)
    """

    # type
    def __init__(
        self,
        coordinator: PowerviewShadeUpdateCoordinator,
        device_info: PowerviewDeviceInfo,
        room_name: str,
        shade: BaseShade,
        name: str,
    ) -> None:
        """Initialize the shade."""
        super().__init__(coordinator, device_info, room_name, shade, name)
        self._attr_unique_id = f"{self._shade.id}_combined"
        self._attr_name = f"{self._shade_name} Combined"

    @property
    def is_closed(self) -> bool:
        """Return if the cover is closed."""
        # if rear shade is down it is closed
        return self.positions.secondary <= CLOSED_POSITION

    @property
    def current_cover_position(self) -> int:
        """Return the current position of cover."""
        # if front is open return that (other positions are impossible)
        # if front shade is closed get position of rear
        position = (hd_position_to_hass(self.positions.primary, MAX_POSITION) / 2) + 50
        if self.positions.primary == MIN_POSITION:
            position = hd_position_to_hass(self.positions.secondary, MAX_POSITION) / 2

        return ceil(position)

    @callback
    def _get_shade_move(self, target_hass_position: int) -> PowerviewShadeMove:
        position_shade = hass_position_to_hd(target_hass_position, MAX_POSITION)
        # note we set POS_KIND_VANE: MIN_POSITION here even with shades without tilt so no additional
        # override is required for differences between type 8/9/10
        # this just stores the value in the coordinator for future reference
        if target_hass_position <= 50:
            target_hass_position = target_hass_position * 2
            return PowerviewShadeMove(
                {
                    ATTR_POSITION1: position_shade,
                    ATTR_POSKIND1: POS_KIND_SECONDARY,
                },
                {POS_KIND_PRIMARY: MIN_POSITION, POS_KIND_VANE: MIN_POSITION},
            )

        # 51 <= target_hass_position <= 100 (51-100 represents front sheer shade)
        target_hass_position = (target_hass_position - 50) * 2
        return PowerviewShadeMove(
            {
                ATTR_POSITION1: position_shade,
                ATTR_POSKIND1: POS_KIND_PRIMARY,
            },
            {POS_KIND_SECONDARY: MAX_POSITION, POS_KIND_VANE: MIN_POSITION},
        )


class PowerViewShadeDualOverlappedFront(PowerViewShadeDualOverlappedBase):
    """Represent the shade front panel - These have a opaque panel too.

    This equates to two shades being controlled by one motor.
    The front shade must be completely down before the rear shade will move.
    Sibling Class: PowerViewShadeDualOverlappedCombined, PowerViewShadeDualOverlappedRear
    API Class: ShadeDualOverlapped + ShadeDualOverlappedTilt90 + ShadeDualOverlappedTilt180

    Type 8 - Duolite (front and rear shades)
    Type 9 - Duolite with 90° Tilt (front bottom up shade that also tilts plus a rear opaque (non-tilting) shade)
    Type 10 - Duolite with 180° Tilt
    """

    def __init__(
        self,
        coordinator: PowerviewShadeUpdateCoordinator,
        device_info: PowerviewDeviceInfo,
        room_name: str,
        shade: BaseShade,
        name: str,
    ) -> None:
        """Initialize the shade."""
        super().__init__(coordinator, device_info, room_name, shade, name)
        self._attr_unique_id = f"{self._shade.id}_front"
        self._attr_name = f"{self._shade_name} Front"

    @property
    def should_poll(self) -> bool:
        """Certain shades create multiple entities.

        Do not poll shade multiple times. Combined shade will return data
        and multiple polling will cause timeouts.
        """
        return False

    @callback
    def _get_shade_move(self, target_hass_position: int) -> PowerviewShadeMove:
        position_shade = hass_position_to_hd(target_hass_position, MAX_POSITION)
        # note we set POS_KIND_VANE: MIN_POSITION here even with shades without tilt so no additional
        # override is required for differences between type 8/9/10
        # this just stores the value in the coordinator for future reference
        return PowerviewShadeMove(
            {
                ATTR_POSITION1: position_shade,
                ATTR_POSKIND1: POS_KIND_PRIMARY,
            },
            {POS_KIND_SECONDARY: MAX_POSITION, POS_KIND_VANE: MIN_POSITION},
        )

    @property
    def close_position(self) -> PowerviewShadeMove:
        """Return the close position and required additional positions."""
        return PowerviewShadeMove(
            {
                ATTR_POSITION1: MIN_POSITION,
                ATTR_POSKIND1: POS_KIND_PRIMARY,
            },
            {POS_KIND_SECONDARY: MAX_POSITION, POS_KIND_VANE: MIN_POSITION},
        )


class PowerViewShadeDualOverlappedRear(PowerViewShadeDualOverlappedBase):
    """Represent the shade front panel - These have a opaque panel too.

    This equates to two shades being controlled by one motor.
    The front shade must be completely down before the rear shade will move.
    Sibling Class: PowerViewShadeDualOverlappedCombined, PowerViewShadeDualOverlappedFront
    API Class: ShadeDualOverlapped + ShadeDualOverlappedTilt90 + ShadeDualOverlappedTilt180

    Type 8 - Duolite (front and rear shades)
    Type 9 - Duolite with 90° Tilt (front bottom up shade that also tilts plus a rear opaque (non-tilting) shade)
    Type 10 - Duolite with 180° Tilt
    """

    def __init__(
        self,
        coordinator: PowerviewShadeUpdateCoordinator,
        device_info: PowerviewDeviceInfo,
        room_name: str,
        shade: BaseShade,
        name: str,
    ) -> None:
        """Initialize the shade."""
        super().__init__(coordinator, device_info, room_name, shade, name)
        self._attr_unique_id = f"{self._shade.id}_rear"
        self._attr_name = f"{self._shade_name} Rear"

    @property
    def should_poll(self) -> bool:
        """Certain shades create multiple entities.

        Do not poll shade multiple times. Combined shade will return data
        and multiple polling will cause timeouts.
        """
        return False

    @property
    def is_closed(self) -> bool:
        """Return if the cover is closed."""
        # if rear shade is down it is closed
        return self.positions.secondary <= CLOSED_POSITION

    @property
    def current_cover_position(self) -> int:
        """Return the current position of cover."""
        return hd_position_to_hass(self.positions.secondary, MAX_POSITION)

    @callback
    def _get_shade_move(self, target_hass_position: int) -> PowerviewShadeMove:
        position_shade = hass_position_to_hd(target_hass_position, MAX_POSITION)
        # note we set POS_KIND_VANE: MIN_POSITION here even with shades without tilt so no additional
        # override is required for differences between type 8/9/10
        # this just stores the value in the coordinator for future reference
        return PowerviewShadeMove(
            {
                ATTR_POSITION1: position_shade,
                ATTR_POSKIND1: POS_KIND_SECONDARY,
            },
            {POS_KIND_PRIMARY: MIN_POSITION, POS_KIND_VANE: MIN_POSITION},
        )

    @property
    def open_position(self) -> PowerviewShadeMove:
        """Return the open position and required additional positions."""
        return PowerviewShadeMove(
            {
                ATTR_POSITION1: MAX_POSITION,
                ATTR_POSKIND1: POS_KIND_SECONDARY,
            },
            {POS_KIND_PRIMARY: MIN_POSITION, POS_KIND_VANE: MIN_POSITION},
        )


class PowerViewShadeDualOverlappedCombinedTilt(PowerViewShadeDualOverlappedCombined):
    """Represent a shade that has a front sheer and rear opaque panel.

    This equates to two shades being controlled by one motor.
    The front shade must be completely down before the rear shade will move.
    Tilting this shade will also force positional change of the main roller.

    Sibling Class: PowerViewShadeDualOverlappedFront, PowerViewShadeDualOverlappedRear
    API Class: ShadeDualOverlappedTilt90 + ShadeDualOverlappedTilt180

    Type 9 - Duolite with 90° Tilt (front bottom up shade that also tilts plus a rear opaque (non-tilting) shade)
    Type 10 - Duolite with 180° Tilt
    """

    # type
    def __init__(
        self,
        coordinator: PowerviewShadeUpdateCoordinator,
        device_info: PowerviewDeviceInfo,
        room_name: str,
        shade: BaseShade,
        name: str,
    ) -> None:
        """Initialize the shade."""
        super().__init__(coordinator, device_info, room_name, shade, name)
        self._attr_supported_features |= (
            CoverEntityFeature.OPEN_TILT
            | CoverEntityFeature.CLOSE_TILT
            | CoverEntityFeature.SET_TILT_POSITION
        )
        if self._device_info.model != LEGACY_DEVICE_MODEL:
            self._attr_supported_features |= CoverEntityFeature.STOP_TILT
        self._max_tilt = self._shade.shade_limits.tilt_max

    @property
    def transition_steps(self) -> int:
        """Return the steps to make a move."""
        # poskind 1 represents the second half of the shade in hass
        # front must be fully closed before rear can move
        # 51 - 100 is equiv to 1-100 on other shades - one motor, two shades
        primary = (hd_position_to_hass(self.positions.primary, MAX_POSITION) / 2) + 50
        # poskind 2 represents the shade first half of the shade in hass
        # rear (opaque) must be fully open before front can move
        # 51 - 100 is equiv to 1-100 on other shades - one motor, two shades
        secondary = hd_position_to_hass(self.positions.secondary, MAX_POSITION) / 2
        vane = hd_position_to_hass(self.positions.vane, self._max_tilt)
        return ceil(primary + secondary + vane)

    @callback
    def _get_shade_tilt(self, target_hass_tilt_position: int) -> PowerviewShadeMove:
        """Return a PowerviewShadeMove."""
        position_vane = hass_position_to_hd(target_hass_tilt_position, self._max_tilt)
        return PowerviewShadeMove(
            {
                ATTR_POSITION1: position_vane,
                ATTR_POSKIND1: POS_KIND_VANE,
            },
            {POS_KIND_PRIMARY: MIN_POSITION, POS_KIND_SECONDARY: MAX_POSITION},
        )

    @property
    def open_tilt_position(self) -> PowerviewShadeMove:
        """Return the open tilt position and required additional positions."""
        return PowerviewShadeMove(
            self._shade.open_position_tilt,
            {POS_KIND_PRIMARY: MIN_POSITION, POS_KIND_SECONDARY: MAX_POSITION},
        )

    @property
    def close_tilt_position(self) -> PowerviewShadeMove:
        """Return the open tilt position and required additional positions."""
        return PowerviewShadeMove(
            self._shade.open_position_tilt,
            {POS_KIND_PRIMARY: MIN_POSITION, POS_KIND_SECONDARY: MAX_POSITION},
        )


TYPE_TO_CLASSES = {
    0: (PowerViewShade,),
    1: (PowerViewShadeWithTiltOnClosed,),
    2: (PowerViewShadeWithTiltAnywhere,),
    3: (PowerViewShade,),
    4: (PowerViewShadeWithTiltAnywhere,),
    5: (PowerViewShadeTiltOnly,),
    6: (PowerViewShadeTopDown,),
    7: (
        PowerViewShadeTDBUTop,
        PowerViewShadeTDBUBottom,
    ),
    8: (
        PowerViewShadeDualOverlappedCombined,
        PowerViewShadeDualOverlappedFront,
        PowerViewShadeDualOverlappedRear,
    ),
    9: (
        PowerViewShadeDualOverlappedCombinedTilt,
        PowerViewShadeDualOverlappedFront,
        PowerViewShadeDualOverlappedRear,
    ),
    10: (
        PowerViewShadeDualOverlappedCombinedTilt,
        PowerViewShadeDualOverlappedFront,
        PowerViewShadeDualOverlappedRear,
    ),
}


def create_powerview_shade_entity(
    coordinator: PowerviewShadeUpdateCoordinator,
    device_info: PowerviewDeviceInfo,
    room_name: str,
    shade: BaseShade,
    name_before_refresh: str,
) -> Iterable[ShadeEntity]:
    """Create a PowerViewShade entity."""
    classes: Iterable[BaseShade] = TYPE_TO_CLASSES.get(
        shade.capability.type, (PowerViewShade,)
    )
    _LOGGER.debug(
        "%s (%s) detected as %a %s",
        shade.name,
        shade.capability.type,
        classes,
        shade.raw_data,
    )
    return [
        cls(coordinator, device_info, room_name, shade, name_before_refresh)
        for cls in classes
    ]
