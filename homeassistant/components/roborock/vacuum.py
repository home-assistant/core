"""Support for Roborock vacuum class."""

import logging
from typing import Any

from roborock.data import RoborockStateCode, SCWindMapping, WorkStatusMapping
from roborock.data.b01_q10.b01_q10_code_mappings import (
    B01_Q10_DP,
    YXDeviceState,
    YXFanLevel,
)
from roborock.exceptions import RoborockException
from roborock.roborock_typing import RoborockCommand

from homeassistant.components.vacuum import (
    Segment,
    StateVacuumEntity,
    VacuumActivity,
    VacuumEntityFeature,
)
from homeassistant.core import HomeAssistant, ServiceResponse, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import (
    RoborockB01Q7UpdateCoordinator,
    RoborockB01Q10UpdateCoordinator,
    RoborockConfigEntry,
    RoborockDataUpdateCoordinator,
)
from .entity import (
    RoborockCoordinatedEntityB01Q7,
    RoborockCoordinatedEntityB01Q10,
    RoborockCoordinatedEntityV1,
)

_LOGGER = logging.getLogger(__name__)

STATE_CODE_TO_STATE = {
    RoborockStateCode.starting: VacuumActivity.IDLE,  # "Starting"
    RoborockStateCode.attaching_the_mop: VacuumActivity.DOCKED,  # "Attaching the mop"
    RoborockStateCode.charger_disconnected: VacuumActivity.IDLE,  # "Charger disconnected"
    RoborockStateCode.idle: VacuumActivity.IDLE,  # "Idle"
    RoborockStateCode.remote_control_active: VacuumActivity.CLEANING,  # "Remote control active"
    RoborockStateCode.cleaning: VacuumActivity.CLEANING,  # "Cleaning"
    RoborockStateCode.detaching_the_mop: VacuumActivity.DOCKED,  # "Detaching the mop"
    RoborockStateCode.returning_home: VacuumActivity.RETURNING,  # "Returning home"
    RoborockStateCode.manual_mode: VacuumActivity.CLEANING,  # "Manual mode"
    RoborockStateCode.charging: VacuumActivity.DOCKED,  # "Charging"
    RoborockStateCode.charging_problem: VacuumActivity.ERROR,  # "Charging problem"
    RoborockStateCode.paused: VacuumActivity.PAUSED,  # "Paused"
    RoborockStateCode.spot_cleaning: VacuumActivity.CLEANING,  # "Spot cleaning"
    RoborockStateCode.error: VacuumActivity.ERROR,  # "Error"
    RoborockStateCode.shutting_down: VacuumActivity.IDLE,  # "Shutting down"
    RoborockStateCode.updating: VacuumActivity.DOCKED,  # "Updating"
    RoborockStateCode.docking: VacuumActivity.RETURNING,  # "Docking"
    RoborockStateCode.going_to_target: VacuumActivity.CLEANING,  # "Going to target"
    RoborockStateCode.zoned_cleaning: VacuumActivity.CLEANING,  # "Zoned cleaning"
    RoborockStateCode.segment_cleaning: VacuumActivity.CLEANING,  # "Segment cleaning"
    RoborockStateCode.emptying_the_bin: VacuumActivity.DOCKED,  # "Emptying the bin" on s7+
    RoborockStateCode.washing_the_mop: VacuumActivity.DOCKED,  # "Washing the mop" on s7maxV
    RoborockStateCode.going_to_wash_the_mop: VacuumActivity.RETURNING,  # "Going to wash the mop" on s7maxV
    RoborockStateCode.charging_complete: VacuumActivity.DOCKED,  # "Charging complete"
    RoborockStateCode.device_offline: VacuumActivity.ERROR,  # "Device offline"
}

Q7_STATE_CODE_TO_STATE = {
    WorkStatusMapping.SLEEPING: VacuumActivity.IDLE,
    WorkStatusMapping.WAITING_FOR_ORDERS: VacuumActivity.IDLE,
    WorkStatusMapping.PAUSED: VacuumActivity.PAUSED,
    WorkStatusMapping.DOCKING: VacuumActivity.RETURNING,
    WorkStatusMapping.CHARGING: VacuumActivity.DOCKED,
    WorkStatusMapping.SWEEP_MOPING: VacuumActivity.CLEANING,
    WorkStatusMapping.SWEEP_MOPING_2: VacuumActivity.CLEANING,
    WorkStatusMapping.MOPING: VacuumActivity.CLEANING,
    WorkStatusMapping.UPDATING: VacuumActivity.DOCKED,
    WorkStatusMapping.MOP_CLEANING: VacuumActivity.DOCKED,
    WorkStatusMapping.MOP_AIRDRYING: VacuumActivity.DOCKED,
}

