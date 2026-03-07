"""Support for the Switchbot BlindTilt, Curtain, Curtain3, RollerShade as Cover."""

import asyncio
from datetime import timedelta
import logging
from typing import Any

from switchbot_api import (
    BlindTiltCommands,
    CommonCommands,
    CurtainCommands,
    Device,
    Remote,
    RollerShadeCommands,
    SwitchBotAPI,
)

from homeassistant.components.cover import (
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.update_coordinator import UpdateFailed
import homeassistant.util.dt as dt_util

from . import SwitchbotCloudData, SwitchBotCoordinator
from .const import COVER_ENTITY_AFTER_COMMAND_REFRESH, COVER_ENTITY_POLL_TIMEOUT, DOMAIN
from .entity import SwitchBotCloudEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up SwitchBot Cloud entry."""
    data: SwitchbotCloudData = hass.data[DOMAIN][config.entry_id]
    async_add_entities(
        _async_make_entity(data.api, device, coordinator)
        for device, coordinator in data.devices.covers
    )


class SwitchBotCloudCover(SwitchBotCloudEntity, CoverEntity):
    """Representation of a SwitchBot Cover."""

    _attr_name = None
    _attr_is_closed: bool | None = None

    def _set_attributes(self) -> None:
        if self.coordinator.data is None:
            return
        position: int | None = self.coordinator.data.get("slidePosition")
        if position is None:
            return
        self._attr_current_cover_position = 100 - position
        self._attr_current_cover_tilt_position = 100 - position
        self._attr_is_closed = position == 100

    async def _async_poll_until_stopped(self) -> None:
        """Poll the API until the device reports it has stopped moving."""
        elapsed = 0
        while elapsed < COVER_ENTITY_POLL_TIMEOUT:
            done = asyncio.Event()

            @callback
            def _set_done(_now: Any, _e: asyncio.Event = done) -> None:
                _e.set()

            fire_at = dt_util.utcnow() + timedelta(
                seconds=COVER_ENTITY_AFTER_COMMAND_REFRESH
            )
            cancel_timer = async_track_point_in_utc_time(
                self.hass,
                _set_done,
                fire_at,
            )
            try:
                await done.wait()
            except asyncio.CancelledError:
                cancel_timer()
                raise
            elapsed += COVER_ENTITY_AFTER_COMMAND_REFRESH
            try:
                await self.coordinator.async_refresh()
            except UpdateFailed as err:
                _LOGGER.warning("Error refreshing cover state during polling: %s", err)
                self._async_on_poll_stopped()
                return
            if not (self.coordinator.data or {}).get("moving", True):
                break
        self._async_on_poll_stopped()

    @callback
    def _async_on_poll_stopped(self) -> None:
        """Called when polling has determined the device has stopped moving."""


class SwitchBotCloudCoverCurtain(SwitchBotCloudCover):
    """Representation of a SwitchBot Curtain & Curtain3."""

    _attr_device_class = CoverDeviceClass.CURTAIN
    _attr_supported_features: CoverEntityFeature = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.STOP
        | CoverEntityFeature.SET_POSITION
    )

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        await self.send_api_command(CommonCommands.ON)
        await asyncio.sleep(COVER_ENTITY_AFTER_COMMAND_REFRESH)
        await self.coordinator.async_request_refresh()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        await self.send_api_command(CommonCommands.OFF)
        await asyncio.sleep(COVER_ENTITY_AFTER_COMMAND_REFRESH)
        await self.coordinator.async_request_refresh()

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        position: int | None = kwargs.get("position")
        if position is not None:
            await self.send_api_command(
                CurtainCommands.SET_POSITION,
                parameters=f"{0},ff,{100 - position}",
            )
            await asyncio.sleep(COVER_ENTITY_AFTER_COMMAND_REFRESH)
            await self.coordinator.async_request_refresh()

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        await self.send_api_command(CurtainCommands.PAUSE)
        await self.coordinator.async_request_refresh()


class SwitchBotCloudCoverRollerShade(SwitchBotCloudCover):
    """Representation of a SwitchBot RollerShade."""

    _attr_device_class = CoverDeviceClass.SHADE
    _attr_supported_features: CoverEntityFeature = (
        CoverEntityFeature.SET_POSITION
        | CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
    )

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        await self.send_api_command(RollerShadeCommands.SET_POSITION, parameters=0)
        await asyncio.sleep(COVER_ENTITY_AFTER_COMMAND_REFRESH)
        await self.coordinator.async_request_refresh()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        await self.send_api_command(RollerShadeCommands.SET_POSITION, parameters=100)
        await asyncio.sleep(COVER_ENTITY_AFTER_COMMAND_REFRESH)
        await self.coordinator.async_request_refresh()

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        position: int | None = kwargs.get("position")
        if position is not None:
            await self.send_api_command(
                RollerShadeCommands.SET_POSITION, parameters=(100 - position)
            )
            await asyncio.sleep(COVER_ENTITY_AFTER_COMMAND_REFRESH)
            await self.coordinator.async_request_refresh()


class SwitchBotCloudCoverBlindTilt(SwitchBotCloudCover):
    """Representation of a SwitchBot Blind Tilt."""

    _attr_direction: str | None = None
    _attr_device_class = CoverDeviceClass.BLIND
    CLOSED_UP_THRESHOLD = 80
    CLOSED_DOWN_THRESHOLD = 20
    POSITION_TOLERANCE = 3
    _attr_supported_features: CoverEntityFeature = (
        CoverEntityFeature.SET_TILT_POSITION
        | CoverEntityFeature.OPEN_TILT
        | CoverEntityFeature.CLOSE_TILT
    )
    _command_in_flight: bool = False
    _target_tilt_position: int | None = None
    _poll_task: asyncio.Task | None = None

    def _set_attributes(self) -> None:
        if self.coordinator.data is None:
            return
        position: int | None = self.coordinator.data.get("slidePosition")
        if position is None:
            return
        direction = self.coordinator.data.get("direction")
        self._attr_direction = direction.lower() if direction else None
        # slidePosition uses the same physical scale as the BT library:
        # 0=closed down, 50=horizontal/open, 100=closed up. Pass through directly.
        self._attr_current_cover_tilt_position = position
        # While a command is in flight, don't touch is_closed or the opening/closing
        # flags — the command methods set them immediately and _async_on_poll_stopped
        # clears them once movement is confirmed done.
        if self._command_in_flight:
            # Fallback: if the position has reached the target, finalize
            # immediately without waiting for the poll loop to finish.
            if self._target_tilt_position is not None and self._position_reached_target(
                position
            ):
                if self._poll_task and not self._poll_task.done():
                    self._poll_task.cancel()
                    self._poll_task = None
                self._async_on_poll_stopped()
        else:
            self._attr_is_opening = False
            self._attr_is_closing = False
            self._attr_is_closed = (position < self.CLOSED_DOWN_THRESHOLD) or (
                position > self.CLOSED_UP_THRESHOLD
            )

    def _start_poll_task(self) -> None:
        """Cancel any existing poll task and start a new one."""
        if self._poll_task and not self._poll_task.done():
            self._poll_task.cancel()
        self._poll_task = self.hass.async_create_background_task(
            self._async_poll_until_stopped(), "switchbot_cloud blind tilt poll"
        )

    async def async_will_remove_from_hass(self) -> None:
        """Cancel poll task when entity is removed."""
        if self._poll_task and not self._poll_task.done():
            self._poll_task.cancel()

    def _position_reached_target(self, position: int) -> bool:
        """Return True if position has reached the target."""
        target = self._target_tilt_position
        assert target is not None
        if target >= self.CLOSED_UP_THRESHOLD:
            # Closing up: done when position is in the closed-up zone
            return position >= self.CLOSED_UP_THRESHOLD
        if target <= self.CLOSED_DOWN_THRESHOLD:
            # Closing down: done when position is in the closed-down zone
            return position <= self.CLOSED_DOWN_THRESHOLD
        # Intermediate target (open zone): use absolute tolerance so that
        # e.g. target=60 is not considered reached when position is only 25.
        return abs(position - target) <= self.POSITION_TOLERANCE

    @callback
    def _async_on_poll_stopped(self) -> None:
        """Finalize state once movement is confirmed done."""
        self._command_in_flight = False
        self._target_tilt_position = None
        self._attr_is_opening = False
        self._attr_is_closing = False
        if self._attr_current_cover_tilt_position is not None:
            pos = self._attr_current_cover_tilt_position
            self._attr_is_closed = (
                pos < self.CLOSED_DOWN_THRESHOLD or pos > self.CLOSED_UP_THRESHOLD
            )
        self.async_write_ha_state()

    async def async_set_cover_tilt_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        tilt_position: int | None = kwargs.get("tilt_position")
        if tilt_position is not None:
            # setPosition uses a direction-relative scale where 0=closed end and
            # 100=horizontal/open, per direction. Derive direction from the target:
            # positions > 50 tilt up, positions < 50 tilt down, 50 uses "up".
            # Convert physical position to per-direction command position:
            #   up:   cmd = (100 - physical) * 2  (physical 100→0, physical 50→100)
            #   down: cmd = physical * 2           (physical 0→0, physical 50→100)
            if tilt_position >= 50:
                direction = "up"
                cmd_position = (100 - tilt_position) * 2
            else:
                direction = "down"
                cmd_position = tilt_position * 2
            await self.send_api_command(
                BlindTiltCommands.SET_POSITION,
                parameters=f"{direction};{cmd_position}",
            )
            current = self._attr_current_cover_tilt_position
            # Opening means moving toward 50 (horizontal/open center).
            # Compare distance to 50 to determine direction.
            if current is None or abs(tilt_position - 50) < abs(current - 50):
                self._attr_is_opening = True
                self._attr_is_closing = False
            else:
                self._attr_is_closing = True
                self._attr_is_opening = False
            self._command_in_flight = True
            self._target_tilt_position = tilt_position
            self.async_write_ha_state()
            self._start_poll_task()

    async def async_open_cover_tilt(self, **kwargs: Any) -> None:
        """Open the cover."""
        await self.send_api_command(BlindTiltCommands.FULLY_OPEN)
        self._attr_is_opening = True
        self._attr_is_closing = False
        self._command_in_flight = True
        self._target_tilt_position = 50
        self.async_write_ha_state()
        self._start_poll_task()

    async def async_close_cover_tilt(self, **kwargs: Any) -> None:
        """Close the cover."""
        if self._attr_direction is None:
            raise HomeAssistantError(
                "Cannot close cover tilt: direction is not yet known"
            )
        if "up" in self._attr_direction:
            await self.send_api_command(BlindTiltCommands.CLOSE_UP)
            self._target_tilt_position = 100
        else:
            await self.send_api_command(BlindTiltCommands.CLOSE_DOWN)
            self._target_tilt_position = 0
        self._attr_is_closing = True
        self._attr_is_opening = False
        self._command_in_flight = True
        self.async_write_ha_state()
        self._start_poll_task()


class SwitchBotCloudCoverGarageDoorOpener(SwitchBotCloudCover):
    """Representation of a SwitchBot Garage Door Opener."""

    _attr_device_class = CoverDeviceClass.GARAGE
    _attr_supported_features: CoverEntityFeature = (
        CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE
    )

    def _set_attributes(self) -> None:
        if self.coordinator.data is None:
            return
        door_status: int | None = self.coordinator.data.get("doorStatus")
        self._attr_is_closed = None if door_status is None else door_status == 1

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        await self.send_api_command(CommonCommands.ON)
        await asyncio.sleep(COVER_ENTITY_AFTER_COMMAND_REFRESH)
        await self.coordinator.async_request_refresh()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        await self.send_api_command(CommonCommands.OFF)
        await asyncio.sleep(COVER_ENTITY_AFTER_COMMAND_REFRESH)
        await self.coordinator.async_request_refresh()


@callback
def _async_make_entity(
    api: SwitchBotAPI, device: Device | Remote, coordinator: SwitchBotCoordinator
) -> (
    SwitchBotCloudCoverBlindTilt
    | SwitchBotCloudCoverRollerShade
    | SwitchBotCloudCoverCurtain
    | SwitchBotCloudCoverGarageDoorOpener
):
    """Make a SwitchBotCloudCover device."""
    if device.device_type == "Blind Tilt":
        return SwitchBotCloudCoverBlindTilt(api, device, coordinator)
    if device.device_type == "Roller Shade":
        return SwitchBotCloudCoverRollerShade(api, device, coordinator)
    if device.device_type == "Garage Door Opener":
        return SwitchBotCloudCoverGarageDoorOpener(api, device, coordinator)
    return SwitchBotCloudCoverCurtain(api, device, coordinator)
