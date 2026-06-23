"""Platform for cover integration."""

from typing import Any

from boschshcpy import SHCMicromoduleShutterControl, SHCShutterControl

from homeassistant.components.cover import (
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import LOGGER
from .entity import SHCEntity, async_migrate_to_new_unique_id, device_excluded

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the SHC cover platform."""
    entities = []
    session = config_entry.runtime_data.session

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

    The authoritative lift position is ShutterControl.level (range 0.0-1.0).
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
                # Refresh the reference position on every rest so the next
                # movement's direction is computed against the actual resting
                # position. Physical-switch moves on MICROMODULE devices arrive
                # as PRESS_SHORT and rely on this reference rather than the
                # keycode branch below.
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
                    # Physical switch: keycode 1 = open, 2 = close; level is unreliable during movement.
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
                LOGGER.debug(
                    "Cannot determine movement direction for %s", self._device.name
                )
                self._attr_is_closing = None
                self._attr_is_opening = None

        # Some devices report movement direction directly via OPENING/CLOSING
        # operationState (never MOVING). Update direction flags only; do not
        # touch _target_position so position-during-move display is unchanged.
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
        """Return the device class based on the model type."""
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
        # for BBL devices, we can rely on the level attribute to determine the current position, even when moving
        return round(self._device.level * 100.0)

    async def async_stop_cover(self, **kwargs: Any) -> None:
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

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        self._micromodule_keypad_switch_off()
        self._attr_is_opening = True
        await self._device.async_set_level(1.0)
        self._target_position = 100
        self._skip_update = True
        self._app_command = True

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close cover."""
        self._micromodule_keypad_switch_off()
        self._attr_is_closing = True
        await self._device.async_set_level(0.0)
        self._target_position = 0
        self._skip_update = True
        self._app_command = True

    async def async_set_cover_position(self, **kwargs: Any) -> None:
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
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes."""
        return {
            "operation_state": self._device.operation_state,
        }


class BlindsControlCover(ShutterControlCover, CoverEntity):
    """Representation of a SHC blinds cover device."""

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

    @property
    def device_class(self) -> CoverDeviceClass | None:
        """Return the device class for blinds."""
        return CoverDeviceClass.BLIND

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover (lift) via ShutterControl.level."""
        self._attr_is_opening = True
        self._attr_is_closing = False
        await self._device.async_set_level(1.0)
        self._target_position = 100
        self._skip_update = True
        self._app_command = True

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close cover (lift) via ShutterControl.level."""
        self._attr_is_closing = True
        self._attr_is_opening = False
        await self._device.async_set_level(0.0)
        self._target_position = 0
        self._skip_update = True
        self._app_command = True

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover (lift) to a specific position via ShutterControl.level."""
        position = kwargs[ATTR_POSITION]
        await self._device.async_set_level(position / 100.0)
        self._target_position = position
        self._skip_update = True
        self._app_command = True

    @property
    def current_cover_position(self):
        """Return the current cover (lift) position from ShutterControl.level."""
        return round(self._device.level * 100.0)

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover using the blind-specific stop endpoint."""
        self._attr_is_opening = False
        self._attr_is_closing = False
        await self._device.async_stop_blinds()
        self._skip_update = True
        self._app_command = True

    async def async_stop_cover_tilt(self, **kwargs: Any) -> None:
        """Stop the cover tilt using the blind-specific stop endpoint."""
        await self._device.async_stop_blinds()

    @property
    def current_cover_tilt_position(self):
        """Return the current cover tilt position."""
        return round((1.0 - self._device.current_angle) * 100.0)

    async def async_open_cover_tilt(self, **kwargs: Any) -> None:
        """Open the cover tilt."""
        await self._device.async_set_target_angle(1.0 - 1.0)

    async def async_close_cover_tilt(self, **kwargs: Any) -> None:
        """Close cover tilt."""
        await self._device.async_set_target_angle(1.0 - 0.0)

    async def async_set_cover_tilt_position(self, **kwargs: Any) -> None:
        """Move the cover tilt to a specific position."""
        tilt_position = kwargs[ATTR_TILT_POSITION]
        await self._device.async_set_target_angle(1.0 - (tilt_position / 100.0))
