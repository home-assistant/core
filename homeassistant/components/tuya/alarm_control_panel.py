"""Support for Tuya Alarm."""

from __future__ import annotations

from enum import StrEnum

from base64 import b64decode

from tuya_sharing import CustomerDevice, Manager

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityDescription,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import TuyaConfigEntry
from .const import TUYA_DISCOVERY_NEW, DPCode, DPType
from .entity import TuyaEntity


class Mode(StrEnum):
    """Alarm modes."""

    ARM = "arm"
    DISARMED = "disarmed"
    HOME = "home"
    SOS = "sos"

class State(StrEnum):
    """Alarm states."""

    NORMAL = "normal"
    ALARM = "alarm"

STATE_MAPPING: dict[str, AlarmControlPanelState] = {
    Mode.DISARMED: AlarmControlPanelState.DISARMED,
    Mode.ARM: AlarmControlPanelState.ARMED_AWAY,
    Mode.HOME: AlarmControlPanelState.ARMED_HOME,
    Mode.SOS: AlarmControlPanelState.TRIGGERED,
}


# All descriptions can be found here:
# https://developer.tuya.com/en/docs/iot/standarddescription?id=K9i5ql6waswzq
ALARM: dict[str, tuple[AlarmControlPanelEntityDescription, ...]] = {
    # Alarm Host
    # https://developer.tuya.com/en/docs/iot/categorymal?id=Kaiuz33clqxaf
    "mal": (
        AlarmControlPanelEntityDescription(
            key=DPCode.MASTER_MODE,
            name="Alarm",
        ),
    )
}


async def async_setup_entry(
    hass: HomeAssistant, entry: TuyaConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Tuya alarm dynamically through Tuya discovery."""
    hass_data = entry.runtime_data

    @callback
    def async_discover_device(device_ids: list[str]) -> None:
        """Discover and add a discovered Tuya siren."""
        entities: list[TuyaAlarmEntity] = []
        for device_id in device_ids:
            device = hass_data.manager.device_map[device_id]
            if descriptions := ALARM.get(device.category):
                entities.extend(
                    TuyaAlarmEntity(device, hass_data.manager, description)
                    for description in descriptions
                    if description.key in device.status
                )
        async_add_entities(entities)

    async_discover_device([*hass_data.manager.device_map])

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
    ) -> None:
        """Init Tuya Alarm."""
        super().__init__(device, device_manager)
        self.entity_description = description
        self._attr_unique_id = f"{super().unique_id}{description.key}"

        # Determine supported  modes
        if supported_modes := self.find_dpcode(
            description.key, dptype=DPType.ENUM, prefer_function=True
        ):
            if Mode.HOME in supported_modes.range:
                self._attr_supported_features |= AlarmControlPanelEntityFeature.ARM_HOME

            if Mode.ARM in supported_modes.range:
                self._attr_supported_features |= AlarmControlPanelEntityFeature.ARM_AWAY

            if Mode.SOS in supported_modes.range:
                self._attr_supported_features |= AlarmControlPanelEntityFeature.TRIGGER

    @property
    def alarm_state(self) -> AlarmControlPanelState | None:
        """Return the state of the device."""
        mode = self.device.status.get(DPCode.MASTER_MODE)
        state = self.device.status.get(DPCode.MASTER_STATE)
        # When the alarm is triggered, only its 'state' is changing. From 'normal' to 'alarm'.
        # The 'mode' doesn't change, and stays as 'arm' or 'home'.
        if state == State.ALARM:
            return AlarmControlPanelState.TRIGGERED
        return STATE_MAPPING.get(mode)

    @property
    def changed_by(self) -> str | None:
        """Last change triggered by."""
        state = self.device.status.get(DPCode.MASTER_STATE)
        if state == State.ALARM:            
            encoded_msg = self.device.status.get(DPCode.ALARM_MSG)
            if encoded_msg:
                return b64decode(encoded_msg).decode('utf-16be')
        return None

    def alarm_disarm(self, code: str | None = None) -> None:
        """Send Disarm command."""
        self._send_command(
            [{"code": self.entity_description.key, "value": Mode.DISARMED}]
        )

    def alarm_arm_home(self, code: str | None = None) -> None:
        """Send Home command."""
        self._send_command([{"code": self.entity_description.key, "value": Mode.HOME}])

    def alarm_arm_away(self, code: str | None = None) -> None:
        """Send Arm command."""
        self._send_command([{"code": self.entity_description.key, "value": Mode.ARM}])

    def alarm_trigger(self, code: str | None = None) -> None:
        """Send SOS command."""
        self._send_command([{"code": self.entity_description.key, "value": Mode.SOS}])
