"""Support for Roborock vacuum class."""

import asyncio
import logging
from typing import Any

from roborock.data import RoborockStateCode, SCWindMapping, WorkStatusMapping
from roborock.exceptions import RoborockException
from roborock.roborock_typing import RoborockCommand

from homeassistant.components.vacuum import (
    Segment,
    StateVacuumEntity,
    VacuumActivity,
    VacuumEntityFeature,
)
from homeassistant.core import HomeAssistant, ServiceResponse
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, MAP_SLEEP
from .coordinator import (
    RoborockB01Q7UpdateCoordinator,
    RoborockConfigEntry,
    RoborockDataUpdateCoordinator,
)
from .entity import RoborockCoordinatedEntityB01, RoborockCoordinatedEntityV1

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
        for coordinator in config_entry.runtime_data.b01
        if isinstance(coordinator, RoborockB01Q7UpdateCoordinator)
    )


class RoborockVacuum(RoborockCoordinatedEntityV1, StateVacuumEntity):
    """General Representation of a Roborock vacuum."""

    _attr_icon = "mdi:robot-vacuum"
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
        self._home_trait = coordinator.properties_api.home
        self._maps_trait = coordinator.properties_api.maps

    @property
    def fan_speed_list(self) -> list[str]:
        """Get the list of available fan speeds."""
        return self._device_status.fan_power_options

    @property
    def activity(self) -> VacuumActivity | None:
        """Return the status of the vacuum cleaner."""
        assert self._device_status.state is not None
        return STATE_CODE_TO_STATE.get(self._device_status.state)

    @property
    def fan_speed(self) -> str | None:
        """Return the fan speed of the vacuum cleaner."""
        return self._device_status.fan_power_name

    async def async_start(self) -> None:
        """Start the vacuum."""
        if self._device_status.in_returning == 1:
            await self.send(RoborockCommand.APP_CHARGE)
        elif self._device_status.in_cleaning == 2:
            await self.send(RoborockCommand.RESUME_ZONED_CLEAN)
        elif self._device_status.in_cleaning == 3:
            await self.send(RoborockCommand.RESUME_SEGMENT_CLEAN)
        elif self._device_status.in_cleaning == 4:
            await self.send(RoborockCommand.APP_RESUME_BUILD_MAP)
        else:
            await self.send(RoborockCommand.APP_START)

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
        await self.send(
            RoborockCommand.SET_CUSTOM_MODE,
            [self._device_status.get_fan_speed_code(fan_speed)],
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
                id=f"{map_flag}:{room.segment_id}",
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
            # Segment id is mapflag:segment_id
            parts = seg_id.split(":")
            if len(parts) != 2:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="segment_id_parse_error",
                    translation_placeholders={"segment_id": seg_id},
                )
            try:
                # We need to make sure both parts are ints.
                parsed.append((int(parts[0]), int(parts[1])))
            except ValueError as err:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="segment_id_parse_error",
                    translation_placeholders={"segment_id": seg_id},
                ) from err

        # Because segment_ids can overlap for each map,
        # we need to make sure that only one map is passed in.
        unique_map_flags = {map_flag for map_flag, _ in parsed}
        if len(unique_map_flags) > 1:
            map_flags_str = ", ".join(str(flag) for flag in sorted(unique_map_flags))
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="multiple_maps_in_clean",
                translation_placeholders={"map_flags": map_flags_str},
            )
        target_map_flag = next(iter(unique_map_flags))
        if self._maps_trait.current_map != target_map_flag:
            # If the user is attempting to clean an area on a map that is not selected, we should try to change.
            try:
                await self._maps_trait.set_current_map(target_map_flag)
            except RoborockException as err:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="command_failed",
                    translation_placeholders={"command": "load_multi_map"},
                ) from err
            await asyncio.sleep(MAP_SLEEP)

        # We can now confirm all segments are on our current map, so clean them all.
        await self.send(
            RoborockCommand.APP_SEGMENT_CLEAN,
            [{"segments": [seg_id for _, seg_id in parsed]}],
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


class RoborockQ7Vacuum(RoborockCoordinatedEntityB01, StateVacuumEntity):
    """General Representation of a Roborock vacuum."""

    _attr_icon = "mdi:robot-vacuum"
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
        RoborockCoordinatedEntityB01.__init__(
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
