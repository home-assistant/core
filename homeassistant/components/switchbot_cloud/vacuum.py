"""Support for SwitchBot vacuum."""

from typing import Any

from switchbot_api import Device, Remote, SwitchBotAPI, VacuumCommands

from homeassistant.components.vacuum import StateVacuumEntity, VacuumEntityFeature
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


# GET /v1.1/devices/{deviceId}/status
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
    _attr_fan_speed_list: list[str] = ["1", "2", "3", "4"]

    async def async_set_fan_speed(self, fan_speed: str, **kwargs: Any) -> None:
        """Set fan speed."""
        self._attr_fan_speed = fan_speed
        await self.send_api_command(
            VacuumCommands.POW_LEVEL,
            parameters=fan_speed,
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
        self._attr_state = self.coordinator.data.get("workingStatus")
        self.async_write_ha_state()


@callback
def _async_make_entity(
    api: SwitchBotAPI, device: Device | Remote, coordinator: SwitchBotCoordinator
) -> SwitchBotCloudVacuum:
    """Make a SwitchBotCloudVacuum."""
    if device.device_type in ["K10+"]:
        return SwitchBotCloudVacuum(api, device, coordinator)

    raise NotImplementedError(f"Unsupported device type: {device.device_type}")
