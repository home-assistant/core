"""Support for the Xiaomi vacuum cleaner robot."""
from __future__ import annotations

from functools import partial
import logging
from typing import Any

from miio import DeviceException
import voluptuous as vol

from homeassistant.components.vacuum import (
    STATE_CLEANING,
    STATE_DOCKED,
    STATE_ERROR,
    STATE_IDLE,
    STATE_PAUSED,
    STATE_RETURNING,
    StateVacuumEntity,
    VacuumEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util.dt import as_utc

from . import VacuumCoordinatorData
from .const import (
    CONF_FLOW_TYPE,
    DOMAIN,
    KEY_COORDINATOR,
    KEY_DEVICE,
    SERVICE_CLEAN_SEGMENT,
    SERVICE_CLEAN_ZONE,
    SERVICE_GOTO,
    SERVICE_MOVE_REMOTE_CONTROL,
    SERVICE_MOVE_REMOTE_CONTROL_STEP,
    SERVICE_START_REMOTE_CONTROL,
    SERVICE_STOP_REMOTE_CONTROL,
)
from .device import XiaomiCoordinatedMiioEntity

_LOGGER = logging.getLogger(__name__)

ATTR_ERROR = "error"
ATTR_RC_DURATION = "duration"
ATTR_RC_ROTATION = "rotation"
ATTR_RC_VELOCITY = "velocity"
ATTR_STATUS = "status"
ATTR_ZONE_ARRAY = "zone"
ATTR_ZONE_REPEATER = "repeats"
ATTR_TIMERS = "timers"

STATE_CODE_TO_STATE = {
    1: STATE_IDLE,  # "Starting"
    2: STATE_IDLE,  # "Charger disconnected"
    3: STATE_IDLE,  # "Idle"
    4: STATE_CLEANING,  # "Remote control active"
    5: STATE_CLEANING,  # "Cleaning"
    6: STATE_RETURNING,  # "Returning home"
    7: STATE_CLEANING,  # "Manual mode"
    8: STATE_DOCKED,  # "Charging"
    9: STATE_ERROR,  # "Charging problem"
    10: STATE_PAUSED,  # "Paused"
    11: STATE_CLEANING,  # "Spot cleaning"
    12: STATE_ERROR,  # "Error"
    13: STATE_IDLE,  # "Shutting down"
    14: STATE_DOCKED,  # "Updating"
    15: STATE_RETURNING,  # "Docking"
    16: STATE_CLEANING,  # "Going to target"
    17: STATE_CLEANING,  # "Zoned cleaning"
    18: STATE_CLEANING,  # "Segment cleaning"
    22: STATE_DOCKED,  # "Emptying the bin" on s7+
    23: STATE_DOCKED,  # "Washing the mop" on s7maxV
    26: STATE_RETURNING,  # "Going to wash the mop" on s7maxV
    100: STATE_DOCKED,  # "Charging complete"
    101: STATE_ERROR,  # "Device offline"
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Xiaomi vacuum cleaner robot from a config entry."""
    entities = []

    if config_entry.data[CONF_FLOW_TYPE] == CONF_DEVICE:
        unique_id = config_entry.unique_id

        mirobo = MiroboVacuum(
            hass.data[DOMAIN][config_entry.entry_id][KEY_DEVICE],
            config_entry,
            unique_id,
            hass.data[DOMAIN][config_entry.entry_id][KEY_COORDINATOR],
        )
        entities.append(mirobo)

        platform = entity_platform.async_get_current_platform()

        platform.async_register_entity_service(
            SERVICE_START_REMOTE_CONTROL,
            {},
            MiroboVacuum.async_remote_control_start.__name__,
        )

        platform.async_register_entity_service(
            SERVICE_STOP_REMOTE_CONTROL,
            {},
            MiroboVacuum.async_remote_control_stop.__name__,
        )

        platform.async_register_entity_service(
            SERVICE_MOVE_REMOTE_CONTROL,
            {
                vol.Optional(ATTR_RC_VELOCITY): vol.All(
                    vol.Coerce(float), vol.Clamp(min=-0.29, max=0.29)
                ),
                vol.Optional(ATTR_RC_ROTATION): vol.All(
                    vol.Coerce(int), vol.Clamp(min=-179, max=179)
                ),
                vol.Optional(ATTR_RC_DURATION): cv.positive_int,
            },
            MiroboVacuum.async_remote_control_move.__name__,
        )

        platform.async_register_entity_service(
            SERVICE_MOVE_REMOTE_CONTROL_STEP,
            {
                vol.Optional(ATTR_RC_VELOCITY): vol.All(
                    vol.Coerce(float), vol.Clamp(min=-0.29, max=0.29)
                ),
                vol.Optional(ATTR_RC_ROTATION): vol.All(
                    vol.Coerce(int), vol.Clamp(min=-179, max=179)
                ),
                vol.Optional(ATTR_RC_DURATION): cv.positive_int,
            },
            MiroboVacuum.async_remote_control_move_step.__name__,
        )

        platform.async_register_entity_service(
            SERVICE_CLEAN_ZONE,
            {
                vol.Required(ATTR_ZONE_ARRAY): vol.All(
                    list,
                    [
                        vol.ExactSequence(
                            [
                                vol.Coerce(int),
                                vol.Coerce(int),
                                vol.Coerce(int),
                                vol.Coerce(int),
                            ]
                        )
                    ],
                ),
                vol.Required(ATTR_ZONE_REPEATER): vol.All(
                    vol.Coerce(int), vol.Clamp(min=1, max=3)
                ),
            },
            MiroboVacuum.async_clean_zone.__name__,
        )

        platform.async_register_entity_service(
            SERVICE_GOTO,
            {
                vol.Required("x_coord"): vol.Coerce(int),
                vol.Required("y_coord"): vol.Coerce(int),
            },
            MiroboVacuum.async_goto.__name__,
        )
        platform.async_register_entity_service(
            SERVICE_CLEAN_SEGMENT,
            {vol.Required("segments"): vol.Any(vol.Coerce(int), [vol.Coerce(int)])},
            MiroboVacuum.async_clean_segment.__name__,
        )

    async_add_entities(entities, update_before_add=True)


class MiroboVacuum(
    XiaomiCoordinatedMiioEntity[DataUpdateCoordinator[VacuumCoordinatorData]],
    StateVacuumEntity,
):
    """Representation of a Xiaomi Vacuum cleaner robot."""

    _attr_name = None
    _attr_supported_features = (
        VacuumEntityFeature.STATE
        | VacuumEntityFeature.PAUSE
        | VacuumEntityFeature.STOP
        | VacuumEntityFeature.RETURN_HOME
        | VacuumEntityFeature.FAN_SPEED
        | VacuumEntityFeature.SEND_COMMAND
        | VacuumEntityFeature.LOCATE
        | VacuumEntityFeature.BATTERY
        | VacuumEntityFeature.CLEAN_SPOT
        | VacuumEntityFeature.START
    )

    def __init__(
        self,
        device,
        entry,
        unique_id,
        coordinator: DataUpdateCoordinator[VacuumCoordinatorData],
    ) -> None:
        """Initialize the Xiaomi vacuum cleaner robot handler."""
        super().__init__(device, entry, unique_id, coordinator)
        self._state: str | None = None

    async def async_added_to_hass(self) -> None:
        """Run when entity is about to be added to hass."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()

    @property
    def state(self) -> str | None:
        """Return the status of the vacuum cleaner."""
        # The vacuum reverts back to an idle state after erroring out.
        # We want to keep returning an error until it has been cleared.
        if self.coordinator.data.status.got_error:
            return STATE_ERROR

        return self._state

    @property
    def battery_level(self) -> int:
        """Return the battery level of the vacuum cleaner."""
        return self.coordinator.data.status.battery

    @property
    def fan_speed(self) -> str:
        """Return the fan speed of the vacuum cleaner."""
        speed = self.coordinator.data.status.fanspeed
        if speed in self.coordinator.data.fan_speeds_reverse:
            return self.coordinator.data.fan_speeds_reverse[speed]

        _LOGGER.debug("Unable to find reverse for %s", speed)

        return str(speed)

    @property
    def fan_speed_list(self) -> list[str]:
        """Get the list of available fan speed steps of the vacuum cleaner."""
        if speed_list := self.coordinator.data.fan_speeds:
            return list(speed_list)
        return []

    @property
    def timers(self) -> list[dict[str, Any]]:
        """Get the list of added timers of the vacuum cleaner."""
        return [
            {
                "enabled": timer.enabled,
                "cron": timer.cron,
                "next_schedule": as_utc(timer.next_schedule),
            }
            for timer in self.coordinator.data.timers
        ]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the specific state attributes of this vacuum cleaner."""
        attrs: dict[str, Any] = {}
        attrs[ATTR_STATUS] = str(self.coordinator.data.status.state)

        if self.coordinator.data.status.got_error:
            attrs[ATTR_ERROR] = self.coordinator.data.status.error

        if self.timers:
            attrs[ATTR_TIMERS] = self.timers
        return attrs

    async def _try_command(self, mask_error, func, *args, **kwargs):
        """Call a vacuum command handling error messages."""
        try:
            await self.hass.async_add_executor_job(partial(func, *args, **kwargs))
            await self.coordinator.async_refresh()
            return True
        except DeviceException as exc:
            _LOGGER.error(mask_error, exc)
            return False

    async def async_start(self) -> None:
        """Start or resume the cleaning task."""
        await self._try_command(
            "Unable to start the vacuum: %s", self._device.resume_or_start
        )

    async def async_pause(self) -> None:
        """Pause the cleaning task."""
        await self._try_command("Unable to set start/pause: %s", self._device.pause)

    async def async_stop(self, **kwargs: Any) -> None:
        """Stop the vacuum cleaner."""
        await self._try_command("Unable to stop: %s", self._device.stop)

    async def async_set_fan_speed(self, fan_speed: str, **kwargs: Any) -> None:
        """Set fan speed."""
        if fan_speed in self.coordinator.data.fan_speeds:
            fan_speed_int = self.coordinator.data.fan_speeds[fan_speed]
        else:
            try:
                fan_speed_int = int(fan_speed)
            except ValueError as exc:
                _LOGGER.error(
                    "Fan speed step not recognized (%s). Valid speeds are: %s",
                    exc,
                    self.fan_speed_list,
                )
                return
        await self._try_command(
            "Unable to set fan speed: %s", self._device.set_fan_speed, fan_speed_int
        )

    async def async_return_to_base(self, **kwargs: Any) -> None:
        """Set the vacuum cleaner to return to the dock."""
        await self._try_command("Unable to return home: %s", self._device.home)

    async def async_clean_spot(self, **kwargs: Any) -> None:
        """Perform a spot clean-up."""
        await self._try_command(
            "Unable to start the vacuum for a spot clean-up: %s", self._device.spot
        )

    async def async_locate(self, **kwargs: Any) -> None:
        """Locate the vacuum cleaner."""
        await self._try_command("Unable to locate the botvac: %s", self._device.find)

    async def async_send_command(
        self,
        command: str,
        params: dict[str, Any] | list[Any] | None = None,
        **kwargs: Any,
    ) -> None:
        """Send raw command."""
        await self._try_command(
            "Unable to send command to the vacuum: %s",
            self._device.raw_command,
            command,
            params,
        )

    async def async_remote_control_start(self) -> None:
        """Start remote control mode."""
        await self._try_command(
            "Unable to start remote control the vacuum: %s", self._device.manual_start
        )

    async def async_remote_control_stop(self) -> None:
        """Stop remote control mode."""
        await self._try_command(
            "Unable to stop remote control the vacuum: %s", self._device.manual_stop
        )

    async def async_remote_control_move(
        self, rotation: int = 0, velocity: float = 0.3, duration: int = 1500
    ) -> None:
        """Move vacuum with remote control mode."""
        await self._try_command(
            "Unable to move with remote control the vacuum: %s",
            self._device.manual_control,
            velocity=velocity,
            rotation=rotation,
            duration=duration,
        )

    async def async_remote_control_move_step(
        self, rotation: int = 0, velocity: float = 0.2, duration: int = 1500
    ) -> None:
        """Move vacuum one step with remote control mode."""
        await self._try_command(
            "Unable to remote control the vacuum: %s",
            self._device.manual_control_once,
            velocity=velocity,
            rotation=rotation,
            duration=duration,
        )

    async def async_goto(self, x_coord: int, y_coord: int) -> None:
        """Goto the specified coordinates."""
        await self._try_command(
            "Unable to send the vacuum cleaner to the specified coordinates: %s",
            self._device.goto,
            x_coord=x_coord,
            y_coord=y_coord,
        )

    async def async_clean_segment(self, segments) -> None:
        """Clean the specified segments(s)."""
        if isinstance(segments, int):
            segments = [segments]

        await self._try_command(
            "Unable to start cleaning of the specified segments: %s",
            self._device.segment_clean,
            segments=segments,
        )

    async def async_clean_zone(self, zone: list[Any], repeats: int = 1) -> None:
        """Clean selected area for the number of repeats indicated."""
        for _zone in zone:
            _zone.append(repeats)
        _LOGGER.debug("Zone with repeats: %s", zone)
        try:
            await self.hass.async_add_executor_job(self._device.zoned_clean, zone)
            await self.coordinator.async_refresh()
        except (OSError, DeviceException) as exc:
            _LOGGER.error("Unable to send zoned_clean command to the vacuum: %s", exc)

    @callback
    def _handle_coordinator_update(self) -> None:
        state_code = int(self.coordinator.data.status.state_code)
        if state_code not in STATE_CODE_TO_STATE:
            _LOGGER.error(
                "STATE not supported: %s, state_code: %s",
                self.coordinator.data.status.state,
                self.coordinator.data.status.state_code,
            )
            self._state = None
        else:
            self._state = STATE_CODE_TO_STATE[state_code]

        super()._handle_coordinator_update()