Q10_STATE_CODE_TO_STATE = {
    YXDeviceState.SLEEPING: VacuumActivity.IDLE,
    YXDeviceState.IDLE: VacuumActivity.IDLE,
    YXDeviceState.CLEANING: VacuumActivity.CLEANING,
    YXDeviceState.RETURNING_HOME: VacuumActivity.RETURNING,
    YXDeviceState.REMOTE_CONTROL_ACTIVE: VacuumActivity.CLEANING,
    YXDeviceState.CHARGING: VacuumActivity.DOCKED,
    YXDeviceState.PAUSED: VacuumActivity.PAUSED,
    YXDeviceState.ERROR: VacuumActivity.ERROR,
    YXDeviceState.UPDATING: VacuumActivity.DOCKED,
    YXDeviceState.EMPTYING_THE_BIN: VacuumActivity.DOCKED,
    YXDeviceState.MAPPING: VacuumActivity.CLEANING,
    YXDeviceState.RELOCATING: VacuumActivity.CLEANING,
    YXDeviceState.SWEEPING: VacuumActivity.CLEANING,
    YXDeviceState.MOPPING: VacuumActivity.CLEANING,
    YXDeviceState.SWEEP_AND_MOP: VacuumActivity.CLEANING,
    YXDeviceState.TRANSITIONING: VacuumActivity.CLEANING,
    YXDeviceState.WAITING_TO_CHARGE: VacuumActivity.DOCKED,
}

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: RoborockConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Roborock sensor."""
    async_add_entities(
        RoborockVacuum(coordinator) for coordinator in config_entry.runtime_data.v1
    )
    async_add_entities(
        RoborockQ7Vacuum(coordinator)
        for coordinator in config_entry.runtime_data.b01_q7
    )
    async_add_entities(
        RoborockQ10Vacuum(coordinator)
        for coordinator in config_entry.runtime_data.b01_q10
    )


class RoborockVacuum(RoborockCoordinatedEntityV1, StateVacuumEntity):
    """General Representation of a Roborock vacuum."""

    _attr_supported_features = (
        VacuumEntityFeature.PAUSE
        | VacuumEntityFeature.STOP
        | VacuumEntityFeature.RETURN_HOME
        | VacuumEntityFeature.FAN_SPEED
        | VacuumEntityFeature.SEND_COMMAND
        | VacuumEntityFeature.LOCATE
        | VacuumEntityFeature.CLEAN_SPOT
        | VacuumEntityFeature.STATE
        | VacuumEntityFeature.START
        | VacuumEntityFeature.CLEAN_AREA
    )
    _attr_translation_key = DOMAIN
    _attr_name = None

    def __init__(
        self,
        coordinator: RoborockDataUpdateCoordinator,
    ) -> None:
        """Initialize a vacuum."""
        StateVacuumEntity.__init__(self)
        RoborockCoordinatedEntityV1.__init__(
            self,
            coordinator.duid_slug,
            coordinator,
        )
        self._status_trait = coordinator.properties_api.status
        self._home_trait = coordinator.properties_api.home
        self._maps_trait = coordinator.properties_api.maps

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator.

        Creates a repair issue when the vacuum reports different segments than
        what was available when the area mapping was last configured.
        """
        super()._handle_coordinator_update()
        last_seen = self.last_seen_segments
        if last_seen is None:
            # No area mapping has been configured yet; nothing to check.
            return
        current_ids = {
            f"{map_flag}_{room.segment_id}"
            for map_flag, map_info in (self._home_trait.home_map_info or {}).items()
            for room in map_info.rooms
        }
        if current_ids != {seg.id for seg in last_seen}:
            self.async_create_segments_issue()

    @property
    def fan_speed_list(self) -> list[str]:
        """Get the list of available fan speeds."""
        if self.coordinator.data is None:
            return []
        return [mode.value for mode in self._status_trait.fan_speed_options]

    @property
    def activity(self) -> VacuumActivity | None:
        """Return the status of the vacuum cleaner."""
        if self.coordinator.data is None or self._status_trait.state is None:
            return None
        return STATE_CODE_TO_STATE.get(self._status_trait.state)

    @property
    def fan_speed(self) -> str | None:
        """Return the fan speed of the vacuum cleaner."""
        if self.coordinator.data is None:
            return None
        return self._status_trait.fan_speed_name

    async def async_start(self) -> None:
        """Start the vacuum."""
        command = RoborockCommand.APP_START
        if self.coordinator.data is not None:
            if self._status_trait.in_returning == 1:
                command = RoborockCommand.APP_CHARGE
            elif self._status_trait.in_cleaning == 2:
                command = RoborockCommand.RESUME_ZONED_CLEAN
            elif self._status_trait.in_cleaning == 3:
                command = RoborockCommand.RESUME_SEGMENT_CLEAN
            elif self._status_trait.in_cleaning == 4:
                command = RoborockCommand.APP_RESUME_BUILD_MAP
        await self.send(command)

    async def async_pause(self) -> None:
        """Pause the vacuum."""
        await self.send(RoborockCommand.APP_PAUSE)

    async def async_stop(self, **kwargs: Any) -> None:
        """Stop the vacuum."""
        await self.send(RoborockCommand.APP_STOP)

    async def async_return_to_base(self, **kwargs: Any) -> None:
        """Send vacuum back to base."""
        await self.send(RoborockCommand.APP_CHARGE)

    async def async_clean_spot(self, **kwargs: Any) -> None:
        """Spot clean."""
        await self.send(RoborockCommand.APP_SPOT)

    async def async_locate(self, **kwargs: Any) -> None:
        """Locate vacuum."""
        await self.send(RoborockCommand.FIND_ME)

    async def async_set_fan_speed(self, fan_speed: str, **kwargs: Any) -> None:
        """Set vacuum fan speed."""
        if self.coordinator.data is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="update_options_failed",
            )
        await self.send(
            RoborockCommand.SET_CUSTOM_MODE,
            [
                {v: k for k, v in self._status_trait.fan_speed_mapping.items()}[
                    fan_speed
                ]
            ],
        )

    async def async_set_vacuum_goto_position(self, x: int, y: int) -> None:
        """Send vacuum to a specific target point."""
        await self.send(RoborockCommand.APP_GOTO_TARGET, [x, y])

    async def async_get_segments(self) -> list[Segment]:
        """Get the segments that can be cleaned."""
        home_map_info = self._home_trait.home_map_info
        if not home_map_info:
            return []
        return [
            Segment(
                id=f"{map_flag}_{room.segment_id}",
                name=room.name,
                group=map_info.name,
            )
            for map_flag, map_info in home_map_info.items()
            for room in map_info.rooms
        ]

    async def async_clean_segments(self, segment_ids: list[str], **kwargs: Any) -> None:
        """Clean the specified segments."""
        parsed: list[tuple[int, int]] = []
        for seg_id in segment_ids:
            map_flag_str, room_id_str = seg_id.split("_", maxsplit=1)
            parsed.append((int(map_flag_str), int(room_id_str)))

        # Segments from other maps are silently ignored; only segments
        # belonging to the currently active map are cleaned.
        current_map = self._maps_trait.current_map
        current_map_segments = [
            seg_id for map_flag, seg_id in parsed if map_flag == current_map
        ]
        if not current_map_segments:
            return

        await self.send(
            RoborockCommand.APP_SEGMENT_CLEAN,
            [{"segments": current_map_segments}],
        )

    async def async_send_command(
        self,
        command: str,
        params: dict[str, Any] | list[Any] | None = None,
        **kwargs: Any,
    ) -> None:
        """Send a command to a vacuum cleaner."""
        await self.send(command, params)

    async def get_maps(self) -> ServiceResponse:
        """Get map information such as map id and room ids."""
        home_trait = self.coordinator.properties_api.home
        return {
            "maps": [
                {
                    "flag": vacuum_map.map_flag,
                    "name": vacuum_map.name,
                    "rooms": {
                        # JsonValueType does not accept a int as a key - was not a
                        # issue with previous asdict() implementation.
                        room.segment_id: room.name  # type: ignore[misc]
                        for room in vacuum_map.rooms
                    },
                }
                for vacuum_map in (home_trait.home_map_info or {}).values()
            ]
        }

    async def get_vacuum_current_position(self) -> ServiceResponse:
        """Get the current position of the vacuum from the map."""
        map_content_trait = self.coordinator.properties_api.map_content
        try:
            await map_content_trait.refresh()
        except RoborockException as err:
            _LOGGER.debug("Failed to refresh map content: %s", err)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="map_failure",
            ) from err
        if map_content_trait.map_data is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="map_failure",
            )
        if (robot_position := map_content_trait.map_data.vacuum_position) is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="position_not_found"
            )

        return {
            "x": robot_position.x,
            "y": robot_position.y,
        }


