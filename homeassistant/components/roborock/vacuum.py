"""Support for Roborock vacuum class."""
from typing import Any

from roborock.code_mappings import RoborockStateCode
from roborock.roborock_message import RoborockDataProtocol
from roborock.roborock_typing import RoborockCommand

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
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify

from .const import DOMAIN
from .coordinator import RoborockDataUpdateCoordinator
from .device import RoborockCoordinatedEntity

STATE_CODE_TO_STATE = {
    RoborockStateCode.starting: STATE_IDLE,  # "Starting"
    RoborockStateCode.charger_disconnected: STATE_IDLE,  # "Charger disconnected"
    RoborockStateCode.idle: STATE_IDLE,  # "Idle"
    RoborockStateCode.remote_control_active: STATE_CLEANING,  # "Remote control active"
    RoborockStateCode.cleaning: STATE_CLEANING,  # "Cleaning"
    RoborockStateCode.returning_home: STATE_RETURNING,  # "Returning home"
    RoborockStateCode.manual_mode: STATE_CLEANING,  # "Manual mode"
    RoborockStateCode.charging: STATE_DOCKED,  # "Charging"
    RoborockStateCode.charging_problem: STATE_ERROR,  # "Charging problem"
    RoborockStateCode.paused: STATE_PAUSED,  # "Paused"
    RoborockStateCode.spot_cleaning: STATE_CLEANING,  # "Spot cleaning"
    RoborockStateCode.error: STATE_ERROR,  # "Error"
    RoborockStateCode.shutting_down: STATE_IDLE,  # "Shutting down"
    RoborockStateCode.updating: STATE_DOCKED,  # "Updating"
    RoborockStateCode.docking: STATE_RETURNING,  # "Docking"
    RoborockStateCode.going_to_target: STATE_CLEANING,  # "Going to target"
    RoborockStateCode.zoned_cleaning: STATE_CLEANING,  # "Zoned cleaning"
    RoborockStateCode.segment_cleaning: STATE_CLEANING,  # "Segment cleaning"
    RoborockStateCode.emptying_the_bin: STATE_DOCKED,  # "Emptying the bin" on s7+
    RoborockStateCode.washing_the_mop: STATE_DOCKED,  # "Washing the mop" on s7maxV
    RoborockStateCode.going_to_wash_the_mop: STATE_RETURNING,  # "Going to wash the mop" on s7maxV
    RoborockStateCode.charging_complete: STATE_DOCKED,  # "Charging complete"
    RoborockStateCode.device_offline: STATE_ERROR,  # "Device offline"
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Roborock sensor."""
    coordinators: dict[str, RoborockDataUpdateCoordinator] = hass.data[DOMAIN][
        config_entry.entry_id
    ]
    async_add_entities(
        RoborockVacuum(slugify(device_id), coordinator)
        for device_id, coordinator in coordinators.items()
    )


class RoborockVacuum(RoborockCoordinatedEntity, StateVacuumEntity):
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
        unique_id: str,
        coordinator: RoborockDataUpdateCoordinator,
    ) -> None:
        """Initialize a vacuum."""
        StateVacuumEntity.__init__(self)
        RoborockCoordinatedEntity.__init__(self, unique_id, coordinator)
        self._attr_fan_speed_list = self._device_status.fan_power_options
        self.api.add_listener(
            RoborockDataProtocol.FAN_POWER, self._update_from_listener, self.api.cache
        )
        self.api.add_listener(
            RoborockDataProtocol.STATE, self._update_from_listener, self.api.cache
        )

    @property
    def state(self) -> str | None:
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

    async def async_send_command(
        self,
        command: str,
        params: dict[str, Any] | list[Any] | None = None,
        **kwargs: Any,
    ) -> None:
        """Send a command to a vacuum cleaner."""
        await self.send(command, params)
