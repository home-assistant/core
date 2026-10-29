"""Support for Tuya switches."""

from dataclasses import dataclass
from typing import Any, override

from tuya_device_handlers.definition.switch import (
    SwitchDefinition,
    get_default_definition,
)
from tuya_sharing import CustomerDevice, Manager

from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import ChildDeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.issue_registry import (
    IssueSeverity,
    async_create_issue,
    async_delete_issue,
)

from .const import DOMAIN, TUYA_DISCOVERY_NEW, DeviceCategory, DPCode
from .coordinator import TuyaConfigEntry
from .entity import TuyaEntity, TuyaEntityDescription, get_child_device_info


def _has_multiple_switch_channels(device: CustomerDevice, channels: int) -> bool:
    """Return if the device reports more than one indexed switch channel."""
    return (
        sum(
            f"switch_{index}" in device.status_range for index in range(1, channels + 1)
        )
        > 1
    )


def _channel_switches(
    channels: int,
    *,
    translation_key: str,
    device_class: SwitchDeviceClass | None = None,
) -> tuple[TuyaSwitchEntityDescription, ...]:
    """Build switch descriptions for indexed channels."""
    return tuple(
        TuyaSwitchEntityDescription(
            key=f"switch_{index}",
            translation_key=translation_key,
            device_class=device_class,
            channel_index=index,
            channel_condition=lambda device: _has_multiple_switch_channels(
                device, channels
            ),
        )
        for index in range(1, channels + 1)
    )


# All descriptions can be found here. Mostly the Boolean data types in the
# default instruction set of each category end up being a Switch.
# https://developer.tuya.com/en/docs/iot/standarddescription?id=K9i5ql6waswzq
@dataclass(frozen=True)
class TuyaSwitchEntityDescription(TuyaEntityDescription, SwitchEntityDescription):
    """Describes a Tuya switch entity."""


@dataclass(frozen=True, kw_only=True)
class TuyaDeprecatedSwitchEntityDescription(TuyaSwitchEntityDescription):
    """Describes a deprecated Tuya switch entity."""

    deprecated: str
    breaks_in_ha_version: str


