"""Platform for cover integration."""

from typing import Any

from boschshcpy import (
    SHCSession,
    SHCShutterControl,
    SHCMicromoduleShutterControl,
)

from homeassistant.components.cover import (
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    CoverEntityFeature,
    CoverDeviceClass,
    CoverEntity,
)
from homeassistant.const import Platform
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_SESSION, DOMAIN, LOGGER
from .entity import SHCEntity, async_migrate_to_new_unique_id, device_excluded

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the SHC cover platform."""
    entities = []
    session: SHCSession = hass.data[DOMAIN][config_entry.entry_id][DATA_SESSION]

    for cover in (
        session.device_helper.shutter_controls
        + session.device_helper.micromodule_shutter_controls
    ):
        if device_excluded(cover, config_entry.options):
            continue
        await async_migrate_to_new_unique_id(hass, Platform.COVER, device=cover)
        entities.append(
            ShutterControlCover(
                device=cover,
                entry_id=config_entry.entry_id,
            )
        )

    for blind in session.device_helper.micromodule_blinds:
        if device_excluded(blind, config_entry.options):
            continue
        await async_migrate_to_new_unique_id(hass, Platform.COVER, device=blind)
        entities.append(
            BlindsControlCover(
                device=blind,
                entry_id=config_entry.entry_id,
            )
        )

    if entities:
        async_add_entities(entities)


class ShutterControlCover(SHCEntity, CoverEntity):
    """Representation of a SHC shutter control device.

    Issue #183 (resolved): State stops refreshing after hours was caused by
    boschshcpy's long-polling loop not pushing a fresh state snapshot after
    re-subscribing on poll-ID invalidation (JSONRPCError -32001).  The lib
    now calls short_poll() on each service immediately after re-subscription,
    so callbacks are delivered and state is restored without HA-side polling.
    """

    _attr_supported_features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.STOP
        | CoverEntityFeature.SET_POSITION
    )

    _current_operation_state = None
    _target_position = None
    _last_position = None
    _skip_update = False
    _app_command = False

    def _micromodule_keypad_switch_off(self) -> None:
        if self._device.device_model == "MICROMODULE_SHUTTER":
            # Some MICROMODULE_SHUTTER devices expose no Keypad service (no
            # physical wall switch wired). On the released lib the eventtype
            # setter then dereferences a None keypad service and open/close/
            # stop crash with "'NoneType' object has no attribute 'eventType'"
            # (issue #318). eventType is only local bookkeeping for the
            # physical-switch direction logic, so skipping it is safe.
            if getattr(self._device, "_keypad_service", None) is None:
                return
            # Stopping a micromodule shutter requires setting the eventtype to SWITCH_OFF, in case the manual switch was not put to off position
            self._device.eventtype = (
                SHCMicromoduleShutterControl.KeypadService.KeyEvent.SWITCH_OFF
            )

    def _update_attr(self) -> None:
        """Recomputes the attributes values either at init or when the device state changes."""
        self._attr_current_cover_position = self.current_cover_position
        self._current_operation_state = self._device.operation_state

        if (
            self._current_operation_state
            == SHCShutterControl.ShutterControlService.State.STOPPED
        ):
            self._attr_is_closing = False
            self._attr_is_opening = False
            if not self._skip_update:
                # Refresh the reference position on every rest for level-based
                # devices, so the next movement's direction is computed against the
                # actual resting position. This must include physical-switch moves
                # of MICROMODULE shutters/blinds: their Keypad events arrive as
                # PRESS_SHORT (not SWITCH_ON), so they never hit the keycode
                # direction branch below and rely on this reference (issue #294).
                if (
                    self._device.device_model
                    in ("BBL", "MICROMODULE_SHUTTER", "MICROMODULE_BLINDS")
                    or self._app_command
                ):
                    self._last_position = self.current_cover_position
                    self._app_command = False
            else:
                # In case of HA commands, the first STOPPED state is not reliable, so we skip it and reset the flag for the next update
                self._skip_update = False

            # Initialize the last position for MM at start
            if self._last_position is None:
                self._last_position = self.current_cover_position

        if (
            self._current_operation_state
            == SHCShutterControl.ShutterControlService.State.MOVING
        ):
            if self._device.device_model == "BBL":
                self._target_position = round(self._device.level * 100.0)
                if self._last_position is not None:
                    if self._target_position > self._last_position:
                        self._attr_is_closing = False
                        self._attr_is_opening = True
                    elif self._target_position < self._last_position:
                        self._attr_is_closing = True
                        self._attr_is_opening = False
            elif self._device.device_model == "MICROMODULE_SHUTTER":
                if (
                    self._device.eventtype
                    == SHCMicromoduleShutterControl.KeypadService.KeyEvent.SWITCH_ON
                    and self._device.keycode == 1
                ):
                    # When the event is triggered by the physical switch, we can determine the movement direction based on the keycode (1 for open, 2 for close), as the level attribute is not reliable during movement
                    self._last_position = round(self._device.level * 100.0)
                    self._attr_is_closing = False
                    self._attr_is_opening = True
                    self._target_position = 100
                elif (
                    self._device.eventtype
                    == SHCMicromoduleShutterControl.KeypadService.KeyEvent.SWITCH_ON
                    and self._device.keycode == 2
                ):
                    self._last_position = round(self._device.level * 100.0)
                    self._attr_is_closing = True
                    self._attr_is_opening = False
                    self._target_position = 0
                else:
                    self._target_position = round(self._device.level * 100.0)
                    if self._last_position is not None:
                        if self._target_position > self._last_position:
                            self._attr_is_closing = False
                            self._attr_is_opening = True
                        elif self._target_position < self._last_position:
                            self._attr_is_closing = True
                            self._attr_is_opening = False

            elif self._device.device_model == "MICROMODULE_BLINDS":
                self._target_position = round(self._device.level * 100.0)
                if self._last_position is not None:
                    if self._target_position > self._last_position:
                        self._attr_is_closing = False
                        self._attr_is_opening = True
                    elif self._target_position < self._last_position:
                        self._attr_is_closing = True
                        self._attr_is_opening = False

            else:
                # for other devices, we cannot determine the movement direction, so we set both to None
                LOGGER.debug("Cannot determine movement direction for %s", self._device.name)
                self._attr_is_closing = None
                self._attr_is_opening = None

        # Shutter Control II devices (MICROMODULE_BLINDS / MICROMODULE_SHUTTER)
        # report the movement direction DIRECTLY via operationState — the Bosch
        # spec enum is [STOPPED, OPENING, CLOSING] and they never emit MOVING
        # (Shutter-II-local-openapi-v3.yml). The STOPPED/MOVING branches above
        # therefore never matched these states, so physical-switch and Bosch-app
        # moves left is_opening/is_closing unset while HA-initiated moves (which
        # set the flags directly in open_cover/close_cover) looked correct — the
        # exact direction symptom in issue #100. We set ONLY the direction flags
        # here: it is purely additive (handles states that previously fell
        # through) and deliberately does not touch _target_position, so the
        # position-during-move display is unchanged for all models.
        if (
            self._current_operation_state
            == SHCShutterControl.ShutterControlService.State.OPENING
        ):
            self._attr_is_opening = True
            self._attr_is_closing = False

        if (
            self._current_operation_state
            == SHCShutterControl.ShutterControlService.State.CLOSING
        ):
            self._attr_is_closing = True
            self._attr_is_opening = False

    @property
    def device_class(self) -> CoverDeviceClass | None:
        return (
            CoverDeviceClass.AWNING
            if self._device.device_model == "MICROMODULE_AWNING"
            else CoverDeviceClass.SHUTTER
        )

    @property
    def current_cover_position(self):
        """Return the current or target cover position."""
        if self._device.device_model == "MICROMODULE_SHUTTER":
            if (
                self._device.operation_state
                == SHCShutterControl.ShutterControlService.State.STOPPED
            ):
                return round(self._device.level * 100.0)
            # MOVING: use target if set, else fall back to current level reading
            if self._target_position is not None:
                return self._target_position
            return round(self._device.level * 100.0)
        else:
            # for BBL devices, we can rely on the level attribute to determine the current position, even when moving
            return round(self._device.level * 100.0)

    async def async_stop_cover(self, **kwargs):
        """Stop the cover."""
        self._micromodule_keypad_switch_off()
        self._attr_is_opening = False
        self._attr_is_closing = False
        await self._device.async_stop()
        self._skip_update = True
        self._app_command = True

    @property
    def is_closed(self):
        """Return if the cover is closed or not."""
        return (
            self._device.operation_state
            == SHCShutterControl.ShutterControlService.State.STOPPED
            and self._device.level == 0.0
        )

    async def async_open_cover(self, **kwargs):
        """Open the cover."""
        self._micromodule_keypad_switch_off()
        self._attr_is_opening = True
        await self._device.async_set_level(1.0)
        self._target_position = 100
        self._skip_update = True
        self._app_command = True

    async def async_close_cover(self, **kwargs):
        """Close cover."""
        self._micromodule_keypad_switch_off()
        self._attr_is_closing = True
        await self._device.async_set_level(0.0)
        self._target_position = 0
        self._skip_update = True
        self._app_command = True

    async def async_set_cover_position(self, **kwargs):
        """Move the cover to a specific position."""
        if self._device.device_model == "MICROMODULE_SHUTTER":
            self._micromodule_keypad_switch_off()
            self._last_position = self.current_cover_position
        position = kwargs[ATTR_POSITION]
        self._target_position = position
        await self._device.async_set_level(position / 100.0)
        self._skip_update = True
        self._app_command = True

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {
            "operation_state": self._device.operation_state,
        }


class BlindsControlCover(ShutterControlCover, CoverEntity):
    """Representation of a SHC blinds cover device."""

    _attr_device_class = CoverDeviceClass.BLIND
    _attr_supported_features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.CLOSE_TILT
        | CoverEntityFeature.OPEN_TILT
        | CoverEntityFeature.SET_TILT_POSITION
        | CoverEntityFeature.SET_POSITION
        | CoverEntityFeature.STOP
        | CoverEntityFeature.STOP_TILT
    )

    async def async_open_cover(self, **kwargs):
        """Open the cover (lift) via ShutterControl.level."""
        self._attr_is_opening = True
        self._attr_is_closing = False
        await self._device.async_set_level(1.0)
        self._target_position = 100
        self._skip_update = True
        self._app_command = True

    async def async_close_cover(self, **kwargs):
        """Close cover (lift) via ShutterControl.level."""
        self._attr_is_closing = True
        self._attr_is_opening = False
        await self._device.async_set_level(0.0)
        self._target_position = 0
        self._skip_update = True
        self._app_command = True

    async def async_set_cover_position(self, **kwargs):
        """Move the cover (lift) to a specific position via ShutterControl.level."""
        position = kwargs[ATTR_POSITION]
        await self._device.async_set_level(position / 100.0)
        self._target_position = position
        self._skip_update = True
        self._app_command = True

    @property
    def current_cover_position(self):
        """Return the current cover (lift) position from ShutterControl.level.

        Issue #100 ("fully up shows 0%", reporter-confirmed on a DEGREE_180
        MICROMODULE_BLINDS, dev 6c5cb1…): venetian blinds expose THREE services
        - ShutterControl (level = the live lift, 1=up/open .. 0=down/closed),
          operationState only ever STOPPED/MOVING (never directional);
        - BlindsControl (currentAngle = slat tilt); and
        - BlindsSceneControl (level/angle = the last *scene* values, not the
          live lift).
        The previous code read the lift from blinds_level
        (BlindsSceneControl.level), which on this device sat at 0.0 while the
        blind was fully up -> HA showed 0% for a fully-open blind. The authori-
        tative lift is ShutterControl.level (inherited self._device.level), the
        same source the parent ShutterControlCover uses for non-
        MICROMODULE_SHUTTER models, so this also matches the BBL mapping. Tilt
        stays on BlindsControl (see current_cover_tilt_position).
        """
        return round(self._device.level * 100.0)

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover using the blind-specific stop endpoint."""
        self._attr_is_opening = False
        self._attr_is_closing = False
        await self._device.async_stop_blinds()
        self._skip_update = True
        self._app_command = True

    async def async_stop_cover_tilt(self, **kwargs: Any) -> None:
        await self._device.async_stop_blinds()

    @property
    def current_cover_tilt_position(self):
        """Return the current cover tilt position."""
        return round((1.0 - self._device.current_angle) * 100.0)

    async def async_open_cover_tilt(self, **kwargs):
        """Open the cover tilt."""
        await self._device.async_set_target_angle(1.0 - 1.0)

    async def async_close_cover_tilt(self, **kwargs):
        """Close cover tilt."""
        await self._device.async_set_target_angle(1.0 - 0.0)

    async def async_set_cover_tilt_position(self, **kwargs):
        """Move the cover tilt to a specific position."""
        tilt_position = kwargs[ATTR_TILT_POSITION]
        await self._device.async_set_target_angle(1.0 - (tilt_position / 100.0))
