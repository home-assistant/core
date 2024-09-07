"""Support for SwitchBot vacuum."""

from typing import Any

from switchbot_api import Device, Remote, SwitchBotAPI, VacuumCommands

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
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SwitchbotCloudData
from .const import DOMAIN
from .coordinator import SwitchBotCoordinator
from .entity import SwitchBotCloudEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SwitchBot Cloud entry."""
    data: SwitchbotCloudData = hass.data[DOMAIN][config.entry_id]
    async_add_entities(
        _async_make_entity(data.api, device, coordinator)
        for device, coordinator in data.devices.vacuums
    )


# vacuum state / workingStatus
# "StandBy": "Stand by",
# "Clearing": "Clearing",
# "Paused": "Paused",
# "GotoChargeBase": "Go to charge base",
# "Charging": "Charging",
# "ChargeDone": "Charge done",
# "Dormant": "Dormant",
# "InTrouble": "In trouble",
# "InRemoteControl": "In remote control",
# "InDustCollecting": "In dust collecting"

# fan speed
# "0": "Quiet",
# "1": "Standard",
# "2": "Strong",
# "3": "MAX"
VACUUM_SWITCHBOT_STATE_TO_HA_STATE: dict[str, str] = {
    "StandBy": STATE_IDLE,
    "Clearing": STATE_CLEANING,
    "Paused": STATE_PAUSED,
    "GotoChargeBase": STATE_RETURNING,
    "Charging": STATE_DOCKED,
    "ChargeDone": STATE_DOCKED,
    "Dormant": STATE_IDLE,
    "InTrouble": STATE_ERROR,
    "InRemoteControl": STATE_CLEANING,
    "InDustCollecting": STATE_DOCKED,
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
    _attr_fan_speed_list: list[str] = ["quiet", "standard", "strong", "max"]

    async def async_set_fan_speed(self, fan_speed: str, **kwargs: Any) -> None:
        """Set fan speed."""
        if fan_speed in self._attr_fan_speed_list:
            self._attr_fan_speed = fan_speed
            await self.send_api_command(
                VacuumCommands.POW_LEVEL,
                parameters=str(self._attr_fan_speed_list.index(fan_speed)),
            )
            self.async_write_ha_state()

    async def async_pause(self) -> None:
        """Pause the cleaning task."""
        await self.send_api_command(VacuumCommands.STOP)

    async def async_return_to_base(self, **kwargs: Any) -> None:
        """Set the vacuum cleaner to return to the dock."""
        await self.send_api_command(VacuumCommands.DOCK)

    async def async_start(self) -> None:
        """Start or resume the cleaning task."""
        await self.send_api_command(VacuumCommands.START)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if not self.coordinator.data:
            return

        # 'deviceId' | 'deviceMac': 'XXXXX'
        # 'deviceType': 'K10+' | 'WoSweeperMini'
        # 'workingStatus': 'ChargeDone' | 'Charging' | 'GotoChargeBase' | 'Clearing' | 'Paused' | ...
        # 'onlineStatus': 'online'
        # 'battery': 100
        self._attr_battery_level = self.coordinator.data.get("battery")
        self._attr_available = self.coordinator.data.get("onlineStatus") == "online"

        switchbot_state = self.coordinator.data.get("workingStatus")
        if switchbot_state in VACUUM_SWITCHBOT_STATE_TO_HA_STATE:
            self._attr_state = VACUUM_SWITCHBOT_STATE_TO_HA_STATE[switchbot_state]

        self.async_write_ha_state()


@callback
def _async_make_entity(
    api: SwitchBotAPI, device: Device | Remote, coordinator: SwitchBotCoordinator
) -> SwitchBotCloudVacuum:
    """Make a SwitchBotCloudVacuum."""
    return SwitchBotCloudVacuum(api, device, coordinator)