class RoborockQ7Vacuum(RoborockCoordinatedEntityB01Q7, StateVacuumEntity):
    """General Representation of a Roborock vacuum."""

    _attr_supported_features = (
        VacuumEntityFeature.PAUSE
        | VacuumEntityFeature.STOP
        | VacuumEntityFeature.RETURN_HOME
        | VacuumEntityFeature.FAN_SPEED
        | VacuumEntityFeature.SEND_COMMAND
        | VacuumEntityFeature.LOCATE
        | VacuumEntityFeature.STATE
        | VacuumEntityFeature.START
    )
    _attr_translation_key = DOMAIN
    _attr_name = None
    coordinator: RoborockB01Q7UpdateCoordinator

    def __init__(
        self,
        coordinator: RoborockB01Q7UpdateCoordinator,
    ) -> None:
        """Initialize a vacuum."""
        StateVacuumEntity.__init__(self)
        RoborockCoordinatedEntityB01Q7.__init__(
            self,
            coordinator.duid_slug,
            coordinator,
        )

    @property
    def fan_speed_list(self) -> list[str]:
        """Get the list of available fan speeds."""
        return SCWindMapping.keys()

    @property
    def activity(self) -> VacuumActivity | None:
        """Return the status of the vacuum cleaner."""
        if self.coordinator.data.status is not None:
            return Q7_STATE_CODE_TO_STATE.get(self.coordinator.data.status)
        return None

    @property
    def fan_speed(self) -> str | None:
        """Return the fan speed of the vacuum cleaner."""
        return self.coordinator.data.wind_name

    async def async_start(self) -> None:
        """Start the vacuum."""
        try:
            await self.coordinator.api.start_clean()
        except RoborockException as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_failed",
                translation_placeholders={
                    "command": "start_clean",
                },
            ) from err

    async def async_pause(self) -> None:
        """Pause the vacuum."""
        try:
            await self.coordinator.api.pause_clean()
        except RoborockException as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_failed",
                translation_placeholders={
                    "command": "pause_clean",
                },
            ) from err

    async def async_stop(self, **kwargs: Any) -> None:
        """Stop the vacuum."""
        try:
            await self.coordinator.api.stop_clean()
        except RoborockException as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_failed",
                translation_placeholders={
                    "command": "stop_clean",
                },
            ) from err

    async def async_return_to_base(self, **kwargs: Any) -> None:
        """Send vacuum back to base."""
        try:
            await self.coordinator.api.return_to_dock()
        except RoborockException as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_failed",
                translation_placeholders={
                    "command": "return_to_dock",
                },
            ) from err

    async def async_locate(self, **kwargs: Any) -> None:
        """Locate vacuum."""
        try:
            await self.coordinator.api.find_me()
        except RoborockException as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_failed",
                translation_placeholders={
                    "command": "find_me",
                },
            ) from err

    async def async_set_fan_speed(self, fan_speed: str, **kwargs: Any) -> None:
        """Set vacuum fan speed."""
        try:
            await self.coordinator.api.set_fan_speed(
                SCWindMapping.from_value(fan_speed)
            )
        except RoborockException as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_failed",
                translation_placeholders={
                    "command": "set_fan_speed",
                },
            ) from err

    async def async_send_command(
        self,
        command: str,
        params: dict[str, Any] | list[Any] | None = None,
        **kwargs: Any,
    ) -> None:
        """Send a command to a vacuum cleaner."""
        try:
            await self.coordinator.api.send(command, params)
        except RoborockException as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_failed",
                translation_placeholders={
                    "command": command,
                },
            ) from err