SWITCHES: dict[DeviceCategory, tuple[TuyaSwitchEntityDescription, ...]] = {
    DeviceCategory.BH: (
        TuyaSwitchEntityDescription(
            key=DPCode.START,
            translation_key="start",
        ),
        TuyaSwitchEntityDescription(
            key=DPCode.WARM,
            translation_key="heat_preservation",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.BZYD: (
        TuyaSwitchEntityDescription(
            key=DPCode.SWITCH,
            name=None,
        ),
        TuyaSwitchEntityDescription(
            key=DPCode.CHILD_LOCK,
            translation_key="child_lock",
            icon="mdi:account-lock",
            entity_category=EntityCategory.CONFIG,
        ),
        TuyaSwitchEntityDescription(
            key=DPCode.SWITCH_MUSIC,
            translation_key="music",
            icon="mdi:music",
            entity_category=EntityCategory.CONFIG,
        ),
        TuyaSwitchEntityDescription(
            key=DPCode.SNOOZE,
            translation_key="snooze",
            icon="mdi:alarm-snooze",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.CJKG: _channel_switches(4, translation_key="switch"),
    DeviceCategory.CL: (
        TuyaSwitchEntityDescription(
            key=DPCode.CONTROL_BACK,
            translation_key="reverse",
            entity_category=EntityCategory.CONFIG,
        ),
        TuyaSwitchEntityDescription(
            key=DPCode.OPPOSITE,
            translation_key="reverse",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.CN: (
        TuyaSwitchEntityDescription(
            key=DPCode.DISINFECTION,
            translation_key="disinfection",
        ),
        TuyaSwitchEntityDescription(
            key=DPCode.WATER,
            translation_key="water",
        ),
    ),
    DeviceCategory.CS: (
        TuyaSwitchEntityDescription(
            key=DPCode.ANION,
            translation_key="ionizer",
            icon="mdi:atom",
            entity_category=EntityCategory.CONFIG,
        ),
        TuyaSwitchEntityDescription(
            key=DPCode.CHILD_LOCK,
            translation_key="child_lock",
            icon="mdi:account-lock",
            entity_category=EntityCategory.CONFIG,
        ),
        TuyaSwitchEntityDescription(
            key=DPCode.FILTER_RESET,
            translation_key="filter_reset",
            icon="mdi:filter",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.CWJWQ: (
        TuyaSwitchEntityDescription(
            key=DPCode.SWITCH,
            translation_key="switch",
        ),
    ),
    DeviceCategory.CWWSQ: (
        TuyaSwitchEntityDescription(
            key=DPCode.SLOW_FEED,
            translation_key="slow_feed",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.CWYSJ: (
        TuyaSwitchEntityDescription(
            key=DPCode.FILTER_RESET,
            translation_key="filter_reset",
            entity_category=EntityCategory.CONFIG,
        ),
        TuyaSwitchEntityDescription(
            key=DPCode.PUMP_RESET,
            translation_key="water_pump_reset",
            entity_category=EntityCategory.CONFIG,
        ),
        TuyaSwitchEntityDescription(
            key=DPCode.SWITCH,
            translation_key="power",
        ),
        TuyaSwitchEntityDescription(
            key=DPCode.WATER_RESET,
            translation_key="reset_of_water_usage_days",
            entity_category=EntityCategory.CONFIG,
        ),
        TuyaSwitchEntityDescription(
            key=DPCode.UV,
            translation_key="uv_sterilization",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.CZ: (
        TuyaSwitchEntityDescription(
            key=DPCode.CHILD_LOCK,
            translation_key="child_lock",
            entity_category=EntityCategory.CONFIG,
        ),
        *_channel_switches(
            6, translation_key="socket", device_class=SwitchDeviceClass.OUTLET
        ),
        TuyaSwitchEntityDescription(
            key=DPCode.SWITCH_USB1,
            translation_key="indexed_usb",
            translation_placeholders={"index": "1"},
        ),
        TuyaSwitchEntityDescription(
            key=DPCode.SWITCH_USB2,
            translation_key="indexed_usb",
            translation_placeholders={"index": "2"},
        ),
        TuyaSwitchEntityDescription(
            key=DPCode.SWITCH_USB3,
            translation_key="indexed_usb",
            translation_placeholders={"index": "3"},
        ),
        TuyaSwitchEntityDescription(
            key=DPCode.SWITCH_USB4,
            translation_key="indexed_usb",
            translation_placeholders={"index": "4"},
        ),
        TuyaSwitchEntityDescription(
            key=DPCode.SWITCH_USB5,
            translation_key="indexed_usb",
            translation_placeholders={"index": "5"},
        ),
        TuyaSwitchEntityDescription(
            key=DPCode.SWITCH_USB6,
            translation_key="indexed_usb",
            translation_placeholders={"index": "6"},
        ),
        TuyaSwitchEntityDescription(
            key=DPCode.SWITCH,
            translation_key="socket",
            device_class=SwitchDeviceClass.OUTLET,
        ),
    ),
    DeviceCategory.DGHSXJ: (
        TuyaSwitchEntityDescription(
            key=DPCode.WIRELESS_BATTERYLOCK,
            translation_key="battery_lock",
            entity_category=EntityCategory.CONFIG,
        ),
        TuyaSwitchEntityDescription(
            key=DPCode.CRY_DETECTION_SWITCH,
            translation_key="cry_detection",
            entity_category=EntityCategory.CONFIG,
        ),
        TuyaSwitchEntityDescription(
            key=DPCode.DECIBEL_SWITCH,
            translation_key="sound_detection",
            entity_category=EntityCategory.CONFIG,
        ),
        TuyaSwitchEntityDescription(
            key=DPCode.RECORD_SWITCH,
            translation_key="video_recording",
            entity_category=EntityCategory.CONFIG,
        ),
        TuyaSwitchEntityDescription(
            key=DPCode.MOTION_RECORD,
            translation_key="motion_recording",
            entity_category=EntityCategory.CONFIG,
        ),
        TuyaSwitchEntityDescription(
            key=DPCode.BASIC_PRIVATE,
            translation_key="privacy_mode",
            entity_category=EntityCategory.CONFIG,
        ),
        TuyaSwitchEntityDescription(
            key=DPCode.BASIC_FLIP,
            translation_key="flip",
            entity_category=EntityCategory.CONFIG,
        ),
        TuyaSwitchEntityDescription(
            key=DPCode.BASIC_OSD,
            translation_key="time_watermark",
            entity_category=EntityCategory.CONFIG,
        ),
        TuyaSwitchEntityDescription(
            key=DPCode.BASIC_WDR,
            translation_key="wide_dynamic_range",
            entity_category=EntityCategory.CONFIG,
        ),
        TuyaSwitchEntityDescription(
            key=DPCode.MOTION_TRACKING,
            translation_key="motion_tracking",
            entity_category=EntityCategory.CONFIG,
        ),
        TuyaSwitchEntityDescription(
            key=DPCode.MOTION_SWITCH,
            translation_key="motion_alarm",
            entity_category=EntityCategory.CONFIG,
        ),
        TuyaSwitchEntityDescription(
            key=DPCode.MOTION_AREA_SWITCH,
            translation_key="motion_detection_zone",
            entity_category=EntityCategory.CONFIG,
        ),
        TuyaSwitchEntityDescription(
            key=DPCode.IPC_AUTO_SIREN,
            translation_key="auto_siren",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.DJ: (
        # There are sockets available with an RGB light
        # that advertise as `dj`, but provide an additional
        # switch to control the plug.
        TuyaSwitchEntityDescription(
            key=DPCode.SWITCH,
            translation_key="plug",
        ),
    ),
    DeviceCategory.DLQ: (
        TuyaSwitchEntityDescription(
            key=DPCode.CHILD_LOCK,
            translation_key="child_lock",
            entity_category=EntityCategory.CONFIG,
        ),
        TuyaSwitchEntityDescription(
            key=DPCode.SWITCH,
            translation_key="switch",
        ),
    ),
    DeviceCategory.DR: (
        TuyaSwitchEntityDescription(
            key=DPCode.SWITCH,
            name="Power",
            icon="mdi:power",
            device_class=SwitchDeviceClass.SWITCH,
        ),
        TuyaSwitchEntityDescription(
            key=DPCode.SWITCH_1,
            name="Side A Power",
            icon="mdi:alpha-a",
            device_class=SwitchDeviceClass.SWITCH,
        ),
        TuyaSwitchEntityDescription(
            key=DPCode.SWITCH_2,
            name="Side B Power",
            icon="mdi:alpha-b",
            device_class=SwitchDeviceClass.SWITCH,
        ),
        TuyaSwitchEntityDescription(
            key=DPCode.PREHEAT,
            name="Preheat",
            icon="mdi:radiator",
            device_class=SwitchDeviceClass.SWITCH,
        ),
        TuyaSwitchEntityDescription(
            key=DPCode.PREHEAT_1,
            name="Side A Preheat",
            icon="mdi:radiator",
            device_class=SwitchDeviceClass.SWITCH,
        ),
        TuyaSwitchEntityDescription(
            key=DPCode.PREHEAT_2,
            name="Side B Preheat",
            icon="mdi:radiator",
            device_class=SwitchDeviceClass.SWITCH,
        ),
    ),
    DeviceCategory.FS: (
        TuyaSwitchEntityDescription(
            key=DPCode.ANION,
            translation_key="anion",
            entity_category=EntityCategory.CONFIG,
        ),
        TuyaSwitchEntityDescription(
            key=DPCode.HUMIDIFIER,
            translation_key="humidification",
            entity_category=EntityCategory.CONFIG,
        ),
        TuyaSwitchEntityDescription(
            key=DPCode.OXYGEN,
            translation_key="oxygen_bar",
            entity_category=EntityCategory.CONFIG,
        ),
        TuyaSwitchEntityDescription(
            key=DPCode.FAN_COOL,
            translation_key="natural_wind",
            entity_category=EntityCategory.CONFIG,
        ),
        TuyaSwitchEntityDescription(
            key=DPCode.FAN_BEEP,
            translation_key="sound",
            entity_category=EntityCategory.CONFIG,
        ),
        TuyaSwitchEntityDescription(
            key=DPCode.CHILD_LOCK,
            translation_key="child_lock",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.FSD: (
        TuyaSwitchEntityDescription(
            key=DPCode.FAN_BEEP,
            translation_key="sound",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.GGQ: tuple(
        TuyaDeprecatedSwitchEntityDescription(
            key=f"switch_{index}",
            translation_key="indexed_switch",
            translation_placeholders={"index": str(index)},
            deprecated="deprecated_entity_new_valve",
            breaks_in_ha_version="2027.5.0",
        )
        for index in range(1, 9)
    ),
    DeviceCategory.HXD: (
        TuyaSwitchEntityDescription(
            key=DPCode.SWITCH_1,
            translation_key="radio",
        ),
        TuyaSwitchEntityDescription(
            key=DPCode.SWITCH_2,
            translation_key="indexed_alarm",
            translation_placeholders={"index": "1"},
            entity_category=EntityCategory.CONFIG,
        ),
        TuyaSwitchEntityDescription(
            key=DPCode.SWITCH_3,
            translation_key="indexed_alarm",
            translation_placeholders={"index": "2"},
            entity_category=EntityCategory.CONFIG,
        ),
        TuyaSwitchEntityDescription(
            key=DPCode.SWITCH_4,
            translation_key="indexed_alarm",
            translation_placeholders={"index": "3"},
            entity_category=EntityCategory.CONFIG,
        ),
        TuyaSwitchEntityDescription(
            key=DPCode.SWITCH_5,
            translation_key="indexed_alarm",
            translation_placeholders={"index": "4"},
            entity_category=EntityCategory.CONFIG,
        ),
        TuyaSwitchEntityDescription(
            key=DPCode.SWITCH_6,
            translation_key="sleep_aid",
        ),
    ),
    DeviceCategory.HWSB: (
        TuyaSwitchEntityDescription(
            key=DPCode.SWITCH,
            name=None,
        ),
    ),
    DeviceCategory.JSQ: (
        TuyaSwitchEntityDescription(
            key=DPCode.SWITCH_SOUND,
            translation_key="voice",
            entity_category=EntityCategory.CONFIG,
        ),
        TuyaSwitchEntityDescription(
            key=DPCode.SLEEP,
            translation_key="sleep",
            entity_category=EntityCategory.CONFIG,
        ),
        TuyaSwitchEntityDescription(
            key=DPCode.STERILIZATION,
            translation_key="sterilization",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.KG: (
        TuyaSwitchEntityDescription(
            key=DPCode.CHILD_LOCK,
            translation_key="child_lock",
            entity_category=EntityCategory.CONFIG,
        ),
        *_channel_switches(
            22, translation_key="switch", device_class=SwitchDeviceClass.OUTLET
        ),
        TuyaSwitchEntityDescription(
            key=DPCode.SWITCH_USB1,
            translation_key="indexed_usb",
            translation_placeholders={"index": "1"},
        ),
        TuyaSwitchEntityDescription(
            key=DPCode.SWITCH_USB2,
            translation_key="indexed_usb",
            translation_placeholders={"index": "2"},
        ),
        TuyaSwitchEntityDescription(
            key=DPCode.SWITCH_USB3,
            translation_key="indexed_usb",
            translation_placeholders={"index": "3"},
        ),
        TuyaSwitchEntityDescription(
            key=DPCode.SWITCH_USB4,
            translation_key="indexed_usb",
            translation_placeholders={"index": "4"},
        ),
        TuyaSwitchEntityDescription(
            key=DPCode.SWITCH_USB5,
            translation_key="indexed_usb",
            translation_placeholders={"index": "5"},
        ),
        TuyaSwitchEntityDescription(
            key=DPCode.SWITCH_USB6,
            translation_key="indexed_usb",
            translation_placeholders={"index": "6"},
        ),
        TuyaSwitchEntityDescription(
            key=DPCode.SWITCH,
            translation_key="switch",
            device_class=SwitchDeviceClass.OUTLET,
        ),
    ),
    DeviceCategory.KJ: (
        TuyaSwitchEntityDescription(
            key=DPCode.ANION,
            translation_key="ionizer",
            entity_category=EntityCategory.CONFIG,
        ),
        TuyaSwitchEntityDescription(
            key=DPCode.FILTER_RESET,
            translation_key="filter_cartridge_reset",
            entity_category=EntityCategory.CONFIG,
        ),
        TuyaSwitchEntityDescription(
            key=DPCode.LOCK,
            translation_key="child_lock",
            entity_category=EntityCategory.CONFIG,
        ),
        TuyaSwitchEntityDescription(
            key=DPCode.SWITCH,
            translation_key="power",
        ),
        TuyaSwitchEntityDescription(
            key=DPCode.WET,
            translation_key="humidification",
            entity_category=EntityCategory.CONFIG,
        ),
        TuyaSwitchEntityDescription(
            key=DPCode.UV,
            translation_key="uv_sterilization",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.KT: (
        TuyaSwitchEntityDescription(
            key=DPCode.ANION,
            translation_key="ionizer",
            entity_category=EntityCategory.CONFIG,
        ),
        TuyaSwitchEntityDescription(
            key=DPCode.LOCK,
            translation_key="child_lock",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.KS: (
        TuyaSwitchEntityDescription(
            key=DPCode.ANION,
            translation_key="ionizer",
        ),
    ),
    DeviceCategory.MAL: (
        TuyaSwitchEntityDescription(
            key=DPCode.SWITCH_ALARM_SOUND,
            # This switch is called "Arm Beep" in the official Tuya app
            translation_key="arm_beep",
            entity_category=EntityCategory.CONFIG,
        ),
        TuyaSwitchEntityDescription(
            key=DPCode.SWITCH_ALARM_LIGHT,
            # This switch is called "Siren" in the official Tuya app
            translation_key="siren",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.MJJ: (
        TuyaSwitchEntityDescription(
            key=DPCode.CHILD_LOCK,
            translation_key="child_lock",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.MSP: (
        TuyaSwitchEntityDescription(
            key=DPCode.AUTO_CLEAN,
            translation_key="auto_clean",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.MZJ: (
        TuyaSwitchEntityDescription(
            key=DPCode.SWITCH,
            translation_key="switch",
            entity_category=EntityCategory.CONFIG,
        ),
        TuyaSwitchEntityDescription(
            key=DPCode.START,
            translation_key="start",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.PC: (
        TuyaSwitchEntityDescription(
            key=DPCode.CHILD_LOCK,
            translation_key="child_lock",
            entity_category=EntityCategory.CONFIG,
        ),
        *_channel_switches(
            6, translation_key="socket", device_class=SwitchDeviceClass.OUTLET
        ),
        TuyaSwitchEntityDescription(
            key=DPCode.SWITCH_USB1,
            translation_key="indexed_usb",
            translation_placeholders={"index": "1"},
        ),
        TuyaSwitchEntityDescription(
            key=DPCode.SWITCH_USB2,
            translation_key="indexed_usb",
            translation_placeholders={"index": "2"},
        ),
        TuyaSwitchEntityDescription(
            key=DPCode.SWITCH_USB3,
            translation_key="indexed_usb",
            translation_placeholders={"index": "3"},
        ),
        TuyaSwitchEntityDescription(
            key=DPCode.SWITCH_USB4,
            translation_key="indexed_usb",
            translation_placeholders={"index": "4"},
        ),
        TuyaSwitchEntityDescription(
            key=DPCode.SWITCH_USB5,
            translation_key="indexed_usb",
            translation_placeholders={"index": "5"},
        ),
        TuyaSwitchEntityDescription(
            key=DPCode.SWITCH_USB6,
            translation_key="indexed_usb",
            translation_placeholders={"index": "6"},
        ),
        TuyaSwitchEntityDescription(
            key=DPCode.SWITCH,
            translation_key="socket",
            device_class=SwitchDeviceClass.OUTLET,
        ),
    ),
    DeviceCategory.QCCDZ: (
        TuyaSwitchEntityDescription(
            key=DPCode.SWITCH,
            translation_key="switch",
        ),
    ),
    DeviceCategory.QJDCZ: (
        TuyaSwitchEntityDescription(
            key=DPCode.SWITCH_1,
            translation_key="switch",
        ),
    ),
    DeviceCategory.QN: (
        TuyaSwitchEntityDescription(
            key=DPCode.ANION,
            translation_key="ionizer",
            entity_category=EntityCategory.CONFIG,
        ),
        TuyaSwitchEntityDescription(
            key=DPCode.LOCK,
            translation_key="child_lock",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.QXJ: (
        TuyaSwitchEntityDescription(
            key=DPCode.SWITCH,
            translation_key="switch",
            device_class=SwitchDeviceClass.OUTLET,
        ),
    ),
    DeviceCategory.SD: (
        TuyaSwitchEntityDescription(
            key=DPCode.SWITCH_DISTURB,
            translation_key="do_not_disturb",
            entity_category=EntityCategory.CONFIG,
        ),
        TuyaSwitchEntityDescription(
            key=DPCode.VOICE_SWITCH,
            translation_key="mute_voice",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.SGBJ: (
        TuyaSwitchEntityDescription(
            key=DPCode.MUFFLING,
            translation_key="mute",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.SJZ: (
        TuyaSwitchEntityDescription(
            key=DPCode.CHILD_LOCK,
            translation_key="child_lock",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.SP: (
        TuyaSwitchEntityDescription(
            key=DPCode.WIRELESS_BATTERYLOCK,
            translation_key="battery_lock",
            entity_category=EntityCategory.CONFIG,
        ),
        TuyaSwitchEntityDescription(
            key=DPCode.CRY_DETECTION_SWITCH,
            translation_key="cry_detection",
            entity_category=EntityCategory.CONFIG,
        ),
        TuyaSwitchEntityDescription(
            key=DPCode.DECIBEL_SWITCH,
            translation_key="sound_detection",
            entity_category=EntityCategory.CONFIG,
        ),
        TuyaSwitchEntityDescription(
            key=DPCode.RECORD_SWITCH,
            translation_key="video_recording",
            entity_category=EntityCategory.CONFIG,
        ),
        TuyaSwitchEntityDescription(
            key=DPCode.MOTION_RECORD,
            translation_key="motion_recording",
            entity_category=EntityCategory.CONFIG,
        ),
        TuyaSwitchEntityDescription(
            key=DPCode.BASIC_PRIVATE,
            translation_key="privacy_mode",
            entity_category=EntityCategory.CONFIG,
        ),
        TuyaSwitchEntityDescription(
            key=DPCode.BASIC_FLIP,
            translation_key="flip",
            entity_category=EntityCategory.CONFIG,
        ),
        TuyaSwitchEntityDescription(
            key=DPCode.BASIC_OSD,
            translation_key="time_watermark",
            entity_category=EntityCategory.CONFIG,
        ),
        TuyaSwitchEntityDescription(
            key=DPCode.BASIC_WDR,
            translation_key="wide_dynamic_range",
            entity_category=EntityCategory.CONFIG,
        ),
        TuyaSwitchEntityDescription(
            key=DPCode.MOTION_TRACKING,
            translation_key="motion_tracking",
            entity_category=EntityCategory.CONFIG,
        ),
        TuyaSwitchEntityDescription(
            key=DPCode.MOTION_SWITCH,
            translation_key="motion_alarm",
            entity_category=EntityCategory.CONFIG,
        ),
        TuyaSwitchEntityDescription(
            key=DPCode.MOTION_AREA_SWITCH,
            translation_key="motion_detection_zone",
            entity_category=EntityCategory.CONFIG,
        ),
        TuyaSwitchEntityDescription(
            key=DPCode.IPC_AUTO_SIREN,
            translation_key="auto_siren",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.SZ: (
        TuyaSwitchEntityDescription(
            key=DPCode.SWITCH,
            translation_key="power",
        ),
        TuyaSwitchEntityDescription(
            key=DPCode.PUMP,
            translation_key="pump",
        ),
    ),
    DeviceCategory.SZJQR: (
        TuyaSwitchEntityDescription(
            key=DPCode.SWITCH,
            translation_key="switch",
        ),
    ),
    DeviceCategory.TDQ: (
        TuyaSwitchEntityDescription(
            key=DPCode.SWITCH_1,
            translation_key="indexed_switch",
            translation_placeholders={"index": "1"},
            device_class=SwitchDeviceClass.OUTLET,
        ),
        TuyaSwitchEntityDescription(
            key=DPCode.SWITCH_2,
            translation_key="indexed_switch",
            translation_placeholders={"index": "2"},
            device_class=SwitchDeviceClass.OUTLET,
        ),
        TuyaSwitchEntityDescription(
            key=DPCode.SWITCH_3,
            translation_key="indexed_switch",
            translation_placeholders={"index": "3"},
            device_class=SwitchDeviceClass.OUTLET,
        ),
        TuyaSwitchEntityDescription(
            key=DPCode.SWITCH_4,
            translation_key="indexed_switch",
            translation_placeholders={"index": "4"},
            device_class=SwitchDeviceClass.OUTLET,
        ),
        TuyaSwitchEntityDescription(
            key=DPCode.SWITCH_5,
            translation_key="indexed_switch",
            translation_placeholders={"index": "5"},
            device_class=SwitchDeviceClass.OUTLET,
        ),
        TuyaSwitchEntityDescription(
            key=DPCode.SWITCH_6,
            translation_key="indexed_switch",
            translation_placeholders={"index": "6"},
            device_class=SwitchDeviceClass.OUTLET,
        ),
        TuyaSwitchEntityDescription(
            key=DPCode.CHILD_LOCK,
            translation_key="child_lock",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.TYNDJ: (
        TuyaSwitchEntityDescription(
            key=DPCode.SWITCH_SAVE_ENERGY,
            translation_key="energy_saving",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.WG2: (
        TuyaSwitchEntityDescription(
            key=DPCode.MUFFLING,
            translation_key="mute",
            entity_category=EntityCategory.CONFIG,
        ),
        TuyaSwitchEntityDescription(
            key=DPCode.SWITCH_KB_SOUND,
            # Poorly translated as "Key tone switch of host" in the official Tuya app
            translation_key="keypad_sound",
            entity_category=EntityCategory.CONFIG,
        ),
        TuyaSwitchEntityDescription(
            key=DPCode.SWITCH_ALARM_PROPEL,
            # Poorly translated as "alarm push switch" in the official Tuya app
            translation_key="alarm_push_notifications",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.WK: (
        TuyaSwitchEntityDescription(
            key=DPCode.CHILD_LOCK,
            translation_key="child_lock",
            entity_category=EntityCategory.CONFIG,
        ),
        TuyaSwitchEntityDescription(
            key=DPCode.FROST,
            translation_key="frost_protection",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.WKCZ: _channel_switches(
        2, translation_key="switch", device_class=SwitchDeviceClass.OUTLET
    ),
    DeviceCategory.WKF: (
        TuyaSwitchEntityDescription(
            key=DPCode.CHILD_LOCK,
            translation_key="child_lock",
            entity_category=EntityCategory.CONFIG,
        ),
        TuyaSwitchEntityDescription(
            key=DPCode.WINDOW_CHECK,
            translation_key="open_window_detection",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.WNYKQ: (
        TuyaSwitchEntityDescription(
            key=DPCode.SWITCH,
            name=None,
        ),
    ),
    DeviceCategory.WSDCG: (
        TuyaSwitchEntityDescription(
            key=DPCode.SWITCH,
            translation_key="switch",
            device_class=SwitchDeviceClass.OUTLET,
        ),
    ),
    DeviceCategory.XDD: (
        TuyaSwitchEntityDescription(
            key=DPCode.DO_NOT_DISTURB,
            translation_key="do_not_disturb",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.XNYJCN: (
        TuyaSwitchEntityDescription(
            key=DPCode.FEEDIN_POWER_LIMIT_ENABLE,
            translation_key="output_power_limit",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.XXJ: (
        TuyaSwitchEntityDescription(
            key=DPCode.SWITCH,
            translation_key="power",
        ),
        TuyaSwitchEntityDescription(
            key=DPCode.SWITCH_SPRAY,
            translation_key="spray",
        ),
        TuyaSwitchEntityDescription(
            key=DPCode.SWITCH_VOICE,
            translation_key="voice",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.YWBJ: (
        TuyaSwitchEntityDescription(
            key=DPCode.MUFFLING,
            translation_key="mute",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.ZNDB: (
        TuyaSwitchEntityDescription(
            key=DPCode.SWITCH,
            translation_key="switch",
        ),
    ),
    DeviceCategory.ZNJDQ: (
        TuyaSwitchEntityDescription(
            key=DPCode.SWITCH_1,
            translation_key="indexed_switch",
            translation_placeholders={"index": "1"},
        ),
        TuyaSwitchEntityDescription(
            key=DPCode.CHILD_LOCK,
            translation_key="child_lock",
            icon="mdi:account-lock",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.ZNJXS: (
        TuyaSwitchEntityDescription(
            key=DPCode.SWITCH,
            translation_key="switch",
        ),
    ),
    DeviceCategory.ZNRB: (
        TuyaSwitchEntityDescription(
            key=DPCode.CHILD_LOCK,
            translation_key="child_lock",
            icon="mdi:account-lock",
            entity_category=EntityCategory.CONFIG,
        ),
        TuyaSwitchEntityDescription(
            key=DPCode.SWITCH,
            translation_key="switch",
        ),
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TuyaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up tuya sensors dynamically through tuya discovery."""
    manager = entry.runtime_data.manager
    entity_registry = er.async_get(hass)

    @callback
    def async_discover_device(device_ids: list[str]) -> None:
        """Discover and add a discovered tuya sensor."""
        entities: list[TuyaSwitchEntity] = []
        for device_id in device_ids:
            device = manager.device_map[device_id]
            if descriptions := SWITCHES.get(device.category):
                parent_device_id = dr.async_get_device_id_by_identifier(
                    hass, (DOMAIN, device.id), config_entry_id=entry.entry_id
                )
                entities.extend(
                    TuyaSwitchEntity(
                        device,
                        manager,
                        description,
                        definition,
                        device_info=get_child_device_info(
                            device, parent_device_id, description
                        ),
                    )
                    for description in descriptions
                    if (definition := get_default_definition(device, description.key))
                    and _check_deprecation(hass, device, description, entity_registry)
                )

        async_add_entities(entities)

    async_discover_device([*manager.device_map])

    entry.async_on_unload(
        async_dispatcher_connect(hass, TUYA_DISCOVERY_NEW, async_discover_device)
    )


def _check_deprecation(
    hass: HomeAssistant,
    device: CustomerDevice,
    description: TuyaSwitchEntityDescription,
    entity_registry: er.EntityRegistry,
) -> bool:
    """Check entity deprecation.

    Returns:
        `True` if the entity should be created, `False` otherwise.
    """
    if not isinstance(description, TuyaDeprecatedSwitchEntityDescription):
        return True

    unique_id = f"tuya.{device.id}{description.key}"
    entity_id = entity_registry.async_get_entity_id(SWITCH_DOMAIN, DOMAIN, unique_id)

    if not entity_id or not (entity_entry := entity_registry.async_get(entity_id)):
        async_delete_issue(hass, DOMAIN, f"deprecated_entity_{unique_id}")
        return False

    if entity_entry.disabled:
        entity_registry.async_remove(entity_id)
        async_delete_issue(hass, DOMAIN, f"deprecated_entity_{unique_id}")
        return False

    async_create_issue(
        hass,
        DOMAIN,
        f"deprecated_entity_{unique_id}",
        breaks_in_ha_version=description.breaks_in_ha_version,
        config_entry_id=entity_entry.config_entry_id,
        is_fixable=False,
        severity=IssueSeverity.WARNING,
        translation_key=description.deprecated,
        translation_placeholders={
            "name": f"{device.name} {entity_entry.name or entity_entry.original_name}",
            "entity": entity_id,
        },
    )
    return True


class TuyaSwitchEntity(TuyaEntity, SwitchEntity):
    """Tuya Switch Device."""

    def __init__(
        self,
        device: CustomerDevice,
        device_manager: Manager,
        description: TuyaSwitchEntityDescription,
        definition: SwitchDefinition,
        *,
        device_info: ChildDeviceInfo | None = None,
    ) -> None:
        """Init TuyaHaSwitch."""
        super().__init__(device, device_manager, description, device_info=device_info)
        self._dpcode_wrapper = definition.switch_wrapper

    @property
    @override
    def is_on(self) -> bool | None:
        """Return true if switch is on."""
        return self._read_wrapper(self._dpcode_wrapper)

    @override
    async def _process_device_update(
        self,
        updated_status_properties: list[str],
        dp_timestamps: dict[str, int] | None,
    ) -> bool:
        """Called when Tuya device sends an update with updated properties.

        Returns True if the Home Assistant state should be written,
        or False if the state write should be skipped.
        """
        return not self._dpcode_wrapper.skip_update(
            self.device, updated_status_properties, dp_timestamps
        )

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self._async_send_wrapper_updates(self._dpcode_wrapper, True)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self._async_send_wrapper_updates(self._dpcode_wrapper, False)
