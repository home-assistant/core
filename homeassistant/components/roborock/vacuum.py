"""Support for Roborock vacuum class."""

import logging
from typing import Any

from roborock.data import B01Props, RoborockStateCode, SCWindMapping, WorkStatusMapping
from roborock.data.b01_q10.b01_q10_code_mappings import (
    B01_Q10_DP,
    YXDeviceState,
    YXFanLevel,
)
from roborock.exceptions import RoborockException
from roborock.roborock_typing import RoborockCommand
import voluptuous as vol

from homeassistant.components.vacuum import (
    StateVacuumEntity,
    VacuumActivity,
    VacuumEntityFeature,
)
from homeassistant.core import HomeAssistant, ServiceResponse, SupportsResponse
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .coordinator import (
    RoborockB01Q7UpdateCoordinator,
    RoborockB01Q10UpdateCoordinator,
    RoborockConfigEntry,
    RoborockDataUpdateCoordinator,
)
from .entity import RoborockCoordinatedEntityB01, RoborockCoordinatedEntityV1
from .services import (
    GET_MAPS_SERVICE_NAME,
    GET_VACUUM_CURRENT_POSITION_SERVICE_NAME,
    SET_VACUUM_GOTO_POSITION_SERVICE_NAME,
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
    YXDeviceState.SLEEP_STATE: VacuumActivity.IDLE,
    YXDeviceState.STANDBY_STATE: VacuumActivity.IDLE,
    YXDeviceState.CLEANING_STATE: VacuumActivity.CLEANING,
    YXDeviceState.TO_CHARGE_STATE: VacuumActivity.RETURNING,
    YXDeviceState.REMOTEING_STATE: VacuumActivity.CLEANING,
    YXDeviceState.CHARGING_STATE: VacuumActivity.DOCKED,
    YXDeviceState.PAUSE_STATE: VacuumActivity.PAUSED,
    YXDeviceState.FAULT_STATE: VacuumActivity.ERROR,
    YXDeviceState.UPGRADE_STATE: VacuumActivity.DOCKED,
    YXDeviceState.DUSTING: VacuumActivity.DOCKED,
    YXDeviceState.ROBOT_SWEEPING: VacuumActivity.CLEANING,
    YXDeviceState.ROBOT_MOPING: VacuumActivity.CLEANING,
    YXDeviceState.ROBOT_SWEEP_AND_MOPING: VacuumActivity.CLEANING,
    YXDeviceState.ROBOT_TRANSITIONING: VacuumActivity.RETURNING,
    YXDeviceState.ROBOT_WAIT_CHARGE: VacuumActivity.RETURNING,
}


def _get_q10_status(data: dict[Any, Any]) -> YXDeviceState | None:
    """Get status from Q10 data."""
    # Q10 data - dict from status.refresh() - uses B01_Q10_DP keys
    status_code = data.get(B01_Q10_DP.STATUS)
    if status_code is None:
        return None

    for state in YXDeviceState:
        if state.code == status_code:
            return state
    return None


def _get_q10_wind_name(data: dict[Any, Any]) -> str | None:
    """Get wind/fan speed name from Q10 data."""
    # Q10 data - dict from status.refresh() - uses B01_Q10_DP keys
    fan_level = data.get(B01_Q10_DP.FAN_LEVEL)
    if fan_level is not None:
        # Map YXFanLevel code to value (e.g., "quiet", "normal", "strong", "max")
        for yx_fan in YXFanLevel:
            if yx_fan.code == fan_level:
                return yx_fan.value
    return None


