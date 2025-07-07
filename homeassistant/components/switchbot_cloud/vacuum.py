"""Support for SwitchBot vacuum."""

from typing import Any

from switchbot_api import (
    Device,
    Remote,
    SwitchBotAPI,
    VacuumCleanerV2Commands,
    VacuumCleanerV3Commands,
    VacuumCleanMode,
    VacuumCommands,
)

from homeassistant.components.vacuum import (
    StateVacuumEntity,
    VacuumActivity,
    VacuumEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SwitchbotCloudData
from .const import (
    DOMAIN,
    VACUUM_FAN_SPEED_MAX,
    VACUUM_FAN_SPEED_QUIET,
    VACUUM_FAN_SPEED_STANDARD,
    VACUUM_FAN_SPEED_STRONG,
)
from .coordinator import SwitchBotCoordinator
from .entity import SwitchBotCloudEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up SwitchBot Cloud entry."""
    data: SwitchbotCloudData = hass.data[DOMAIN][config.entry_id]
    async_add_entities(
        _async_make_entity(data.api, device, coordinator)
        for device, coordinator in data.devices.vacuums
    )


VACUUM_SWITCHBOT_STATE_TO_HA_STATE: dict[str, VacuumActivity] = {
    "StandBy": VacuumActivity.IDLE,
    "Clearing": VacuumActivity.CLEANING,
    "Paused": VacuumActivity.PAUSED,
    "GotoChargeBase": VacuumActivity.RETURNING,
    "Charging": VacuumActivity.DOCKED,
    "ChargeDone": VacuumActivity.DOCKED,
    "Dormant": VacuumActivity.IDLE,
    "InTrouble": VacuumActivity.ERROR,
    "InRemoteControl": VacuumActivity.CLEANING,
    "InDustCollecting": VacuumActivity.DOCKED,
}

VACUUM_FAN_SPEED_TO_SWITCHBOT_FAN_SPEED: dict[str, str] = {
    VACUUM_FAN_SPEED_QUIET: "0",
    VACUUM_FAN_SPEED_STANDARD: "1",
    VACUUM_FAN_SPEED_STRONG: "2",
    VACUUM_FAN_SPEED_MAX: "3",
}


# https://github.com/OpenWonderLabs/SwitchBotAPI?tab=readme-ov-file#robot-vacuum-cleaner-s1-plus-1
class SwitchBotCloudVacuum(SwitchBotCloudEntity, StateVacuumEntity):
    """Representation of a SwitchBot vacuum."""

    _attr_supported_features: VacuumEntityFeature = (
        VacuumEntityFeature.BATTERY
        | VacuumEntityFeature.FAN_SPEED
        | VacuumEntityFeature.PAUSE
        | VacuumEntityFeature.RETURN_HOME
        | VacuumEntityFeature.START
        | VacuumEntityFeature.STATE
    )

    _attr_name = None
    _attr_fan_speed_list: list[str] = list(
        VACUUM_FAN_SPEED_TO_SWITCHBOT_FAN_SPEED.keys()
    )

    def __init__(
        self,
        api: SwitchBotAPI,
        device: Device | Remote,
        coordinator: SwitchBotCoordinator,
    ) -> None:
        """Init SwitchBotCloudVacuum."""
        super().__init__(api, device, coordinator)
        self._attr_model_name: str | None = (
            self.device_info.get("model") if self.device_info else None
        )

    async def async_set_fan_speed(self, fan_speed: str, **kwargs: Any) -> None:
        """Set fan speed."""
        self._attr_fan_speed = fan_speed
        if (
            self._attr_model_name is not None
            and fan_speed in VACUUM_FAN_SPEED_TO_SWITCHBOT_FAN_SPEED
        ):
            if self._attr_model_name in VacuumCleanerV2Commands.get_supported_devices():
                await self.send_api_command(
                    VacuumCleanerV2Commands.CHANGE_PARAM,
                    parameters={
                        "fanLevel": int(
                            VACUUM_FAN_SPEED_TO_SWITCHBOT_FAN_SPEED[fan_speed]
                        )
                        + 1,
                        "waterLevel": 1,
                        "times": 1,
                    },
                )
            elif (
                self._attr_model_name in VacuumCleanerV3Commands.get_supported_devices()
            ):
                await self.send_api_command(
                    VacuumCleanerV3Commands.CHANGE_PARAM,
                    parameters={
                        "fanLevel": int(
                            VACUUM_FAN_SPEED_TO_SWITCHBOT_FAN_SPEED[fan_speed]
                        )
                        + 1,
                        "waterLevel": 1,
                        "times": 1,
                    },
                )
            elif self._attr_model_name in VacuumCommands.get_supported_devices():
                await self.send_api_command(
                    VacuumCommands.POW_LEVEL,
                    parameters=VACUUM_FAN_SPEED_TO_SWITCHBOT_FAN_SPEED[fan_speed],
                )
            else:
                pass
        self.async_write_ha_state()

    async def async_pause(self) -> None:
        """Pause the cleaning task."""
        if self._attr_model_name is not None:
            if self._attr_model_name in VacuumCleanerV2Commands.get_supported_devices():
                await self.send_api_command(VacuumCleanerV2Commands.PAUSE)

            elif (
                self._attr_model_name in VacuumCleanerV3Commands.get_supported_devices()
            ):
                await self.send_api_command(VacuumCleanerV3Commands.PAUSE)

            elif self._attr_model_name in VacuumCommands.get_supported_devices():
                await self.send_api_command(VacuumCommands.STOP)
            else:
                pass

    async def async_return_to_base(self, **kwargs: Any) -> None:
        """Set the vacuum cleaner to return to the dock."""
        if self._attr_model_name is not None:
            if self._attr_model_name in VacuumCleanerV2Commands.get_supported_devices():
                await self.send_api_command(VacuumCleanerV2Commands.DOCK)

            elif (
                self._attr_model_name in VacuumCleanerV3Commands.get_supported_devices()
            ):
                await self.send_api_command(VacuumCleanerV3Commands.DOCK)

            elif self._attr_model_name in VacuumCommands.get_supported_devices():
                await self.send_api_command(VacuumCommands.DOCK)
            else:
                pass

    async def async_start(self) -> None:
        """Start or resume the cleaning task."""

        assert self.fan_speed in VACUUM_FAN_SPEED_TO_SWITCHBOT_FAN_SPEED
        if self._attr_model_name is not None:
            if self._attr_model_name in VacuumCleanerV2Commands.get_supported_devices():
                command_param = {
                    "action": VacuumCleanMode.SWEEP.value,
                    "param": {
                        "fanLevel": int(
                            VACUUM_FAN_SPEED_TO_SWITCHBOT_FAN_SPEED[self.fan_speed]
                        )
                        + 1,
                        "times": 1,
                    },
                }
                await self.send_api_command(
                    VacuumCleanerV2Commands.START_CLEAN,
                    parameters=command_param,
                )
            elif (
                self._attr_model_name in VacuumCleanerV3Commands.get_supported_devices()
            ):
                command_param = {
                    "action": VacuumCleanMode.SWEEP.value,
                    "param": {
                        "fanLevel": int(
                            VACUUM_FAN_SPEED_TO_SWITCHBOT_FAN_SPEED[self.fan_speed]
                        )
                        + 1,
                        "waterLevel": 1,
                        "times": 1,
                    },
                }
                await self.send_api_command(
                    VacuumCleanerV3Commands.START_CLEAN,
                    parameters=command_param,
                )
            elif self._attr_model_name in VacuumCommands.get_supported_devices():
                await self.send_api_command(VacuumCommands.START)
            else:
                pass

    def _set_attributes(self) -> None:
        """Set attributes from coordinator data."""
        if not self.coordinator.data:
            return

        self._attr_battery_level = self.coordinator.data.get("battery")
        self._attr_available = self.coordinator.data.get("onlineStatus") == "online"

        switchbot_state = str(self.coordinator.data.get("workingStatus"))
        self._attr_activity = VACUUM_SWITCHBOT_STATE_TO_HA_STATE.get(switchbot_state)

        if self._attr_fan_speed is None:
            self._attr_fan_speed = VACUUM_FAN_SPEED_QUIET


@callback
def _async_make_entity(
    api: SwitchBotAPI, device: Device | Remote, coordinator: SwitchBotCoordinator
) -> SwitchBotCloudVacuum:
    """Make a SwitchBotCloudVacuum."""
    return SwitchBotCloudVacuum(api, device, coordinator)
