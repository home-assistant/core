"""Support for hunter douglas shades."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import replace
from datetime import datetime, timedelta
import logging
from math import ceil
from typing import Any

from aiopvapi.helpers.constants import (
    ATTR_NAME,
    CLOSED_POSITION,
    MAX_POSITION,
    MIN_POSITION,
    MOTION_STOP,
)
from aiopvapi.resources.shade import BaseShade, ShadePosition

from homeassistant.components.cover import (
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_call_later

from .const import STATE_ATTRIBUTE_ROOM_NAME
from .coordinator import PowerviewShadeUpdateCoordinator
from .entity import ShadeEntity
from .model import PowerviewConfigEntry, PowerviewDeviceInfo

_LOGGER = logging.getLogger(__name__)

# Estimated time it takes to complete a transition
# from one state to another
TRANSITION_COMPLETE_DURATION = 40

PARALLEL_UPDATES = 1

RESYNC_DELAY = 60

SCAN_INTERVAL = timedelta(minutes=10)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PowerviewConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the hunter douglas shades."""
    pv_entry = entry.runtime_data
    coordinator = pv_entry.coordinator

    async def _async_initial_refresh() -> None:
        """Force position refresh shortly after adding.

        Legacy shades can become out of sync with hub when moved
        using physical remotes. This also allows reducing speed
        of calls to older generation hubs in an effort to
        prevent hub crashes.
        """

        for shade in pv_entry.shade_data.values():
            _LOGGER.debug("Initial refresh of shade: %s", shade.name)
            async with coordinator.radio_operation_lock:
                await shade.refresh(suppress_timeout=True)  # default 15 second timeout

    entities: list[ShadeEntity] = []
    for shade in pv_entry.shade_data.values():
        room_name = getattr(pv_entry.room_data.get(shade.room_id), ATTR_NAME, "")
        entities.extend(
            create_powerview_shade_entity(
                coordinator, pv_entry.device_info, room_name, shade, shade.name
            )
        )

    async_add_entities(entities)

    # background the fetching of state for initial launch
    entry.async_create_background_task(
        hass,
        _async_initial_refresh(),
        f"powerview {entry.title} initial shade refresh",
    )


