"""Support for Tuya Alarm."""
from __future__ import annotations

from dataclasses import dataclass

from tuya_iot import TuyaDevice, TuyaDeviceManager

from homeassistant.components.alarm_control_panel import (
    SUPPORT_ALARM_ARM_AWAY,
    SUPPORT_ALARM_ARM_HOME,
    SUPPORT_ALARM_TRIGGER,
    AlarmControlPanelEntity,
    AlarmControlPanelEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_DISARMED,
    STATE_ALARM_TRIGGERED,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HomeAssistantTuyaData
from .base import TuyaEntity
from .const import DOMAIN, TUYA_DISCOVERY_NEW, DPCode

ICON = "mdi:security"

MODE_ALARM_ARM = "arm"
MODE_ALARM_DISARMED = "disarmed"
MODE_ALARM_HOME = "home"
MODE_ALARM_SOS = "sos"


@dataclass
class TuyaAlarmControlPanelEntityDescription(AlarmControlPanelEntityDescription):
    """Describe an Tuya Alarm entity."""


# All descriptions can be found here:
# https://developer.tuya.com/en/docs/iot/standarddescription?id=K9i5ql6waswzq
ALARM: dict[str, tuple[TuyaAlarmControlPanelEntityDescription, ...]] = {
    # Alarm Host
    # https://developer.tuya.com/en/docs/iot/categorymal?id=Kaiuz33clqxaf
    "mal": (
        TuyaAlarmControlPanelEntityDescription(
            key=DPCode.ALARM_MODE,
            name="Alarm",
        ),
    )
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Tuya alarm dynamically through Tuya discovery."""
    hass_data: HomeAssistantTuyaData = hass.data[DOMAIN][entry.entry_id]

    @callback
    def async_discover_device(device_ids: list[str]) -> None:
        """Discover and add a discovered Tuya siren."""
        entities: list[TuyaAlarmEntity] = []
        for device_id in device_ids:
            device = hass_data.device_manager.device_map[device_id]
            if descriptions := ALARM.get(device.category):
                for description in descriptions:
                    if (
                        description.key in device.function
                        or description.key in device.status
                    ):
                        entities.append(
                            TuyaAlarmEntity(
                                device, hass_data.device_manager, description
                            )
                        )
        async_add_entities(entities)

    async_discover_device([*hass_data.device_manager.device_map])

    entry.async_on_unload(
        async_dispatcher_connect(hass, TUYA_DISCOVERY_NEW, async_discover_device)
    )


class TuyaAlarmEntity(TuyaEntity, AlarmControlPanelEntity):
    """Tuya Alarm Entity."""

    _attr_supported_features = (
        SUPPORT_ALARM_ARM_HOME | SUPPORT_ALARM_ARM_AWAY | SUPPORT_ALARM_TRIGGER
    )

    def __init__(
        self,
        device: TuyaDevice,
        device_manager: TuyaDeviceManager,
        description: TuyaAlarmControlPanelEntityDescription,
    ) -> None:
        """Init Tuya Alarm."""
        super().__init__(device, device_manager)
        self.entity_description = description
        self._attr_unique_id = f"{super().unique_id}{description.key}"

    @property
    def state(self):
        """Return the state of the device."""
        status = self.device.status.get(DPCode.ALARM_MODE)

        if status == MODE_ALARM_DISARMED:
            state = STATE_ALARM_DISARMED
        elif status == MODE_ALARM_ARM:
            state = STATE_ALARM_ARMED_AWAY
        elif status == MODE_ALARM_HOME:
            state = STATE_ALARM_ARMED_HOME
        elif status == MODE_ALARM_SOS:
            state = STATE_ALARM_TRIGGERED
        else:
            state = None
        return state

    def alarm_disarm(self, code: str | None = None) -> None:
        """Send Disarm command."""
        self._send_command([{"code": DPCode.ALARM_MODE, "value": MODE_ALARM_DISARMED}])

    def alarm_arm_home(self, code: str | None = None) -> None:
        """Send Home command."""
        self._send_command([{"code": DPCode.ALARM_MODE, "value": MODE_ALARM_HOME}])

    def alarm_arm_away(self, code: str | None = None) -> None:
        """Send Arm command."""
        self._send_command([{"code": DPCode.ALARM_MODE, "value": MODE_ALARM_ARM}])

    def alarm_trigger(self, code: str | None = None) -> None:
        """Send SOS command."""
        self._send_command([{"code": DPCode.ALARM_MODE, "value": MODE_ALARM_SOS}])
