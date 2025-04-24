"""Support for Roborock vacuum class."""

from typing import Any

from roborock.code_mappings import RoborockStateCode
from roborock.roborock_message import RoborockDataProtocol
from roborock.roborock_typing import RoborockCommand
from vacuum_map_parser_base.config.color import ColorsPalette
from vacuum_map_parser_base.config.image_config import ImageConfig
from vacuum_map_parser_base.config.size import Sizes
from vacuum_map_parser_roborock.map_data_parser import RoborockMapDataParser
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

from .const import (
    DOMAIN,
    GET_MAPS_SERVICE_NAME,
    GET_VACUUM_CURRENT_POSITION_SERVICE_NAME,
    SET_VACUUM_GOTO_POSITION_SERVICE_NAME,
)
from .coordinator import RoborockConfigEntry, RoborockDataUpdateCoordinator
from .entity import RoborockCoordinatedEntityV1

STATE_CODE_TO_STATE = {
    RoborockStateCode.starting: VacuumActivity.IDLE,  # "Starting"
    RoborockStateCode.charger_disconnected: VacuumActivity.IDLE,  # "Charger disconnected"
    RoborockStateCode.idle: VacuumActivity.IDLE,  # "Idle"
    RoborockStateCode.remote_control_active: VacuumActivity.CLEANING,  # "Remote control active"
    RoborockStateCode.cleaning: VacuumActivity.CLEANING,  # "Cleaning"
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

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: RoborockConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Roborock sensor."""
    async_add_entities(
        RoborockVacuum(coordinator)
        for coordinator in config_entry.runtime_data.v1
        if isinstance(coordinator, RoborockDataUpdateCoordinator)
    )

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


class RoborockVacuum(RoborockCoordinatedEntityV1, StateVacuumEntity):
    """General Representation of a Roborock vacuum."""

    _attr_icon = "mdi:robot-vacuum"
    _attr_supported_features = (
        VacuumEntityFeature.PAUSE
        | VacuumEntityFeature.STOP
        | VacuumEntityFeature.RETURN_HOME
        | VacuumEntityFeature.FAN_SPEED
        | VacuumEntityFeature.BATTERY
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
            listener_request=[
                RoborockDataProtocol.FAN_POWER,
                RoborockDataProtocol.STATE,
            ],
        )
        self._attr_fan_speed_list = self._device_status.fan_power_options

    @property
    def activity(self) -> VacuumActivity | None:
        """Return the status of the vacuum cleaner."""
        assert self._device_status.state is not None
        return STATE_CODE_TO_STATE.get(self._device_status.state)

    @property
    def battery_level(self) -> int | None:
        """Return the battery level of the vacuum cleaner."""
        return self._device_status.battery

    @property
    def fan_speed(self) -> str | None:
        """Return the fan speed of the vacuum cleaner."""
        return self._device_status.fan_power_name

    async def async_start(self) -> None:
        """Start the vacuum."""
        if self._device_status.in_cleaning == 2:
            await self.send(RoborockCommand.RESUME_ZONED_CLEAN)
        elif self._device_status.in_cleaning == 3:
            await self.send(RoborockCommand.RESUME_SEGMENT_CLEAN)
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
        return {
            "maps": [
                {
                    "flag": vacuum_map.flag,
                    "name": vacuum_map.name,
                    # JsonValueType does not accept a int as a key - was not a
                    # issue with previous asdict() implementation.
                    "rooms": vacuum_map.rooms,  # type: ignore[dict-item]
                }
                for vacuum_map in self.coordinator.maps.values()
            ]
        }

    async def get_vacuum_current_position(self) -> ServiceResponse:
        """Get the current position of the vacuum from the map."""

        map_data = await self.coordinator.cloud_api.get_map_v1()
        if not isinstance(map_data, bytes):
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="map_failure",
            )
        parser = RoborockMapDataParser(ColorsPalette(), Sizes(), [], ImageConfig(), [])
        parsed_map = parser.parse(map_data)
        robot_position = parsed_map.vacuum_position

        if robot_position is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="position_not_found"
            )

        return {
            "x": robot_position.x,
            "y": robot_position.y,
        }
