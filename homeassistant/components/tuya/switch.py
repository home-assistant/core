"""Support for Tuya switches."""
from __future__ import annotations

from typing import Any

from tuya_iot import TuyaDevice, TuyaDeviceManager

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HomeAssistantTuyaData
from .base import TuyaEntity
from .const import DOMAIN, TUYA_DISCOVERY_NEW, DPCode

# All descriptions can be found here. Mostly the Boolean data types in the
# default instruction set of each category end up being a Switch.
# https://developer.tuya.com/en/docs/iot/standarddescription?id=K9i5ql6waswzq
SWITCHES: dict[str, tuple[SwitchEntityDescription, ...]] = {
    # Smart Kettle
    # https://developer.tuya.com/en/docs/iot/fbh?id=K9gf484m21yq7
    "bh": (
        SwitchEntityDescription(
            key=DPCode.START,
            translation_key="start",
            icon="mdi:kettle-steam",
        ),
        SwitchEntityDescription(
            key=DPCode.WARM,
            translation_key="heat_preservation",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    # EasyBaby
    # Undocumented, might have a wider use
    "cn": (
        SwitchEntityDescription(
            key=DPCode.DISINFECTION,
            translation_key="disinfection",
            icon="mdi:bacteria",
        ),
        SwitchEntityDescription(
            key=DPCode.WATER,
            translation_key="water",
            icon="mdi:water",
        ),
    ),
    # Smart Pet Feeder
    # https://developer.tuya.com/en/docs/iot/categorycwwsq?id=Kaiuz2b6vydld
    "cwwsq": (
        SwitchEntityDescription(
            key=DPCode.SLOW_FEED,
            translation_key="slow_feed",
            icon="mdi:speedometer-slow",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    # Pet Water Feeder
    # https://developer.tuya.com/en/docs/iot/f?id=K9gf46aewxem5
    "cwysj": (
        SwitchEntityDescription(
            key=DPCode.FILTER_RESET,
            translation_key="filter_reset",
            icon="mdi:filter",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.PUMP_RESET,
            translation_key="water_pump_reset",
            icon="mdi:pump",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH,
            translation_key="power",
        ),
        SwitchEntityDescription(
            key=DPCode.WATER_RESET,
            translation_key="reset_of_water_usage_days",
            icon="mdi:water-sync",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.UV,
            translation_key="uv_sterilization",
            icon="mdi:lightbulb",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    # Light
    # https://developer.tuya.com/en/docs/iot/f?id=K9i5ql3v98hn3
    "dj": (
        # There are sockets available with an RGB light
        # that advertise as `dj`, but provide an additional
        # switch to control the plug.
        SwitchEntityDescription(
            key=DPCode.SWITCH,
            translation_key="plug",
        ),
    ),
    # Cirquit Breaker
    "dlq": (
        SwitchEntityDescription(
            key=DPCode.CHILD_LOCK,
            translation_key="asd",
            icon="mdi:account-lock",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH,
            translation_key="switch",
        ),
    ),
    # Wake Up Light II
    # Not documented
    "hxd": (
        SwitchEntityDescription(
            key=DPCode.SWITCH_1,
            translation_key="radio",
            icon="mdi:radio",
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_2,
            translation_key="alarm_1",
            icon="mdi:alarm",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_3,
            translation_key="alarm_2",
            icon="mdi:alarm",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_4,
            translation_key="alarm_3",
            icon="mdi:alarm",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_5,
            translation_key="alarm_4",
            icon="mdi:alarm",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_6,
            translation_key="sleep_aid",
            icon="mdi:power-sleep",
        ),
    ),
    # Two-way temperature and humidity switch
    # "MOES Temperature and Humidity Smart Switch Module MS-103"
    # Documentation not found
    "wkcz": (
        SwitchEntityDescription(
            key=DPCode.SWITCH_1,
            translation_key="switch_1",
            device_class=SwitchDeviceClass.OUTLET,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_2,
            translation_key="switch_2",
            device_class=SwitchDeviceClass.OUTLET,
        ),
    ),
    # Switch
    # https://developer.tuya.com/en/docs/iot/s?id=K9gf7o5prgf7s
    "kg": (
        SwitchEntityDescription(
            key=DPCode.CHILD_LOCK,
            translation_key="child_lock",
            icon="mdi:account-lock",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_1,
            translation_key="switch_1",
            device_class=SwitchDeviceClass.OUTLET,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_2,
            translation_key="switch_2",
            device_class=SwitchDeviceClass.OUTLET,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_3,
            translation_key="switch_3",
            device_class=SwitchDeviceClass.OUTLET,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_4,
            translation_key="switch_4",
            device_class=SwitchDeviceClass.OUTLET,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_5,
            translation_key="switch_5",
            device_class=SwitchDeviceClass.OUTLET,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_6,
            translation_key="switch_6",
            device_class=SwitchDeviceClass.OUTLET,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_7,
            translation_key="switch_7",
            device_class=SwitchDeviceClass.OUTLET,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_8,
            translation_key="switch_8",
            device_class=SwitchDeviceClass.OUTLET,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_USB1,
            translation_key="usb_1",
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_USB2,
            translation_key="usb_2",
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_USB3,
            translation_key="usb_3",
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_USB4,
            translation_key="usb_4",
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_USB5,
            translation_key="usb_5",
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_USB6,
            translation_key="usb_6",
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH,
            translation_key="switch",
            device_class=SwitchDeviceClass.OUTLET,
        ),
    ),
    # Air Purifier
    # https://developer.tuya.com/en/docs/iot/f?id=K9gf46h2s6dzm
    "kj": (
        SwitchEntityDescription(
            key=DPCode.ANION,
            translation_key="ionizer",
            icon="mdi:minus-circle-outline",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.FILTER_RESET,
            translation_key="filter_cartridge_reset",
            icon="mdi:filter",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.LOCK,
            translation_key="child_lock",
            icon="mdi:account-lock",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH,
            translation_key="power",
        ),
        SwitchEntityDescription(
            key=DPCode.WET,
            translation_key="humidification",
            icon="mdi:water-percent",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.UV,
            translation_key="uv_sterilization",
            icon="mdi:minus-circle-outline",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    # Air conditioner
    # https://developer.tuya.com/en/docs/iot/categorykt?id=Kaiuz0z71ov2n
    "kt": (
        SwitchEntityDescription(
            key=DPCode.ANION,
            translation_key="ionizer",
            icon="mdi:minus-circle-outline",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.LOCK,
            translation_key="child_lock",
            icon="mdi:account-lock",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    # Sous Vide Cooker
    # https://developer.tuya.com/en/docs/iot/categorymzj?id=Kaiuz2vy130ux
    "mzj": (
        SwitchEntityDescription(
            key=DPCode.SWITCH,
            translation_key="switch",
            icon="mdi:power",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.START,
            translation_key="start",
            icon="mdi:pot-steam",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    # Power Socket
    # https://developer.tuya.com/en/docs/iot/s?id=K9gf7o5prgf7s
    "pc": (
        SwitchEntityDescription(
            key=DPCode.CHILD_LOCK,
            translation_key="child_lock",
            icon="mdi:account-lock",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_1,
            translation_key="socket_1",
            device_class=SwitchDeviceClass.OUTLET,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_2,
            translation_key="socket_2",
            device_class=SwitchDeviceClass.OUTLET,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_3,
            translation_key="socket_3",
            device_class=SwitchDeviceClass.OUTLET,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_4,
            translation_key="socket_4",
            device_class=SwitchDeviceClass.OUTLET,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_5,
            translation_key="socket_5",
            device_class=SwitchDeviceClass.OUTLET,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_6,
            translation_key="socket_6",
            device_class=SwitchDeviceClass.OUTLET,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_USB1,
            translation_key="usb_1",
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_USB2,
            translation_key="usb_2",
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_USB3,
            translation_key="usb_3",
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_USB4,
            translation_key="usb_4",
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_USB5,
            translation_key="usb_5",
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_USB6,
            translation_key="usb_6",
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH,
            translation_key="socket",
            device_class=SwitchDeviceClass.OUTLET,
        ),
    ),
    # Unknown product with switch capabilities
    # Fond in some diffusers, plugs and PIR flood lights
    # Not documented
    "qjdcz": (
        SwitchEntityDescription(
            key=DPCode.SWITCH_1,
            translation_key="switch",
        ),
    ),
    # Heater
    # https://developer.tuya.com/en/docs/iot/categoryqn?id=Kaiuz18kih0sm
    "qn": (
        SwitchEntityDescription(
            key=DPCode.ANION,
            translation_key="ionizer",
            icon="mdi:minus-circle-outline",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.LOCK,
            translation_key="child_lock",
            icon="mdi:account-lock",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    # Robot Vacuum
    # https://developer.tuya.com/en/docs/iot/fsd?id=K9gf487ck1tlo
    "sd": (
        SwitchEntityDescription(
            key=DPCode.SWITCH_DISTURB,
            translation_key="do_not_disturb",
            icon="mdi:minus-circle",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.VOICE_SWITCH,
            translation_key="mute_voice",
            icon="mdi:account-voice",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    # Siren Alarm
    # https://developer.tuya.com/en/docs/iot/categorysgbj?id=Kaiuz37tlpbnu
    "sgbj": (
        SwitchEntityDescription(
            key=DPCode.MUFFLING,
            translation_key="mute",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    # Smart Camera
    # https://developer.tuya.com/en/docs/iot/categorysp?id=Kaiuz35leyo12
    "sp": (
        SwitchEntityDescription(
            key=DPCode.WIRELESS_BATTERYLOCK,
            translation_key="battery_lock",
            icon="mdi:battery-lock",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.CRY_DETECTION_SWITCH,
            translation_key="cry_detection",
            icon="mdi:emoticon-cry",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.DECIBEL_SWITCH,
            translation_key="sound_detection",
            icon="mdi:microphone-outline",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.RECORD_SWITCH,
            translation_key="video_recording",
            icon="mdi:record-rec",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.MOTION_RECORD,
            translation_key="motion_recording",
            icon="mdi:record-rec",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.BASIC_PRIVATE,
            translation_key="privacy_mode",
            icon="mdi:eye-off",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.BASIC_FLIP,
            translation_key="flip",
            icon="mdi:flip-horizontal",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.BASIC_OSD,
            translation_key="time_watermark",
            icon="mdi:watermark",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.BASIC_WDR,
            translation_key="wide_dynamic_range",
            icon="mdi:watermark",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.MOTION_TRACKING,
            translation_key="motion_tracking",
            icon="mdi:motion-sensor",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.MOTION_SWITCH,
            translation_key="motion_alarm",
            icon="mdi:motion-sensor",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    # Fingerbot
    "szjqr": (
        SwitchEntityDescription(
            key=DPCode.SWITCH,
            translation_key="switch",
            icon="mdi:cursor-pointer",
        ),
    ),
    # IoT Switch?
    # Note: Undocumented
    "tdq": (
        SwitchEntityDescription(
            key=DPCode.SWITCH_1,
            translation_key="switch_1",
            device_class=SwitchDeviceClass.OUTLET,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_2,
            translation_key="switch_2",
            device_class=SwitchDeviceClass.OUTLET,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_3,
            translation_key="switch_3",
            device_class=SwitchDeviceClass.OUTLET,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_4,
            translation_key="switch_4",
            device_class=SwitchDeviceClass.OUTLET,
        ),
        SwitchEntityDescription(
            key=DPCode.CHILD_LOCK,
            translation_key="child_lock",
            icon="mdi:account-lock",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    # Solar Light
    # https://developer.tuya.com/en/docs/iot/tynd?id=Kaof8j02e1t98
    "tyndj": (
        SwitchEntityDescription(
            key=DPCode.SWITCH_SAVE_ENERGY,
            translation_key="energy_saving",
            icon="mdi:leaf",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    # Thermostatic Radiator Valve
    # Not documented
    "wkf": (
        SwitchEntityDescription(
            key=DPCode.CHILD_LOCK,
            translation_key="child_lock",
            icon="mdi:account-lock",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.WINDOW_CHECK,
            translation_key="open_window_detection",
            icon="mdi:window-open",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    # Air Conditioner Mate (Smart IR Socket)
    "wnykq": (
        SwitchEntityDescription(
            key=DPCode.SWITCH,
            name=None,
        ),
    ),
    # SIREN: Siren (switch) with Temperature and humidity sensor
    # https://developer.tuya.com/en/docs/iot/f?id=Kavck4sr3o5ek
    "wsdcg": (
        SwitchEntityDescription(
            key=DPCode.SWITCH,
            translation_key="switch",
            device_class=SwitchDeviceClass.OUTLET,
        ),
    ),
    # Ceiling Light
    # https://developer.tuya.com/en/docs/iot/ceiling-light?id=Kaiuz03xxfc4r
    "xdd": (
        SwitchEntityDescription(
            key=DPCode.DO_NOT_DISTURB,
            translation_key="do_not_disturb",
            icon="mdi:minus-circle-outline",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    # Diffuser
    # https://developer.tuya.com/en/docs/iot/categoryxxj?id=Kaiuz1f9mo6bl
    "xxj": (
        SwitchEntityDescription(
            key=DPCode.SWITCH,
            translation_key="power",
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_SPRAY,
            translation_key="spray",
            icon="mdi:spray",
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_VOICE,
            translation_key="voice",
            icon="mdi:account-voice",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    # Smart Electricity Meter
    # https://developer.tuya.com/en/docs/iot/smart-meter?id=Kaiuz4gv6ack7
    "zndb": (
        SwitchEntityDescription(
            key=DPCode.SWITCH,
            translation_key="switch",
        ),
    ),
    # Fan
    # https://developer.tuya.com/en/docs/iot/categoryfs?id=Kaiuz1xweel1c
    "fs": (
        SwitchEntityDescription(
            key=DPCode.ANION,
            translation_key="anion",
            icon="mdi:atom",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.HUMIDIFIER,
            translation_key="humidification",
            icon="mdi:air-humidifier",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.OXYGEN,
            translation_key="oxygen_bar",
            icon="mdi:molecule",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.FAN_COOL,
            translation_key="natural_wind",
            icon="mdi:weather-windy",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.FAN_BEEP,
            translation_key="sound",
            icon="mdi:minus-circle",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.CHILD_LOCK,
            translation_key="child_lock",
            icon="mdi:account-lock",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    # Curtain
    # https://developer.tuya.com/en/docs/iot/f?id=K9gf46o5mtfyc
    "cl": (
        SwitchEntityDescription(
            key=DPCode.CONTROL_BACK,
            translation_key="reverse",
            icon="mdi:swap-horizontal",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.OPPOSITE,
            translation_key="reverse",
            icon="mdi:swap-horizontal",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    # Humidifier
    # https://developer.tuya.com/en/docs/iot/categoryjsq?id=Kaiuz1smr440b
    "jsq": (
        SwitchEntityDescription(
            key=DPCode.SWITCH_SOUND,
            translation_key="voice",
            icon="mdi:account-voice",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.SLEEP,
            translation_key="sleep",
            icon="mdi:power-sleep",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.STERILIZATION,
            translation_key="sterilization",
            icon="mdi:minus-circle-outline",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
}

# Socket (duplicate of `pc`)
# https://developer.tuya.com/en/docs/iot/s?id=K9gf7o5prgf7s
SWITCHES["cz"] = SWITCHES["pc"]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up tuya sensors dynamically through tuya discovery."""
    hass_data: HomeAssistantTuyaData = hass.data[DOMAIN][entry.entry_id]

    @callback
    def async_discover_device(device_ids: list[str]) -> None:
        """Discover and add a discovered tuya sensor."""
        entities: list[TuyaSwitchEntity] = []
        for device_id in device_ids:
            device = hass_data.device_manager.device_map[device_id]
            if descriptions := SWITCHES.get(device.category):
                for description in descriptions:
                    if description.key in device.status:
                        entities.append(
                            TuyaSwitchEntity(
                                device, hass_data.device_manager, description
                            )
                        )

        async_add_entities(entities)

    async_discover_device([*hass_data.device_manager.device_map])

    entry.async_on_unload(
        async_dispatcher_connect(hass, TUYA_DISCOVERY_NEW, async_discover_device)
    )


class TuyaSwitchEntity(TuyaEntity, SwitchEntity):
    """Tuya Switch Device."""

    def __init__(
        self,
        device: TuyaDevice,
        device_manager: TuyaDeviceManager,
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
