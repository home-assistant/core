"""Support for Tuya Alarm."""
from __future__ import annotations

from dataclasses import dataclass
import logging

from tuya_iot import TuyaDevice, TuyaDeviceManager

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HomeAssistantTuyaData
from .base import TuyaEntity
from .const import DOMAIN, TUYA_DISCOVERY_NEW, DPCode

_LOGGER = logging.getLogger(__name__)

ICON = "mdi:security"

SUPPORT_ALARM_ARM_HOME = 1
SUPPORT_ALARM_ARM_AWAY = 2
SUPPORT_ALARM_ARM_NIGHT = 4
SUPPORT_ALARM_TRIGGER = 8
SUPPORT_ALARM_ARM_CUSTOM_BYPASS = 16
SUPPORT_ALARM_ARM_VACATION = 32


@dataclass
class TuyaAlarmEntityDescription(AlarmControlPanelEntityDescription):
    """Describe an Tuya cover entity."""

    battery_percentage: DPCode | None = None


# All descriptions can be found here:
# https://developer.tuya.com/en/docs/iot/standarddescription?id=K9i5ql6waswzq
ALARM: dict[str, tuple[TuyaAlarmEntityDescription, ...]] = {
    # Alarm
    # https://developer.tuya.com/en/docs/iot/categorymal?id=Kaiuz33clqxaf
    "mal": (
        TuyaAlarmEntityDescription(
            key="master_mode",
            name="Alarm",
            battery_percentage=DPCode.BATTERY_PERCENTAGE,
        ),
    ),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Tuya alarm dynamically through Tuya discovery."""
    hass_data: HomeAssistantTuyaData = hass.data[DOMAIN][entry.entry_id]
    _LOGGER.info(hass_data)

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

    def __init__(
        self,
        device: TuyaDevice,
        device_manager: TuyaDeviceManager,
        description: TuyaAlarmEntityDescription,
    ) -> None:
        """Init Tuya Alarm."""
        super().__init__(device, device_manager)
        self.entity_description = description
        self._attr_unique_id = f"{super().unique_id}{description.key}"

    @property
    def state(self):
        """Return the current Alarm State."""
        return self.device.status.get(DPCode.ALARM_STATE)

    @property
    def code_format(self) -> str | None:
        """Regex for code format or None if no code is required."""
        return self._attr_code_format

    @property
    def changed_by(self) -> str | None:
        """Last change triggered by."""
        return self._attr_changed_by

    @property
    def code_arm_required(self) -> bool:
        """Whether the code is required for arm actions."""
        return self._attr_code_arm_required

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        return (
            SUPPORT_ALARM_ARM_HOME
            | SUPPORT_ALARM_ARM_AWAY
            | SUPPORT_ALARM_ARM_NIGHT
            | SUPPORT_ALARM_TRIGGER
        )

    def alarm_disarm(self, code: str | None = None) -> None:
        """Send Disarm command."""
        self._send_command(
            [{"code": DPCode.ALARM_STATE, "value": DPCode.ALARM_DISARMED}]
        )

    def alarm_arm_home(self, code: str | None = None) -> None:
        """Send Home command."""
        self._send_command([{"code": DPCode.ALARM_STATE, "value": DPCode.ALARM_HOME}])

    def alarm_arm_away(self, code: str | None = None) -> None:
        """Send Arm command."""
        self._send_command([{"code": DPCode.ALARM_STATE, "value": DPCode.ALARM_ARM}])

    def alarm_arm_night(self, code: str | None = None) -> None:
        """Send arm night command."""
        self._send_command([{"code": DPCode.ALARM_STATE, "value": DPCode.ALARM_ARM}])

    def alarm_trigger(self, code: str | None = None) -> None:
        """Send SOS command."""
        self._send_command([{"code": DPCode.ALARM_STATE, "value": DPCode.SOS}])
