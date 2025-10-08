"""Support for Tuya switches."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from tuya_sharing import CustomerDevice, Manager

from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.issue_registry import (
    IssueSeverity,
    async_create_issue,
    async_delete_issue,
)

from . import TuyaConfigEntry
from .const import DOMAIN, TUYA_DISCOVERY_NEW, DeviceCategory, DPCode
from .entity import TuyaEntity
from .xternal_tuya_quirks import TUYA_QUIRKS_REGISTRY
from .xternal_tuya_quirks.switch import CommonSwitchType, TuyaSwitchDefinition


@dataclass(frozen=True, kw_only=True)
class TuyaDeprecatedSwitchEntityDescription(SwitchEntityDescription):
    """Describes Tuya deprecated switch entity."""

    deprecated: str
    breaks_in_ha_version: str


# All descriptions can be found here. Mostly the Boolean data types in the
# default instruction set of each category end up being a Switch.
# https://developer.tuya.com/en/docs/iot/standarddescription?id=K9i5ql6waswzq
SWITCHES: dict[DeviceCategory, tuple[SwitchEntityDescription, ...]] = {
    DeviceCategory.BH: (
        SwitchEntityDescription(
            key=DPCode.START,
            translation_key="start",
        ),
        SwitchEntityDescription(
            key=DPCode.WARM,
            translation_key="heat_preservation",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.BZYD: (
        SwitchEntityDescription(
            key=DPCode.SWITCH,
            name=None,
        ),
        SwitchEntityDescription(
            key=DPCode.CHILD_LOCK,
            translation_key="child_lock",
            icon="mdi:account-lock",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_MUSIC,
            translation_key="music",
            icon="mdi:music",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.SNOOZE,
            translation_key="snooze",
            icon="mdi:alarm-snooze",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.CL: (
        SwitchEntityDescription(
            key=DPCode.CONTROL_BACK,
            translation_key="reverse",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.OPPOSITE,
            translation_key="reverse",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.CN: (
        SwitchEntityDescription(
            key=DPCode.DISINFECTION,
            translation_key="disinfection",
        ),
        SwitchEntityDescription(
            key=DPCode.WATER,
            translation_key="water",
        ),
    ),
    DeviceCategory.CS: (
        SwitchEntityDescription(
            key=DPCode.ANION,
            translation_key="ionizer",
            icon="mdi:atom",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.CHILD_LOCK,
            translation_key="child_lock",
            icon="mdi:account-lock",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.FILTER_RESET,
            translation_key="filter_reset",
            icon="mdi:filter",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.CWJWQ: (
        SwitchEntityDescription(
            key=DPCode.SWITCH,
            translation_key="switch",
        ),
    ),
    DeviceCategory.CWWSQ: (
        SwitchEntityDescription(
            key=DPCode.SLOW_FEED,
            translation_key="slow_feed",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.CWYSJ: (
        SwitchEntityDescription(
            key=DPCode.FILTER_RESET,
            translation_key="filter_reset",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.PUMP_RESET,
            translation_key="water_pump_reset",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH,
            translation_key="power",
        ),
        SwitchEntityDescription(
            key=DPCode.WATER_RESET,
            translation_key="reset_of_water_usage_days",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.UV,
            translation_key="uv_sterilization",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.DJ: (
        # There are sockets available with an RGB light
        # that advertise as `dj`, but provide an additional
        # switch to control the plug.
        SwitchEntityDescription(
            key=DPCode.SWITCH,
            translation_key="plug",
        ),
    ),
    DeviceCategory.DLQ: (
        SwitchEntityDescription(
            key=DPCode.CHILD_LOCK,
            translation_key="child_lock",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH,
            translation_key="switch",
        ),
    ),
    DeviceCategory.DR: (
        SwitchEntityDescription(
            key=DPCode.SWITCH,
            name="Power",
            icon="mdi:power",
            device_class=SwitchDeviceClass.SWITCH,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_1,
            name="Side A Power",
            icon="mdi:alpha-a",
            device_class=SwitchDeviceClass.SWITCH,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_2,
            name="Side B Power",
            icon="mdi:alpha-b",
            device_class=SwitchDeviceClass.SWITCH,
        ),
        SwitchEntityDescription(
            key=DPCode.PREHEAT,
            name="Preheat",
            icon="mdi:radiator",
            device_class=SwitchDeviceClass.SWITCH,
        ),
        SwitchEntityDescription(
            key=DPCode.PREHEAT_1,
            name="Side A Preheat",
            icon="mdi:radiator",
            device_class=SwitchDeviceClass.SWITCH,
        ),
        SwitchEntityDescription(
            key=DPCode.PREHEAT_2,
            name="Side B Preheat",
            icon="mdi:radiator",
            device_class=SwitchDeviceClass.SWITCH,
        ),
    ),
    DeviceCategory.FS: (
        SwitchEntityDescription(
            key=DPCode.ANION,
            translation_key="anion",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.HUMIDIFIER,
            translation_key="humidification",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.OXYGEN,
            translation_key="oxygen_bar",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.FAN_COOL,
            translation_key="natural_wind",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.FAN_BEEP,
            translation_key="sound",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.CHILD_LOCK,
            translation_key="child_lock",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.FSD: (
        SwitchEntityDescription(
            key=DPCode.FAN_BEEP,
            translation_key="sound",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.GGQ: (
        SwitchEntityDescription(
            key=DPCode.SWITCH_1,
            translation_key="indexed_switch",
            translation_placeholders={"index": "1"},
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_2,
            translation_key="indexed_switch",
            translation_placeholders={"index": "2"},
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_3,
            translation_key="indexed_switch",
            translation_placeholders={"index": "3"},
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_4,
            translation_key="indexed_switch",
            translation_placeholders={"index": "4"},
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_5,
            translation_key="indexed_switch",
            translation_placeholders={"index": "5"},
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_6,
            translation_key="indexed_switch",
            translation_placeholders={"index": "6"},
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_7,
            translation_key="indexed_switch",
            translation_placeholders={"index": "7"},
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_8,
            translation_key="indexed_switch",
            translation_placeholders={"index": "8"},
        ),
    ),
    DeviceCategory.HXD: (
        SwitchEntityDescription(
            key=DPCode.SWITCH_1,
            translation_key="radio",
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_2,
            translation_key="indexed_alarm",
            translation_placeholders={"index": "1"},
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_3,
            translation_key="indexed_alarm",
            translation_placeholders={"index": "2"},
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_4,
            translation_key="indexed_alarm",
            translation_placeholders={"index": "3"},
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_5,
            translation_key="indexed_alarm",
            translation_placeholders={"index": "4"},
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_6,
            translation_key="sleep_aid",
        ),
    ),
    DeviceCategory.JSQ: (
        SwitchEntityDescription(
            key=DPCode.SWITCH_SOUND,
            translation_key="voice",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.SLEEP,
            translation_key="sleep",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.STERILIZATION,
            translation_key="sterilization",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.KG: (
        SwitchEntityDescription(
            key=DPCode.CHILD_LOCK,
            translation_key="child_lock",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_1,
            translation_key="indexed_switch",
            translation_placeholders={"index": "1"},
            device_class=SwitchDeviceClass.OUTLET,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_2,
            translation_key="indexed_switch",
            translation_placeholders={"index": "2"},
            device_class=SwitchDeviceClass.OUTLET,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_3,
            translation_key="indexed_switch",
            translation_placeholders={"index": "3"},
            device_class=SwitchDeviceClass.OUTLET,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_4,
            translation_key="indexed_switch",
            translation_placeholders={"index": "4"},
            device_class=SwitchDeviceClass.OUTLET,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_5,
            translation_key="indexed_switch",
            translation_placeholders={"index": "5"},
            device_class=SwitchDeviceClass.OUTLET,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_6,
            translation_key="indexed_switch",
            translation_placeholders={"index": "6"},
            device_class=SwitchDeviceClass.OUTLET,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_7,
            translation_key="indexed_switch",
            translation_placeholders={"index": "7"},
            device_class=SwitchDeviceClass.OUTLET,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_8,
            translation_key="indexed_switch",
            translation_placeholders={"index": "8"},
            device_class=SwitchDeviceClass.OUTLET,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_USB1,
            translation_key="indexed_usb",
            translation_placeholders={"index": "1"},
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_USB2,
            translation_key="indexed_usb",
            translation_placeholders={"index": "2"},
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_USB3,
            translation_key="indexed_usb",
            translation_placeholders={"index": "3"},
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_USB4,
            translation_key="indexed_usb",
            translation_placeholders={"index": "4"},
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_USB5,
            translation_key="indexed_usb",
            translation_placeholders={"index": "5"},
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_USB6,
            translation_key="indexed_usb",
            translation_placeholders={"index": "6"},
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH,
            translation_key="switch",
            device_class=SwitchDeviceClass.OUTLET,
        ),
    ),
    DeviceCategory.KJ: (
        SwitchEntityDescription(
            key=DPCode.ANION,
            translation_key="ionizer",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.FILTER_RESET,
            translation_key="filter_cartridge_reset",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.LOCK,
            translation_key="child_lock",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH,
            translation_key="power",
        ),
        SwitchEntityDescription(
            key=DPCode.WET,
            translation_key="humidification",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.UV,
            translation_key="uv_sterilization",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.KT: (
        SwitchEntityDescription(
            key=DPCode.ANION,
            translation_key="ionizer",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.LOCK,
            translation_key="child_lock",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.KS: (
        SwitchEntityDescription(
            key=DPCode.ANION,
            translation_key="ionizer",
        ),
    ),
    DeviceCategory.MAL: (
        SwitchEntityDescription(
            key=DPCode.SWITCH_ALARM_SOUND,
            # This switch is called "Arm Beep" in the official Tuya app
            translation_key="arm_beep",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_ALARM_LIGHT,
            # This switch is called "Siren" in the official Tuya app
            translation_key="siren",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.MZJ: (
        SwitchEntityDescription(
            key=DPCode.SWITCH,
            translation_key="switch",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.START,
            translation_key="start",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.PC: (
        SwitchEntityDescription(
            key=DPCode.CHILD_LOCK,
            translation_key="child_lock",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_1,
            translation_key="indexed_socket",
            translation_placeholders={"index": "1"},
            device_class=SwitchDeviceClass.OUTLET,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_2,
            translation_key="indexed_socket",
            translation_placeholders={"index": "2"},
            device_class=SwitchDeviceClass.OUTLET,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_3,
            translation_key="indexed_socket",
            translation_placeholders={"index": "3"},
            device_class=SwitchDeviceClass.OUTLET,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_4,
            translation_key="indexed_socket",
            translation_placeholders={"index": "4"},
            device_class=SwitchDeviceClass.OUTLET,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_5,
            translation_key="indexed_socket",
            translation_placeholders={"index": "5"},
            device_class=SwitchDeviceClass.OUTLET,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_6,
            translation_key="indexed_socket",
            translation_placeholders={"index": "6"},
            device_class=SwitchDeviceClass.OUTLET,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_USB1,
            translation_key="indexed_usb",
            translation_placeholders={"index": "1"},
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_USB2,
            translation_key="indexed_usb",
            translation_placeholders={"index": "2"},
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_USB3,
            translation_key="indexed_usb",
            translation_placeholders={"index": "3"},
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_USB4,
            translation_key="indexed_usb",
            translation_placeholders={"index": "4"},
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_USB5,
            translation_key="indexed_usb",
            translation_placeholders={"index": "5"},
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_USB6,
            translation_key="indexed_usb",
            translation_placeholders={"index": "6"},
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH,
            translation_key="socket",
            device_class=SwitchDeviceClass.OUTLET,
        ),
    ),
    DeviceCategory.QCCDZ: (
        SwitchEntityDescription(
            key=DPCode.SWITCH,
            translation_key="switch",
        ),
    ),
    DeviceCategory.QJDCZ: (
        SwitchEntityDescription(
            key=DPCode.SWITCH_1,
            translation_key="switch",
        ),
    ),
    DeviceCategory.QN: (
        SwitchEntityDescription(
            key=DPCode.ANION,
            translation_key="ionizer",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.LOCK,
            translation_key="child_lock",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.QXJ: (
        SwitchEntityDescription(
            key=DPCode.SWITCH,
            translation_key="switch",
            device_class=SwitchDeviceClass.OUTLET,
        ),
    ),
    DeviceCategory.SD: (
        SwitchEntityDescription(
            key=DPCode.SWITCH_DISTURB,
            translation_key="do_not_disturb",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.VOICE_SWITCH,
            translation_key="mute_voice",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.SFKZQ: (
        TuyaDeprecatedSwitchEntityDescription(
            key=DPCode.SWITCH,
            translation_key="switch",
            deprecated="deprecated_entity_new_valve",
            breaks_in_ha_version="2026.4.0",
        ),
    ),
    DeviceCategory.SGBJ: (
        SwitchEntityDescription(
            key=DPCode.MUFFLING,
            translation_key="mute",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.SJZ: (
        SwitchEntityDescription(
            key=DPCode.CHILD_LOCK,
            translation_key="child_lock",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.SP: (
        SwitchEntityDescription(
            key=DPCode.WIRELESS_BATTERYLOCK,
            translation_key="battery_lock",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.CRY_DETECTION_SWITCH,
            translation_key="cry_detection",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.DECIBEL_SWITCH,
            translation_key="sound_detection",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.RECORD_SWITCH,
            translation_key="video_recording",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.MOTION_RECORD,
            translation_key="motion_recording",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.BASIC_PRIVATE,
            translation_key="privacy_mode",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.BASIC_FLIP,
            translation_key="flip",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.BASIC_OSD,
            translation_key="time_watermark",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.BASIC_WDR,
            translation_key="wide_dynamic_range",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.MOTION_TRACKING,
            translation_key="motion_tracking",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.MOTION_SWITCH,
            translation_key="motion_alarm",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.SZ: (
        SwitchEntityDescription(
            key=DPCode.SWITCH,
            translation_key="power",
        ),
        SwitchEntityDescription(
            key=DPCode.PUMP,
            translation_key="pump",
        ),
    ),
    DeviceCategory.SZJQR: (
        SwitchEntityDescription(
            key=DPCode.SWITCH,
            translation_key="switch",
        ),
    ),
    DeviceCategory.TDQ: (
        SwitchEntityDescription(
            key=DPCode.SWITCH_1,
            translation_key="indexed_switch",
            translation_placeholders={"index": "1"},
            device_class=SwitchDeviceClass.OUTLET,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_2,
            translation_key="indexed_switch",
            translation_placeholders={"index": "2"},
            device_class=SwitchDeviceClass.OUTLET,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_3,
            translation_key="indexed_switch",
            translation_placeholders={"index": "3"},
            device_class=SwitchDeviceClass.OUTLET,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_4,
            translation_key="indexed_switch",
            translation_placeholders={"index": "4"},
            device_class=SwitchDeviceClass.OUTLET,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_5,
            translation_key="indexed_switch",
            translation_placeholders={"index": "5"},
            device_class=SwitchDeviceClass.OUTLET,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_6,
            translation_key="indexed_switch",
            translation_placeholders={"index": "6"},
            device_class=SwitchDeviceClass.OUTLET,
        ),
        SwitchEntityDescription(
            key=DPCode.CHILD_LOCK,
            translation_key="child_lock",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.TYNDJ: (
        SwitchEntityDescription(
            key=DPCode.SWITCH_SAVE_ENERGY,
            translation_key="energy_saving",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.WG2: (
        SwitchEntityDescription(
            key=DPCode.MUFFLING,
            translation_key="mute",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.WK: (
        SwitchEntityDescription(
            key=DPCode.CHILD_LOCK,
            translation_key="child_lock",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.FROST,
            translation_key="frost_protection",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.WKCZ: (
        SwitchEntityDescription(
            key=DPCode.SWITCH_1,
            translation_key="indexed_switch",
            translation_placeholders={"index": "1"},
            device_class=SwitchDeviceClass.OUTLET,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_2,
            translation_key="indexed_switch",
            translation_placeholders={"index": "2"},
            device_class=SwitchDeviceClass.OUTLET,
        ),
    ),
    DeviceCategory.WKF: (
        SwitchEntityDescription(
            key=DPCode.CHILD_LOCK,
            translation_key="child_lock",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.WINDOW_CHECK,
            translation_key="open_window_detection",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.WNYKQ: (
        SwitchEntityDescription(
            key=DPCode.SWITCH,
            name=None,
        ),
    ),
    DeviceCategory.WSDCG: (
        SwitchEntityDescription(
            key=DPCode.SWITCH,
            translation_key="switch",
            device_class=SwitchDeviceClass.OUTLET,
        ),
    ),
    DeviceCategory.XDD: (
        SwitchEntityDescription(
            key=DPCode.DO_NOT_DISTURB,
            translation_key="do_not_disturb",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.XNYJCN: (
        SwitchEntityDescription(
            key=DPCode.FEEDIN_POWER_LIMIT_ENABLE,
            translation_key="output_power_limit",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.XXJ: (
        SwitchEntityDescription(
            key=DPCode.SWITCH,
            translation_key="power",
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_SPRAY,
            translation_key="spray",
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_VOICE,
            translation_key="voice",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.YWBJ: (
        SwitchEntityDescription(
            key=DPCode.MUFFLING,
            translation_key="mute",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.ZNDB: (
        SwitchEntityDescription(
            key=DPCode.SWITCH,
            translation_key="switch",
        ),
    ),
    DeviceCategory.ZNJXS: (
        SwitchEntityDescription(
            key=DPCode.SWITCH,
            translation_key="switch",
        ),
    ),
    DeviceCategory.ZNRB: (
        SwitchEntityDescription(
            key=DPCode.SWITCH,
            translation_key="switch",
        ),
    ),
}

# Socket (duplicate of `pc`)
SWITCHES[DeviceCategory.CZ] = SWITCHES[DeviceCategory.PC]

# Smart Camera - Low power consumption camera (duplicate of `sp`)
SWITCHES[DeviceCategory.DGHSXJ] = SWITCHES[DeviceCategory.SP]

COMMON_SWITCH_DEFINITIONS: dict[CommonSwitchType, SwitchEntityDescription] = {
    CommonSwitchType.CHILD_LOCK: SwitchEntityDescription(
        key="tbc",
        translation_key="child_lock",
        entity_category=EntityCategory.CONFIG,
    )
}


def _create_quirk_description(
    definition: TuyaSwitchDefinition,
) -> SwitchEntityDescription:
    return replace(
        COMMON_SWITCH_DEFINITIONS[definition.common_type],
        key=DPCode(definition.key),
    )


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
            if quirk := TUYA_QUIRKS_REGISTRY.get_quirk_for_device(device):
                entities.extend(
                    TuyaSwitchEntity(
                        device, manager, _create_quirk_description(definition)
                    )
                    for definition in quirk.switch_definitions
                    if definition.key in device.status
                )
            elif descriptions := SWITCHES.get(device.category):
                entities.extend(
                    TuyaSwitchEntity(device, manager, description)
                    for description in descriptions
                    if description.key in device.status
                    and _check_deprecation(
                        hass,
                        device,
                        description,
                        entity_registry,
                    )
                )

        async_add_entities(entities)

    async_discover_device([*manager.device_map])

    entry.async_on_unload(
        async_dispatcher_connect(hass, TUYA_DISCOVERY_NEW, async_discover_device)
    )


def _check_deprecation(
    hass: HomeAssistant,
    device: CustomerDevice,
    description: SwitchEntityDescription,
    entity_registry: er.EntityRegistry,
) -> bool:
    """Check entity deprecation.

    Returns:
        `True` if the entity should be created, `False` otherwise.
    """
    # Not deprecated, just create it
    if not isinstance(description, TuyaDeprecatedSwitchEntityDescription):
        return True

    unique_id = f"tuya.{device.id}{description.key}"
    entity_id = entity_registry.async_get_entity_id(SWITCH_DOMAIN, DOMAIN, unique_id)

    # Deprecated and not present in registry, skip creation
    if not entity_id or not (entity_entry := entity_registry.async_get(entity_id)):
        return False

    # Deprecated and present in registry but disabled, remove it and skip creation
    if entity_entry.disabled:
        entity_registry.async_remove(entity_id)
        async_delete_issue(
            hass,
            DOMAIN,
            f"deprecated_entity_{unique_id}",
        )
        return False

    # Deprecated and present in registry and enabled, raise issue and create it
    async_create_issue(
        hass,
        DOMAIN,
        f"deprecated_entity_{unique_id}",
        breaks_in_ha_version=description.breaks_in_ha_version,
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
        description: SwitchEntityDescription,
    ) -> None:
        """Init TuyaHaSwitch."""
        super().__init__(device, device_manager)
        self.entity_description = description
        self._attr_unique_id = f"{super().unique_id}{description.key}"

    @property
    def is_on(self) -> bool:
        """Return true if switch is on."""
        return self.device.status.get(self.entity_description.key, False)

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        self._send_command([{"code": self.entity_description.key, "value": True}])

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        self._send_command([{"code": self.entity_description.key, "value": False}])