PARALLEL_UPDATES = 0


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Roborock vacuum platform."""
    platform = entity_platform.async_get_current_platform()

    platform.async_register_entity_service(
        GET_MAPS_SERVICE_NAME,
        None,
        RoborockVacuum.get_maps.__name__,
        supports_response=SupportsResponse.ONLY,
    )

    platform.async_register_entity_service(
        GET_VACUUM_CURRENT_POSITION_SERVICE_NAME,
        None,
        RoborockVacuum.get_vacuum_current_position.__name__,
        supports_response=SupportsResponse.ONLY,
    )

    platform.async_register_entity_service(
        SET_VACUUM_GOTO_POSITION_SERVICE_NAME,
        cv.make_entity_service_schema(
            {
                vol.Required("x"): vol.Coerce(int),
                vol.Required("y"): vol.Coerce(int),
            },
        ),
        RoborockVacuum.async_set_vacuum_goto_position.__name__,
        supports_response=SupportsResponse.NONE,
    )

    return True


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
    async_add_entities(
        RoborockQ10Vacuum(coordinator)
        for coordinator in config_entry.runtime_data.b01
        if isinstance(coordinator, RoborockB01Q10UpdateCoordinator)
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
    """Representation of a Roborock Q7/Q10 vacuum."""

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
        data = self.coordinator.data
        if not isinstance(data, B01Props) or data.status is None:
            return None
        return Q7_STATE_CODE_TO_STATE.get(data.status)

    @property
    def fan_speed(self) -> str | None:
        """Return the fan speed of the vacuum cleaner."""
        data = self.coordinator.data
        if not isinstance(data, B01Props):
            return None
        return data.wind_name

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
        await self.coordinator.async_refresh()

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
        await self.coordinator.async_refresh()

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
        await self.coordinator.async_refresh()

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
        await self.coordinator.async_refresh()

    async def async_set_fan_speed(self, fan_speed: str, **kwargs: Any) -> None:
        """Set vacuum fan speed."""
        try:
            fan_level = SCWindMapping.from_value(fan_speed)
            await self.coordinator.api.set_fan_speed(fan_level)
        except RoborockException as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_failed",
                translation_placeholders={
                    "command": "set_fan_speed",
                },
            ) from err
        await self.coordinator.async_refresh()

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

    async def get_maps(self) -> ServiceResponse:
        """Get map information (not available for Q7)."""
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="command_not_supported",
        )

    async def get_vacuum_current_position(self) -> ServiceResponse:
        """Get vacuum current position (not available for Q7)."""
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="command_not_supported",
        )

    async def async_set_vacuum_goto_position(
        self, x: int, y: int, **kwargs: Any
    ) -> None:
        """Set vacuum goto position (not available for Q7)."""
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="command_not_supported",
        )


class RoborockQ10Vacuum(RoborockCoordinatedEntityB01, StateVacuumEntity):
    """Representation of a Roborock Q10 vacuum."""

    _attr_icon = "mdi:robot-vacuum"
    _attr_supported_features = (
        VacuumEntityFeature.PAUSE
        | VacuumEntityFeature.STOP
        | VacuumEntityFeature.RETURN_HOME
        | VacuumEntityFeature.FAN_SPEED
        | VacuumEntityFeature.LOCATE
        | VacuumEntityFeature.SEND_COMMAND
        | VacuumEntityFeature.STATE
        | VacuumEntityFeature.START
        | VacuumEntityFeature.CLEAN_SPOT
    )
    _attr_translation_key = DOMAIN
    _attr_name = None
    # Q10 uses YXFanLevel: quiet, normal, strong, max, super
    _attr_fan_speed_list = [
        YXFanLevel.QUIET.value,
        YXFanLevel.NORMAL.value,
        YXFanLevel.STRONG.value,
        YXFanLevel.MAX.value,
        YXFanLevel.SUPER.value,
    ]
    coordinator: RoborockB01Q10UpdateCoordinator

    def __init__(
        self,
        coordinator: RoborockB01Q10UpdateCoordinator,
    ) -> None:
        """Initialize a vacuum."""
        StateVacuumEntity.__init__(self)
        RoborockCoordinatedEntityB01.__init__(
            self,
            coordinator.duid_slug,
            coordinator,
        )

    @property
    def activity(self) -> VacuumActivity | None:
        """Return the status of the vacuum cleaner."""
        data = self.coordinator.data
        if isinstance(data, B01Props):
            return None
        status = _get_q10_status(data)
        if status is not None:
            return Q10_STATE_CODE_TO_STATE.get(status)
        return None

    @property
    def fan_speed(self) -> str | None:
        """Return the current fan speed."""
        data = self.coordinator.data
        if isinstance(data, B01Props):
            return None
        return _get_q10_wind_name(data)

    async def async_start(self) -> None:
        """Start the vacuum."""
        try:
            data = self.coordinator.data
            status = _get_q10_status(data) if not isinstance(data, B01Props) else None
            if status is YXDeviceState.PAUSE_STATE:
                await self.coordinator.api.command.send(
                    command=B01_Q10_DP.RESUME,
                    params={},
                )
            else:
                await self.coordinator.api.vacuum.start_clean()
        except RoborockException as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_failed",
                translation_placeholders={
                    "command": "start_clean",
                },
            ) from err
        await self.coordinator.async_refresh()

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
        await self.coordinator.async_refresh()

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
        await self.coordinator.async_refresh()

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
        await self.coordinator.async_refresh()

    async def async_clean_spot(self, **kwargs: Any) -> None:
        """Clean a spot/zone."""
        try:
            # Start spot/zone cleaning using start_clean
            await self.coordinator.api.vacuum.start_clean()
        except RoborockException as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_failed",
                translation_placeholders={
                    "command": "start_clean",
                },
            ) from err
        await self.coordinator.async_refresh()

    async def async_locate(self, **kwargs: Any) -> None:
        """Locate vacuum (not available for Q10)."""
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="command_not_supported",
        )

    async def get_maps(self) -> ServiceResponse:
        """Get map information (not available for Q10)."""
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="command_not_supported",
        )

    async def get_vacuum_current_position(self) -> ServiceResponse:
        """Get vacuum current position (not available for Q10)."""
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="command_not_supported",
        )

    async def async_set_vacuum_goto_position(
        self, x: int, y: int, **kwargs: Any
    ) -> None:
        """Set vacuum goto position (not available for Q10)."""
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="command_not_supported",
        )

    async def async_set_fan_speed(self, fan_speed: str, **kwargs: Any) -> None:
        """Set vacuum fan speed."""
        try:
            fan_level = YXFanLevel.from_value(fan_speed)
            await self.coordinator.api.command.send(
                command=B01_Q10_DP.FAN_LEVEL,
                params=fan_level.code,
            )
        except RoborockException as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_failed",
                translation_placeholders={
                    "command": "set_fan_speed",
                },
            ) from err
        await self.coordinator.async_refresh()

    async def async_send_command(
        self,
        command: str,
        params: dict[str, Any] | list[Any] | None = None,
        **kwargs: Any,
    ) -> None:
        """Send a command to a vacuum cleaner (not supported for Q10)."""
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="command_not_supported",
        )
