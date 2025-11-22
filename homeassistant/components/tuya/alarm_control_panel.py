"""Support for Tuya Alarm."""

from __future__ import annotations

from base64 import b64decode
from typing import Any

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
from .models import DPCodeBase64Wrapper, DPCodeEnumWrapper

ALARM: dict[DeviceCategory, tuple[AlarmControlPanelEntityDescription, ...]] = {
    DeviceCategory.MAL: (
        AlarmControlPanelEntityDescription(
            key=DPCode.MASTER_MODE,
            name="Alarm",
        ),
    )
}


class _AlarmChangedByWrapper(DPCodeBase64Wrapper):
    """Wrapper for changed_by.

    Decode base64 to utf-16be string, but only if alarm has been triggered.
    """

    def read_device_status(self, device: CustomerDevice) -> str | None:
        """Read the device status."""
        if (
            device.status.get(DPCode.MASTER_STATE) != "alarm"
            or (data := self.read_bytes(device)) is None
        ):
            return None
        return data.decode("utf-16be")


class _AlarmModeWrapper(DPCodeEnumWrapper):
    """Wrapper for the alarm mode of a device.

    Handles alarm mode enum values and determines the alarm state,
    including logic for detecting when the alarm is triggered and
    distinguishing triggered state from battery warnings.
    """

    _ACTION_MAPPINGS = {
        # Home Assistant action => Tuya device mode
        "arm_home": "home",
        "arm_away": "arm",
        "disarm": "disarmed",
        "trigger": "sos",
    }
    _STATE_MAPPINGS = {
        # Tuya device mode => Home Assistant panel state
        "disarmed": AlarmControlPanelState.DISARMED,
        "arm": AlarmControlPanelState.ARMED_AWAY,
        "home": AlarmControlPanelState.ARMED_HOME,
        "sos": AlarmControlPanelState.TRIGGERED,
    }

    def read_panel_state(self, device: CustomerDevice) -> AlarmControlPanelState | None:
        """Read the device status."""
        # When the alarm is triggered, only its 'state' is changing. From 'normal' to 'alarm'.
        # The 'mode' doesn't change, and stays as 'arm' or 'home'.
        if device.status.get(DPCode.MASTER_STATE) == "alarm":
            # Only report as triggered if NOT a battery warning
            if not (
                (encoded_msg := device.status.get(DPCode.ALARM_MSG))
                and (decoded_message := b64decode(encoded_msg).decode("utf-16be"))
                and "Sensor Low Battery" in decoded_message
            ):
                return AlarmControlPanelState.TRIGGERED

        if (status := self.read_device_status(device)) is None:
            return None
        return self._STATE_MAPPINGS.get(status)

    def supports_action(self, action: str) -> bool:
        """Return if action is supported."""
        return (
            mapped_value := self._ACTION_MAPPINGS.get(action)
        ) is not None and mapped_value in self.type_information.range

    def _convert_value_to_raw_value(self, device: CustomerDevice, value: Any) -> Any:
        """Convert value to raw value."""
        if (
            mapped_value := self._ACTION_MAPPINGS.get(value)
        ) is not None and mapped_value in self.type_information.range:
            return mapped_value
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
                        mode_wrapper=mode_wrapper,
                        changed_by_wrapper=_AlarmChangedByWrapper.find_dpcode(
                            device, DPCode.ALARM_MSG
                        ),
                    )
                    for description in descriptions
                    if (
                        mode_wrapper := _AlarmModeWrapper.find_dpcode(
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
        mode_wrapper: _AlarmModeWrapper,
        changed_by_wrapper: _AlarmChangedByWrapper | None,
    ) -> None:
        """Init Tuya Alarm."""
        super().__init__(device, device_manager)
        self.entity_description = description
        self._attr_unique_id = f"{super().unique_id}{description.key}"
        self._mode_wrapper = mode_wrapper
        self._changed_by_wrapper = changed_by_wrapper

        # Determine supported modes
        if mode_wrapper.supports_action("arm_home"):
            self._attr_supported_features |= AlarmControlPanelEntityFeature.ARM_HOME
        if mode_wrapper.supports_action("arm_away"):
            self._attr_supported_features |= AlarmControlPanelEntityFeature.ARM_AWAY
        if mode_wrapper.supports_action("trigger"):
            self._attr_supported_features |= AlarmControlPanelEntityFeature.TRIGGER

    @property
    def alarm_state(self) -> AlarmControlPanelState | None:
        """Return the state of the device."""
        return self._mode_wrapper.read_panel_state(self.device)

    @property
    def changed_by(self) -> str | None:
        """Last change triggered by."""
        if self._changed_by_wrapper is None:
            return None
        return self._changed_by_wrapper.read_device_status(self.device)

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Send Disarm command."""
        await self._async_send_dpcode_update(self._mode_wrapper, "disarm")

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        """Send Home command."""
        await self._async_send_dpcode_update(self._mode_wrapper, "arm_home")

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Send Arm command."""
        await self._async_send_dpcode_update(self._mode_wrapper, "arm_away")

    async def async_alarm_trigger(self, code: str | None = None) -> None:
        """Send SOS command."""
        await self._async_send_dpcode_update(self._mode_wrapper, "trigger")
