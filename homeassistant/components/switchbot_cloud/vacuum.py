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

    # "K10+"
    # "K10+ Pro"
    # "Robot Vacuum Cleaner S1"
    # "Robot Vacuum Cleaner S1 Plus"

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

    async def async_set_fan_speed(self, fan_speed: str, **kwargs: Any) -> None:
        """Set fan speed."""
        self._attr_fan_speed = fan_speed
        if fan_speed in VACUUM_FAN_SPEED_TO_SWITCHBOT_FAN_SPEED:
            await self.send_api_command(
                VacuumCommands.POW_LEVEL,
                parameters=VACUUM_FAN_SPEED_TO_SWITCHBOT_FAN_SPEED[fan_speed],
            )
            await self.coordinator.async_request_refresh()

    async def async_pause(self) -> None:
        """Pause the cleaning task."""
        await self.send_api_command(VacuumCommands.STOP)
        self.async_write_ha_state()

    async def async_return_to_base(self, **kwargs: Any) -> None:
        """Set the vacuum cleaner to return to the dock."""
        await self.send_api_command(VacuumCommands.DOCK)
        await self.coordinator.async_request_refresh()

    async def async_start(self) -> None:
        """Start or resume the cleaning task."""
        await self.send_api_command(VacuumCommands.START)
        await self.coordinator.async_request_refresh()

    def _set_attributes(self) -> None:
        """Set attributes from coordinator data."""
        if self.coordinator.data is None:
            return

        self._attr_battery_level = self.coordinator.data.get("battery")
        self._attr_available = self.coordinator.data.get("onlineStatus") == "online"

        switchbot_state = str(self.coordinator.data.get("workingStatus"))
        self._attr_activity = VACUUM_SWITCHBOT_STATE_TO_HA_STATE.get(switchbot_state)
        if self._attr_fan_speed is None:
            self._attr_fan_speed = VACUUM_FAN_SPEED_QUIET


class SwitchBotCloudVacuumK20PlusPro(SwitchBotCloudVacuum):
    """Representation of a SwitchBot K20+ Pro."""

    async def async_set_fan_speed(self, fan_speed: str, **kwargs: Any) -> None:
        """Set fan speed."""
        self._attr_fan_speed = fan_speed
        await self.send_api_command(
            VacuumCleanerV2Commands.CHANGE_PARAM,
            parameters={
                "fanLevel": int(VACUUM_FAN_SPEED_TO_SWITCHBOT_FAN_SPEED[fan_speed]) + 1,
                "waterLevel": 1,
                "times": 1,
            },
        )
        await self.coordinator.async_request_refresh()

    async def async_pause(self) -> None:
        """Pause the cleaning task."""
        await self.send_api_command(VacuumCleanerV2Commands.PAUSE)
        await self.coordinator.async_request_refresh()

    async def async_return_to_base(self, **kwargs: Any) -> None:
        """Set the vacuum cleaner to return to the dock."""
        await self.send_api_command(VacuumCleanerV2Commands.DOCK)
        await self.coordinator.async_request_refresh()

    async def async_start(self) -> None:
        """Start or resume the cleaning task."""
        fan_level = (
            VACUUM_FAN_SPEED_TO_SWITCHBOT_FAN_SPEED.get(self.fan_speed)
            if self.fan_speed
            else None
        )
        await self.send_api_command(
            VacuumCleanerV2Commands.START_CLEAN,
            parameters={
                "action": VacuumCleanMode.SWEEP.value,
                "param": {
                    "fanLevel": int(fan_level if fan_level else VACUUM_FAN_SPEED_QUIET)
                    + 1,
                    "times": 1,
                },
            },
        )
        await self.coordinator.async_request_refresh()


class SwitchBotCloudVacuumK10PlusProCombo(SwitchBotCloudVacuumK20PlusPro):
    """Representation of a SwitchBot vacuum K10+ Pro Combo."""

    async def async_set_fan_speed(self, fan_speed: str, **kwargs: Any) -> None:
        """Set fan speed."""
        self._attr_fan_speed = fan_speed
        if fan_speed in VACUUM_FAN_SPEED_TO_SWITCHBOT_FAN_SPEED:
            await self.send_api_command(
                VacuumCleanerV2Commands.CHANGE_PARAM,
                parameters={
                    "fanLevel": int(VACUUM_FAN_SPEED_TO_SWITCHBOT_FAN_SPEED[fan_speed])
                    + 1,
                    "times": 1,
                },
            )
        await self.coordinator.async_request_refresh()


class SwitchBotCloudVacuumV3(SwitchBotCloudVacuumK20PlusPro):
    """Representation of a SwitchBot vacuum Robot Vacuum Cleaner S10 & S20."""

    async def async_set_fan_speed(self, fan_speed: str, **kwargs: Any) -> None:
        """Set fan speed."""
        self._attr_fan_speed = fan_speed
        await self.send_api_command(
            VacuumCleanerV3Commands.CHANGE_PARAM,
            parameters={
                "fanLevel": int(VACUUM_FAN_SPEED_TO_SWITCHBOT_FAN_SPEED[fan_speed]) + 1,
                "waterLevel": 1,
                "times": 1,
            },
        )
        await self.coordinator.async_request_refresh()

    async def async_start(self) -> None:
        """Start or resume the cleaning task."""
        fan_level = (
            VACUUM_FAN_SPEED_TO_SWITCHBOT_FAN_SPEED.get(self.fan_speed)
            if self.fan_speed
            else None
        )
        await self.send_api_command(
            VacuumCleanerV3Commands.START_CLEAN,
            parameters={
                "action": VacuumCleanMode.SWEEP.value,
                "param": {
                    "fanLevel": int(fan_level if fan_level else VACUUM_FAN_SPEED_QUIET),
                    "waterLevel": 1,
                    "times": 1,
                },
            },
        )
        await self.coordinator.async_request_refresh()


@callback
def _async_make_entity(
    api: SwitchBotAPI, device: Device | Remote, coordinator: SwitchBotCoordinator
) -> (
    SwitchBotCloudVacuum
    | SwitchBotCloudVacuumK20PlusPro
    | SwitchBotCloudVacuumV3
    | SwitchBotCloudVacuumK10PlusProCombo
):
    """Make a SwitchBotCloudVacuum."""
    if device.device_type in VacuumCleanerV2Commands.get_supported_devices():
        if device.device_type == "K20+ Pro":
            return SwitchBotCloudVacuumK20PlusPro(api, device, coordinator)
        return SwitchBotCloudVacuumK10PlusProCombo(api, device, coordinator)

    if device.device_type in VacuumCleanerV3Commands.get_supported_devices():
        return SwitchBotCloudVacuumV3(api, device, coordinator)
    return SwitchBotCloudVacuum(api, device, coordinator)