class PowerViewShadeBase(ShadeEntity, CoverEntity):
    """Representation of a powerview shade."""

    _attr_device_class = CoverDeviceClass.SHADE
    _attr_supported_features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.SET_POSITION
    )

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
        self._scheduled_transition_update: CALLBACK_TYPE | None = None
        if self._shade.is_supported(MOTION_STOP):
            self._attr_supported_features |= CoverEntityFeature.STOP
        self._forced_resync: Callable[[], None] | None = None

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
        return self.positions.primary

    @property
    def transition_steps(self) -> int:
        """Return the steps to make a move."""
        return self.positions.primary

    @property
    def open_position(self) -> ShadePosition:
        """Return the open position and required additional positions."""
        return replace(self._shade.open_position, velocity=self.positions.velocity)

    @property
    def close_position(self) -> ShadePosition:
        """Return the close position and required additional positions."""
        return replace(self._shade.close_position, velocity=self.positions.velocity)

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
        await self._shade.stop()
        await self._async_force_refresh_state()

    @callback
    def _clamp_cover_limit(self, target_hass_position: int) -> int:
        """Don't allow a cover to go into an impossbile position."""
        # no override required in base
        return target_hass_position

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the shade to a specific position."""
        await self._async_set_cover_position(kwargs[ATTR_POSITION])

    @callback
    def _get_shade_move(self, target_hass_position: int) -> ShadePosition:
        """Return a ShadePosition."""
        return ShadePosition(
            primary=target_hass_position,
            velocity=self.positions.velocity,
        )

    async def _async_execute_move(self, move: ShadePosition) -> None:
        """Execute a move that can affect multiple positions."""
        _LOGGER.debug("Move request %s: %s", self.name, move)
        async with self.coordinator.radio_operation_lock:
            response = await self._shade.move(move)
        _LOGGER.debug("Move response %s: %s", self.name, response)

        # Process the response from the hub (including new positions)
        self.data.update_shade_position(self._shade.id, response)

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
    def _async_update_shade_data(self, shade_data: ShadePosition) -> None:
        """Update the current cover position from the data."""
        self.data.update_shade_position(self._shade.id, shade_data)
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

        # Schedule a forced update for when we expect the transition
        # to be completed.
        self._scheduled_transition_update = async_call_later(
            self.hass,
            est_time_to_complete_transition,
            self._async_complete_schedule_update,
        )

    async def _async_complete_schedule_update(self, _: datetime) -> None:
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

    # pylint: disable-next=hass-missing-super-call
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
        # suppress timeouts caused by hub nightly reboot
        async with self.coordinator.radio_operation_lock:
            await self._shade.refresh(
                suppress_timeout=True
            )  # default 15 second timeout
        _LOGGER.debug("Process update %s: %s", self.name, self._shade.current_position)
        self._async_update_shade_data(self._shade.current_position)


class PowerViewShade(PowerViewShadeBase):
    """Represent a standard shade."""

    _attr_name = None


class PowerViewShadeWithTiltBase(PowerViewShadeBase):
    """Representation for PowerView shades with tilt capabilities."""

    _attr_name = None

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
        if self._shade.is_supported(MOTION_STOP):
            self._attr_supported_features |= CoverEntityFeature.STOP_TILT
        self._max_tilt = self._shade.shade_limits.tilt_max

    @property
    def current_cover_tilt_position(self) -> int:
        """Return the current cover tile position."""
        return self.positions.tilt

    @property
    def transition_steps(self) -> int:
        """Return the steps to make a move."""
        return self.positions.primary + self.positions.tilt

    @property
    def open_tilt_position(self) -> ShadePosition:
        """Return the open tilt position and required additional positions."""
        return replace(self._shade.open_position_tilt, velocity=self.positions.velocity)

    @property
    def close_tilt_position(self) -> ShadePosition:
        """Return the close tilt position and required additional positions."""
        return replace(
            self._shade.close_position_tilt, velocity=self.positions.velocity
        )

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
        """Move the tilt to a specific position."""
        await self._async_set_cover_tilt_position(kwargs[ATTR_TILT_POSITION])

    async def _async_set_cover_tilt_position(
        self, target_hass_tilt_position: int
    ) -> None:
        """Move the tilt to a specific position."""
        final_position = self.current_cover_position + target_hass_tilt_position
        self._async_schedule_update_for_transition(
            abs(self.transition_steps - final_position)
        )
        await self._async_execute_move(self._get_shade_tilt(target_hass_tilt_position))
        self.async_write_ha_state()

    @callback
    def _get_shade_move(self, target_hass_position: int) -> ShadePosition:
        """Return a ShadePosition."""
        return ShadePosition(
            primary=target_hass_position,
            velocity=self.positions.velocity,
        )

    @callback
    def _get_shade_tilt(self, target_hass_tilt_position: int) -> ShadePosition:
        """Return a ShadePosition."""
        return ShadePosition(
            tilt=target_hass_tilt_position,
            velocity=self.positions.velocity,
        )

    async def async_stop_cover_tilt(self, **kwargs: Any) -> None:
        """Stop the cover tilting."""
        await self.async_stop_cover()


class PowerViewShadeWithTiltOnClosed(PowerViewShadeWithTiltBase):
    """Representation of a PowerView shade with tilt when closed capabilities.

    API Class: ShadeBottomUpTiltOnClosed + ShadeBottomUpTiltOnClosed90

    Type 1 - Bottom Up w/ 90° Tilt
    Shade 44 - a shade thought to have been a firmware issue (type 0 usually don't tilt)
    """

    _attr_name = None

    @property
    def open_position(self) -> ShadePosition:
        """Return the open position and required additional positions."""
        return replace(self._shade.open_position, velocity=self.positions.velocity)

    @property
    def close_position(self) -> ShadePosition:
        """Return the close position and required additional positions."""
        return replace(self._shade.close_position, velocity=self.positions.velocity)

    @property
    def open_tilt_position(self) -> ShadePosition:
        """Return the open tilt position and required additional positions."""
        return replace(self._shade.open_position_tilt, velocity=self.positions.velocity)

    @property
    def close_tilt_position(self) -> ShadePosition:
        """Return the close tilt position and required additional positions."""
        return replace(
            self._shade.close_position_tilt, velocity=self.positions.velocity
        )


class PowerViewShadeWithTiltAnywhere(PowerViewShadeWithTiltBase):
    """Representation of a PowerView shade with tilt anywhere capabilities.

    API Class: ShadeBottomUpTiltAnywhere, ShadeVerticalTiltAnywhere

    Type 2 - Bottom Up w/ 180° Tilt
    Type 4 - Vertical (Traversing) w/ 180° Tilt
    """

    @callback
    def _get_shade_move(self, target_hass_position: int) -> ShadePosition:
        """Return a ShadePosition."""
        return ShadePosition(
            primary=target_hass_position,
            tilt=self.positions.tilt,
            velocity=self.positions.velocity,
        )

    @callback
    def _get_shade_tilt(self, target_hass_tilt_position: int) -> ShadePosition:
        """Return a ShadePosition."""
        return ShadePosition(
            primary=self.positions.primary,
            tilt=target_hass_tilt_position,
            velocity=self.positions.velocity,
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
        if self._shade.is_supported(MOTION_STOP):
            self._attr_supported_features |= CoverEntityFeature.STOP_TILT
        self._max_tilt = self._shade.shade_limits.tilt_max

    @property
    def current_cover_position(self) -> int:
        """Return the current position of cover."""
        # allows using parent class with no other alterations
        return CLOSED_POSITION

    @property
    def transition_steps(self) -> int:
        """Return the steps to make a move."""
        return self.positions.tilt

    @property
    def is_closed(self) -> bool:
        """Return if the cover is closed."""
        return self.positions.tilt <= CLOSED_POSITION


class PowerViewShadeTopDown(PowerViewShadeBase):
    """Representation of a shade that lowers from the roof to the floor.

    These shades are inverted where MAX_POSITION equates to closed and MIN_POSITION is open
    API Class: ShadeTopDown

    Type 6 - Top Down
    """

    _attr_name = None

    @property
    def current_cover_position(self) -> int:
        """Return the current position of cover."""
        # inverted positioning
        return MAX_POSITION - self.positions.primary

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the shade to a specific position."""
        await self._async_set_cover_position(MAX_POSITION - kwargs[ATTR_POSITION])

    @property
    def is_closed(self) -> bool:
        """Return if the cover is closed."""
        return (MAX_POSITION - self.positions.primary) <= CLOSED_POSITION


class PowerViewShadeDualRailBase(PowerViewShadeBase):
    """Representation of a shade with top/down bottom/up capabilities.

    Base methods shared between the two shades created
    Child Classes: PowerViewShadeTDBUBottom / PowerViewShadeTDBUTop
    API Class: ShadeTopDownBottomUp
    """

    @property
    def transition_steps(self) -> int:
        """Return the steps to make a move."""
        return self.positions.primary + self.positions.secondary


class PowerViewShadeTDBUBottom(PowerViewShadeDualRailBase):
    """Representation of the bottom PowerViewShadeDualRailBase shade.

    These shades have top/down bottom up functionality and two entities.
    Sibling Class: PowerViewShadeTDBUTop
    API Class: ShadeTopDownBottomUp
    """

    _attr_translation_key = "bottom"

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
        self._attr_unique_id = f"{self._attr_unique_id}_bottom"

    @callback
    def _clamp_cover_limit(self, target_hass_position: int) -> int:
        """Don't allow a cover to go into an impossbile position."""
        return min(target_hass_position, (MAX_POSITION - self.positions.secondary))

    @callback
    def _get_shade_move(self, target_hass_position: int) -> ShadePosition:
        """Return a ShadePosition."""
        return ShadePosition(
            primary=target_hass_position,
            secondary=self.positions.secondary,
            velocity=self.positions.velocity,
        )


class PowerViewShadeTDBUTop(PowerViewShadeDualRailBase):
    """Representation of the top PowerViewShadeDualRailBase shade.

    These shades have top/down bottom up functionality and two entities.
    Sibling Class: PowerViewShadeTDBUBottom
    API Class: ShadeTopDownBottomUp
    """

    _attr_translation_key = "top"

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
        self._attr_unique_id = f"{self._attr_unique_id}_top"

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
        return self.positions.secondary

    @property
    def open_position(self) -> ShadePosition:
        """Return the open position and required additional positions."""
        # these shades share a class in parent API
        # override open position for top shade
        return ShadePosition(
            primary=MIN_POSITION,
            secondary=MAX_POSITION,
            velocity=self.positions.velocity,
        )

    @callback
    def _clamp_cover_limit(self, target_hass_position: int) -> int:
        """Don't allow a cover to go into an impossbile position."""
        return min(target_hass_position, (MAX_POSITION - self.positions.primary))

    @callback
    def _get_shade_move(self, target_hass_position: int) -> ShadePosition:
        """Return a ShadePosition."""
        return ShadePosition(
            primary=self.positions.primary,
            secondary=target_hass_position,
            velocity=self.positions.velocity,
        )


class PowerViewShadeDualOverlappedBase(PowerViewShadeBase):
    """Represent a shade that has a front sheer and rear opaque panel.

    This equates to two shades being controlled by one motor
    """

    @property
    def transition_steps(self) -> int:
        """Return the steps to make a move."""
        # poskind 1 represents the second half of the shade in hass
        # front must be fully closed before rear can move
        # 51 - 100 is equiv to 1-100 on other shades - one motor, two shades
        primary = (self.positions.primary / 2) + 50
        # poskind 2 represents the shade first half of the shade in hass
        # rear (opaque) must be fully open before front can move
        # 51 - 100 is equiv to 1-100 on other shades - one motor, two shades
        secondary = self.positions.secondary / 2
        return ceil(primary + secondary)

    @property
    def open_position(self) -> ShadePosition:
        """Return the open position and required additional positions."""
        return ShadePosition(
            primary=MAX_POSITION,
            velocity=self.positions.velocity,
        )

    @property
    def close_position(self) -> ShadePosition:
        """Return the open position and required additional positions."""
        return ShadePosition(
            secondary=MIN_POSITION,
            velocity=self.positions.velocity,
        )


class PowerViewShadeDualOverlappedCombined(PowerViewShadeDualOverlappedBase):
    """Represent a shade that has a front sheer and rear opaque panel.

    This equates to two shades being controlled by one motor.
    The front shade must be completely down before the rear shade will move.
    Sibling Class: PowerViewShadeDualOverlappedFront, PowerViewShadeDualOverlappedRear
    API Class: ShadeDualOverlapped

    Type 8 - Duolite (front and rear shades)
    """

    _attr_translation_key = "combined"

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
        self._attr_unique_id = f"{self._attr_unique_id}_combined"

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
        position = (self.positions.primary / 2) + 50
        if self.positions.primary == MIN_POSITION:
            position = self.positions.secondary / 2

        return ceil(position)

    @callback
    def _get_shade_move(self, target_hass_position: int) -> ShadePosition:
        """Return a ShadePosition."""
        # 0 - 50 represents the rear blockut shade
        if target_hass_position <= 50:
            target_hass_position = target_hass_position * 2
            return ShadePosition(
                secondary=target_hass_position,
                velocity=self.positions.velocity,
            )

        # 51 <= target_hass_position <= 100 (51-100 represents front sheer shade)
        target_hass_position = (target_hass_position - 50) * 2
        return ShadePosition(
            primary=target_hass_position,
            velocity=self.positions.velocity,
        )


class PowerViewShadeDualOverlappedFront(PowerViewShadeDualOverlappedBase):
    """Represent the shade front panel - These have an opaque panel too.

    This equates to two shades being controlled by one motor.
    The front shade must be completely down before the rear shade will move.
    Sibling Class:
        PowerViewShadeDualOverlappedCombined, PowerViewShadeDualOverlappedRear
    API Class:
        ShadeDualOverlapped + ShadeDualOverlappedTilt90 + ShadeDualOverlappedTilt180

    Type 8 - Duolite (front and rear shades)
    Type 9 - Duolite with 90° Tilt (front bottom up shade that also tilts
             plus a rear opaque (non-tilting) shade)
    Type 10 - Duolite with 180° Tilt
    """

    _attr_translation_key = "front"

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
        self._attr_unique_id = f"{self._attr_unique_id}_front"

    @property
    def should_poll(self) -> bool:
        """Certain shades create multiple entities.

        Do not poll shade multiple times. Combined shade will return data
        and multiple polling will cause timeouts.
        """
        return False

    @callback
    def _get_shade_move(self, target_hass_position: int) -> ShadePosition:
        """Return a ShadePosition."""
        return ShadePosition(
            primary=target_hass_position,
            velocity=self.positions.velocity,
        )

    @property
    def close_position(self) -> ShadePosition:
        """Return the close position and required additional positions."""
        return ShadePosition(
            primary=MIN_POSITION,
            velocity=self.positions.velocity,
        )


class PowerViewShadeDualOverlappedRear(PowerViewShadeDualOverlappedBase):
    """Represent the shade front panel - These have an opaque panel too.

    This equates to two shades being controlled by one motor.
    The front shade must be completely down before the rear shade will move.
    Sibling Class:
        PowerViewShadeDualOverlappedCombined, PowerViewShadeDualOverlappedFront
    API Class:
        ShadeDualOverlapped + ShadeDualOverlappedTilt90 + ShadeDualOverlappedTilt180

    Type 8 - Duolite (front and rear shades)
    Type 9 - Duolite with 90° Tilt (front bottom up shade that also tilts plus
             a rear opaque (non-tilting) shade)
    Type 10 - Duolite with 180° Tilt
    """

    _attr_translation_key = "rear"

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
        self._attr_unique_id = f"{self._attr_unique_id}_rear"

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
        return self.positions.secondary

    @callback
    def _get_shade_move(self, target_hass_position: int) -> ShadePosition:
        """Return a ShadePosition."""
        return ShadePosition(
            secondary=target_hass_position,
            velocity=self.positions.velocity,
        )

    @property
    def open_position(self) -> ShadePosition:
        """Return the open position and required additional positions."""
        return ShadePosition(
            secondary=MAX_POSITION,
            velocity=self.positions.velocity,
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
        if self._shade.is_supported(MOTION_STOP):
            self._attr_supported_features |= CoverEntityFeature.STOP_TILT
        self._max_tilt = self._shade.shade_limits.tilt_max

    @property
    def transition_steps(self) -> int:
        """Return the steps to make a move."""
        # poskind 1 represents the second half of the shade in hass
        # front must be fully closed before rear can move
        # 51 - 100 is equiv to 1-100 on other shades - one motor, two shades
        primary = (self.positions.primary / 2) + 50
        # poskind 2 represents the shade first half of the shade in hass
        # rear (opaque) must be fully open before front can move
        # 51 - 100 is equiv to 1-100 on other shades - one motor, two shades
        secondary = self.positions.secondary / 2
        tilt = self.positions.tilt
        return ceil(primary + secondary + tilt)

    @callback
    def _get_shade_tilt(self, target_hass_tilt_position: int) -> ShadePosition:
        """Return a ShadePosition."""
        return ShadePosition(
            tilt=target_hass_tilt_position,
            velocity=self.positions.velocity,
        )

    @property
    def open_tilt_position(self) -> ShadePosition:
        """Return the open tilt position and required additional positions."""
        return replace(self._shade.open_position_tilt, velocity=self.positions.velocity)

    @property
    def close_tilt_position(self) -> ShadePosition:
        """Return the open tilt position and required additional positions."""
        return replace(
            self._shade.close_position_tilt, velocity=self.positions.velocity
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
    11: (
        PowerViewShadeDualOverlappedCombined,
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
        "%s %s (%s) detected as %a %s",
        room_name,
        shade.name,
        shade.capability.type,
        classes,
        shade.raw_data,
    )
    return [
        cls(coordinator, device_info, room_name, shade, name_before_refresh)
        for cls in classes
    ]
