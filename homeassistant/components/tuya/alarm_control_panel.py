"""Support for Tuya Alarm."""
from __future__ import annotations

from tuya_iot import TuyaDevice, TuyaDeviceManager

from homeassistant.backports.enum import StrEnum
from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityDescription,
    AlarmControlPanelEntityFeature,
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
from .const import DOMAIN, TUYA_DISCOVERY_NEW, DPCode, DPType


class Mode(StrEnum):
    """Alarm modes."""

    ARM = "arm"
    DISARMED = "disarmed"
    HOME = "home"
    SOS = "sos"


STATE_MAPPING: dict[str, str] = {
    Mode.DISARMED: STATE_ALARM_DISARMED,
    Mode.ARM: STATE_ALARM_ARMED_AWAY,
    Mode.HOME: STATE_ALARM_ARMED_HOME,
    Mode.SOS: STATE_ALARM_TRIGGERED,
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
                    if description.key in device.status:
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

    _attr_icon = "mdi:security"

    def __init__(
        self,
        device: TuyaDevice,
        device_manager: TuyaDeviceManager,
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
    def state(self) -> str | None:
        """Return the state of the device."""
        if not (status := self.device.status.get(self.entity_description.key)):
            return None
        return STATE_MAPPING.get(status)

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
