"""Support for Tuya Alarm."""

from __future__ import annotations

from typing import Any

from tuya_device_handlers.device_wrapper.alarm_control_panel import (
    AlarmChangedByWrapper,
    AlarmStateWrapper,
)
from tuya_device_handlers.device_wrapper.base import DeviceWrapper
from tuya_device_handlers.device_wrapper.common import DPCodeEnumWrapper
from tuya_device_handlers.helpers.homeassistant import TuyaAlarmControlPanelState
from tuya_device_handlers.type_information import EnumTypeInformation
from tuya_sharing import CustomerDevice, Manager

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityDescription,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import TuyaConfigEntry
from .const import TUYA_DISCOVERY_NEW, DeviceCategory, DPCode
from .entity import TuyaEntity

ALARM: dict[DeviceCategory, tuple[AlarmControlPanelEntityDescription, ...]] = {
    DeviceCategory.MAL: (
        AlarmControlPanelEntityDescription(
            key=DPCode.MASTER_MODE,
            name="Alarm",
        ),
    )
}

_TUYA_TO_HA_STATE_MAPPINGS: dict[
    TuyaAlarmControlPanelState | None, AlarmControlPanelState | None
] = {
    None: None,
    TuyaAlarmControlPanelState.DISARMED: AlarmControlPanelState.DISARMED,
    TuyaAlarmControlPanelState.ARMED_HOME: AlarmControlPanelState.ARMED_HOME,
    TuyaAlarmControlPanelState.ARMED_AWAY: AlarmControlPanelState.ARMED_AWAY,
    TuyaAlarmControlPanelState.ARMED_NIGHT: AlarmControlPanelState.ARMED_NIGHT,
    TuyaAlarmControlPanelState.ARMED_VACATION: AlarmControlPanelState.ARMED_VACATION,
    TuyaAlarmControlPanelState.ARMED_CUSTOM_BYPASS: AlarmControlPanelState.ARMED_CUSTOM_BYPASS,
    TuyaAlarmControlPanelState.PENDING: AlarmControlPanelState.PENDING,
    TuyaAlarmControlPanelState.ARMING: AlarmControlPanelState.ARMING,
    TuyaAlarmControlPanelState.DISARMING: AlarmControlPanelState.DISARMING,
    TuyaAlarmControlPanelState.TRIGGERED: AlarmControlPanelState.TRIGGERED,
}


class _AlarmActionWrapper(DPCodeEnumWrapper):
    """Wrapper for setting the alarm mode of a device."""

    _ACTION_MAPPINGS = {
        # Home Assistant action => Tuya device mode
        "arm_home": "home",
        "arm_away": "arm",
        "disarm": "disarmed",
        "trigger": "sos",
    }

    def __init__(self, dpcode: str, type_information: EnumTypeInformation) -> None:
        """Init _AlarmActionWrapper."""
        super().__init__(dpcode, type_information)
        self.options = [
            ha_action
            for ha_action, tuya_action in self._ACTION_MAPPINGS.items()
            if tuya_action in type_information.range
        ]

    def _convert_value_to_raw_value(self, device: CustomerDevice, value: Any) -> Any:
        """Convert value to raw value."""
        if value in self.options:
            return self._ACTION_MAPPINGS[value]
        raise ValueError(f"Unsupported value {value} for {self.dpcode}")


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TuyaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Tuya alarm dynamically through Tuya discovery."""
    manager = entry.runtime_data.manager

    @callback
    def async_discover_device(device_ids: list[str]) -> None:
        """Discover and add a discovered Tuya siren."""
        entities: list[TuyaAlarmEntity] = []
        for device_id in device_ids:
            device = manager.device_map[device_id]
            if descriptions := ALARM.get(device.category):
                entities.extend(
                    TuyaAlarmEntity(
                        device,
                        manager,
                        description,
                        action_wrapper=_AlarmActionWrapper(
                            master_mode.dpcode, master_mode
                        ),
                        changed_by_wrapper=AlarmChangedByWrapper.find_dpcode(
                            device, DPCode.ALARM_MSG
                        ),
                        state_wrapper=AlarmStateWrapper(
                            master_mode.dpcode, master_mode
                        ),
                    )
                    for description in descriptions
                    if (
                        master_mode := EnumTypeInformation.find_dpcode(
                            device, DPCode.MASTER_MODE, prefer_function=True
                        )
                    )
                )
        async_add_entities(entities)

    async_discover_device([*manager.device_map])

    entry.async_on_unload(
        async_dispatcher_connect(hass, TUYA_DISCOVERY_NEW, async_discover_device)
    )


class TuyaAlarmEntity(TuyaEntity, AlarmControlPanelEntity):
    """Tuya Alarm Entity."""

    _attr_name = None
    _attr_code_arm_required = False

    def __init__(
        self,
        device: CustomerDevice,
        device_manager: Manager,
        description: AlarmControlPanelEntityDescription,
        *,
        action_wrapper: DeviceWrapper[str],
        changed_by_wrapper: DeviceWrapper[str] | None,
        state_wrapper: DeviceWrapper[TuyaAlarmControlPanelState],
    ) -> None:
        """Init Tuya Alarm."""
        super().__init__(device, device_manager)
        self.entity_description = description
        self._attr_unique_id = f"{super().unique_id}{description.key}"
        self._action_wrapper = action_wrapper
        self._changed_by_wrapper = changed_by_wrapper
        self._state_wrapper = state_wrapper

        # Determine supported modes
        if "arm_home" in action_wrapper.options:
            self._attr_supported_features |= AlarmControlPanelEntityFeature.ARM_HOME
        if "arm_away" in action_wrapper.options:
            self._attr_supported_features |= AlarmControlPanelEntityFeature.ARM_AWAY
        if "trigger" in action_wrapper.options:
            self._attr_supported_features |= AlarmControlPanelEntityFeature.TRIGGER

    @property
    def alarm_state(self) -> AlarmControlPanelState | None:
        """Return the state of the device."""
        return _TUYA_TO_HA_STATE_MAPPINGS.get(self._read_wrapper(self._state_wrapper))

    @property
    def changed_by(self) -> str | None:
        """Last change triggered by."""
        return self._read_wrapper(self._changed_by_wrapper)

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Send Disarm command."""
        await self._async_send_wrapper_updates(self._action_wrapper, "disarm")

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        """Send Home command."""
        await self._async_send_wrapper_updates(self._action_wrapper, "arm_home")

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Send Arm command."""
        await self._async_send_wrapper_updates(self._action_wrapper, "arm_away")

    async def async_alarm_trigger(self, code: str | None = None) -> None:
        """Send SOS command."""
        await self._async_send_wrapper_updates(self._action_wrapper, "trigger")