class RoborockQ10Vacuum(RoborockCoordinatedEntityB01Q10, StateVacuumEntity):
    """Representation of a Roborock Q10 vacuum."""

    _attr_supported_features = (
        VacuumEntityFeature.PAUSE
        | VacuumEntityFeature.STOP
        | VacuumEntityFeature.RETURN_HOME
        | VacuumEntityFeature.FAN_SPEED
        | VacuumEntityFeature.SEND_COMMAND
        | VacuumEntityFeature.LOCATE
        | VacuumEntityFeature.STATE
        | VacuumEntityFeature.START
    )
    _attr_translation_key = DOMAIN
    _attr_name = None
    _attr_fan_speed_list = [
        fan_level.value for fan_level in YXFanLevel if fan_level != YXFanLevel.UNKNOWN
    ]

    def __init__(
        self,
        coordinator: RoborockB01Q10UpdateCoordinator,
    ) -> None:
        """Initialize a vacuum."""
        StateVacuumEntity.__init__(self)
        RoborockCoordinatedEntityB01Q10.__init__(
            self,
            coordinator.duid_slug,
            coordinator,
        )

    async def async_added_to_hass(self) -> None:
        """Register trait listener for push-based status updates."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.api.status.add_update_listener(self.async_write_ha_state)
        )

    @property
    def activity(self) -> VacuumActivity | None:
        """Return the status of the vacuum cleaner."""
        if self.coordinator.api.status.status is not None:
            return Q10_STATE_CODE_TO_STATE.get(self.coordinator.api.status.status)
        return None

    @property
    def fan_speed(self) -> str | None:
        """Return the fan speed of the vacuum cleaner."""
        if (fan_level := self.coordinator.api.status.fan_level) is not None:
            return fan_level.value
        return None

    async def async_start(self) -> None:
        """Start the vacuum."""
        try:
            await self.coordinator.api.vacuum.start_clean()
        except RoborockException as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_failed",
                translation_placeholders={
                    "command": "start_clean",
                },
            ) from err

    async def async_pause(self) -> None:
        """Pause the vacuum."""
        try:
            await self.coordinator.api.vacuum.pause_clean()
        except RoborockException as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_failed",
                translation_placeholders={
                    "command": "pause_clean",
                },
            ) from err

    async def async_stop(self, **kwargs: Any) -> None:
        """Stop the vacuum."""
        try:
            await self.coordinator.api.vacuum.stop_clean()
        except RoborockException as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_failed",
                translation_placeholders={
                    "command": "stop_clean",
                },
            ) from err

    async def async_return_to_base(self, **kwargs: Any) -> None:
        """Send vacuum back to base."""
        try:
            await self.coordinator.api.vacuum.return_to_dock()
        except RoborockException as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_failed",
                translation_placeholders={
                    "command": "return_to_dock",
                },
            ) from err

    async def async_locate(self, **kwargs: Any) -> None:
        """Locate vacuum."""
        try:
            await self.coordinator.api.command.send(B01_Q10_DP.SEEK)
        except RoborockException as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_failed",
                translation_placeholders={
                    "command": "find_me",
                },
            ) from err

    async def async_set_fan_speed(self, fan_speed: str, **kwargs: Any) -> None:
        """Set vacuum fan speed."""
        try:
            fan_level = YXFanLevel.from_value(fan_speed)
        except ValueError as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_fan_speed",
                translation_placeholders={
                    "fan_speed": fan_speed,
                },
            ) from err
        try:
            await self.coordinator.api.vacuum.set_fan_level(fan_level)
        except RoborockException as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_failed",
                translation_placeholders={
                    "command": "set_fan_speed",
                },
            ) from err

    async def async_send_command(
        self,
        command: str,
        params: dict[str, Any] | list[Any] | None = None,
        **kwargs: Any,
    ) -> None:
        """Send a command to a vacuum cleaner.

        The command string can be an enum name (e.g. "SEEK"), a DP string
        value (e.g. "dpSeek"), or an integer code (e.g. "11").
        """
        if (dp_command := B01_Q10_DP.from_any_optional(command)) is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_command",
                translation_placeholders={
                    "command": command,
                },
            )
        try:
            await self.coordinator.api.command.send(dp_command, params=params)
        except RoborockException as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_failed",
                translation_placeholders={
                    "command": command,
                },
            ) from err
