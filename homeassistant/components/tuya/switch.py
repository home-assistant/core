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
            name="Start",
            icon="mdi:kettle-steam",
        ),
        SwitchEntityDescription(
            key=DPCode.WARM,
            name="Heat preservation",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    # EasyBaby
    # Undocumented, might have a wider use
    "cn": (
        SwitchEntityDescription(
            key=DPCode.DISINFECTION,
            name="Disinfection",
            icon="mdi:bacteria",
        ),
        SwitchEntityDescription(
            key=DPCode.WATER,
            name="Water",
            icon="mdi:water",
        ),
    ),
    # Smart Pet Feeder
    # https://developer.tuya.com/en/docs/iot/categorycwwsq?id=Kaiuz2b6vydld
    "cwwsq": (
        SwitchEntityDescription(
            key=DPCode.SLOW_FEED,
            name="Slow feed",
            icon="mdi:speedometer-slow",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    # Pet Water Feeder
    # https://developer.tuya.com/en/docs/iot/f?id=K9gf46aewxem5
    "cwysj": (
        SwitchEntityDescription(
            key=DPCode.FILTER_RESET,
            name="Filter reset",
            icon="mdi:filter",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.PUMP_RESET,
            name="Water pump reset",
            icon="mdi:pump",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH,
            name="Power",
        ),
        SwitchEntityDescription(
            key=DPCode.WATER_RESET,
            name="Reset of water usage days",
            icon="mdi:water-sync",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.UV,
            name="UV sterilization",
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
            name="Plug",
        ),
    ),
    # Cirquit Breaker
    "dlq": (
        SwitchEntityDescription(
            key=DPCode.CHILD_LOCK,
            name="Child lock",
            icon="mdi:account-lock",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH,
            name="Switch",
        ),
    ),
    # Wake Up Light II
    # Not documented
    "hxd": (
        SwitchEntityDescription(
            key=DPCode.SWITCH_1,
            name="Radio",
            icon="mdi:radio",
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_2,
            name="Alarm 1",
            icon="mdi:alarm",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_3,
            name="Alarm 2",
            icon="mdi:alarm",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_4,
            name="Alarm 3",
            icon="mdi:alarm",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_5,
            name="Alarm 4",
            icon="mdi:alarm",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_6,
            name="Sleep aid",
            icon="mdi:power-sleep",
        ),
    ),
    # Two-way temperature and humidity switch
    # "MOES Temperature and Humidity Smart Switch Module MS-103"
    # Documentation not found
    "wkcz": (
        SwitchEntityDescription(
            key=DPCode.SWITCH_1,
            name="Switch 1",
            device_class=SwitchDeviceClass.OUTLET,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_2,
            name="Switch 2",
            device_class=SwitchDeviceClass.OUTLET,
        ),
    ),
    # Switch
    # https://developer.tuya.com/en/docs/iot/s?id=K9gf7o5prgf7s
    "kg": (
        SwitchEntityDescription(
            key=DPCode.CHILD_LOCK,
            name="Child lock",
            icon="mdi:account-lock",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_1,
            name="Switch 1",
            device_class=SwitchDeviceClass.OUTLET,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_2,
            name="Switch 2",
            device_class=SwitchDeviceClass.OUTLET,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_3,
            name="Switch 3",
            device_class=SwitchDeviceClass.OUTLET,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_4,
            name="Switch 4",
            device_class=SwitchDeviceClass.OUTLET,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_5,
            name="Switch 5",
            device_class=SwitchDeviceClass.OUTLET,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_6,
            name="Switch 6",
            device_class=SwitchDeviceClass.OUTLET,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_7,
            name="Switch 7",
            device_class=SwitchDeviceClass.OUTLET,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_8,
            name="Switch 8",
            device_class=SwitchDeviceClass.OUTLET,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_USB1,
            name="USB 1",
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_USB2,
            name="USB 2",
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_USB3,
            name="USB 3",
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_USB4,
            name="USB 4",
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_USB5,
            name="USB 5",
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_USB6,
            name="USB 6",
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH,
            name="Switch",
            device_class=SwitchDeviceClass.OUTLET,
        ),
    ),
    # Air Purifier
    # https://developer.tuya.com/en/docs/iot/f?id=K9gf46h2s6dzm
    "kj": (
        SwitchEntityDescription(
            key=DPCode.ANION,
            name="Ionizer",
            icon="mdi:minus-circle-outline",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.FILTER_RESET,
            name="Filter cartridge reset",
            icon="mdi:filter",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.LOCK,
            name="Child lock",
            icon="mdi:account-lock",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH,
            name="Power",
        ),
        SwitchEntityDescription(
            key=DPCode.WET,
            name="Humidification",
            icon="mdi:water-percent",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.UV,
            name="UV sterilization",
            icon="mdi:minus-circle-outline",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    # Air conditioner
    # https://developer.tuya.com/en/docs/iot/categorykt?id=Kaiuz0z71ov2n
    "kt": (
        SwitchEntityDescription(
            key=DPCode.ANION,
            name="Ionizer",
            icon="mdi:minus-circle-outline",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.LOCK,
            name="Child lock",
            icon="mdi:account-lock",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    # Sous Vide Cooker
    # https://developer.tuya.com/en/docs/iot/categorymzj?id=Kaiuz2vy130ux
    "mzj": (
        SwitchEntityDescription(
            key=DPCode.SWITCH,
            name="Switch",
            icon="mdi:power",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.START,
            name="Start",
            icon="mdi:pot-steam",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    # Power Socket
    # https://developer.tuya.com/en/docs/iot/s?id=K9gf7o5prgf7s
    "pc": (
        SwitchEntityDescription(
            key=DPCode.CHILD_LOCK,
            name="Child lock",
            icon="mdi:account-lock",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_1,
            name="Socket 1",
            device_class=SwitchDeviceClass.OUTLET,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_2,
            name="Socket 2",
            device_class=SwitchDeviceClass.OUTLET,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_3,
            name="Socket 3",
            device_class=SwitchDeviceClass.OUTLET,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_4,
            name="Socket 4",
            device_class=SwitchDeviceClass.OUTLET,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_5,
            name="Socket 5",
            device_class=SwitchDeviceClass.OUTLET,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_6,
            name="Socket 6",
            device_class=SwitchDeviceClass.OUTLET,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_USB1,
            name="USB 1",
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_USB2,
            name="USB 2",
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_USB3,
            name="USB 3",
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_USB4,
            name="USB 4",
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_USB5,
            name="USB 5",
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_USB6,
            name="USB 6",
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH,
            name="Socket",
            device_class=SwitchDeviceClass.OUTLET,
        ),
    ),
    # Unknown product with switch capabilities
    # Fond in some diffusers, plugs and PIR flood lights
    # Not documented
    "qjdcz": (
        SwitchEntityDescription(
            key=DPCode.SWITCH_1,
            name="Switch",
        ),
    ),
    # Heater
    # https://developer.tuya.com/en/docs/iot/categoryqn?id=Kaiuz18kih0sm
    "qn": (
        SwitchEntityDescription(
            key=DPCode.ANION,
            name="Ionizer",
            icon="mdi:minus-circle-outline",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.LOCK,
            name="Child lock",
            icon="mdi:account-lock",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    # Robot Vacuum
    # https://developer.tuya.com/en/docs/iot/fsd?id=K9gf487ck1tlo
    "sd": (
        SwitchEntityDescription(
            key=DPCode.SWITCH_DISTURB,
            name="Do not disturb",
            icon="mdi:minus-circle",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.VOICE_SWITCH,
            name="Mute voice",
            icon="mdi:account-voice",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    # Siren Alarm
    # https://developer.tuya.com/en/docs/iot/categorysgbj?id=Kaiuz37tlpbnu
    "sgbj": (
        SwitchEntityDescription(
            key=DPCode.MUFFLING,
            name="Mute",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    # Smart Camera
    # https://developer.tuya.com/en/docs/iot/categorysp?id=Kaiuz35leyo12
    "sp": (
        SwitchEntityDescription(
            key=DPCode.WIRELESS_BATTERYLOCK,
            name="Battery lock",
            icon="mdi:battery-lock",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.CRY_DETECTION_SWITCH,
            icon="mdi:emoticon-cry",
            name="Cry detection",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.DECIBEL_SWITCH,
            icon="mdi:microphone-outline",
            name="Sound detection",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.RECORD_SWITCH,
            icon="mdi:record-rec",
            name="Video recording",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.MOTION_RECORD,
            icon="mdi:record-rec",
            name="Motion recording",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.BASIC_PRIVATE,
            icon="mdi:eye-off",
            name="Privacy mode",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.BASIC_FLIP,
            icon="mdi:flip-horizontal",
            name="Flip",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.BASIC_OSD,
            icon="mdi:watermark",
            name="Time watermark",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.BASIC_WDR,
            icon="mdi:watermark",
            name="Wide dynamic range",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.MOTION_TRACKING,
            icon="mdi:motion-sensor",
            name="Motion tracking",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.MOTION_SWITCH,
            icon="mdi:motion-sensor",
            name="Motion alarm",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    # Fingerbot
    "szjqr": (
        SwitchEntityDescription(
            key=DPCode.SWITCH,
            name="Switch",
            icon="mdi:cursor-pointer",
        ),
    ),
    # IoT Switch?
    # Note: Undocumented
    "tdq": (
        SwitchEntityDescription(
            key=DPCode.SWITCH_1,
            name="Switch 1",
            device_class=SwitchDeviceClass.OUTLET,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_2,
            name="Switch 2",
            device_class=SwitchDeviceClass.OUTLET,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_3,
            name="Switch 3",
            device_class=SwitchDeviceClass.OUTLET,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_4,
            name="Switch 4",
            device_class=SwitchDeviceClass.OUTLET,
        ),
        SwitchEntityDescription(
            key=DPCode.CHILD_LOCK,
            name="Child lock",
            icon="mdi:account-lock",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    # Solar Light
    # https://developer.tuya.com/en/docs/iot/tynd?id=Kaof8j02e1t98
    "tyndj": (
        SwitchEntityDescription(
            key=DPCode.SWITCH_SAVE_ENERGY,
            name="Energy saving",
            icon="mdi:leaf",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    # Thermostatic Radiator Valve
    # Not documented
    "wkf": (
        SwitchEntityDescription(
            key=DPCode.CHILD_LOCK,
            name="Child lock",
            icon="mdi:account-lock",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.WINDOW_CHECK,
            name="Open window detection",
            icon="mdi:window-open",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    # SIREN: Siren (switch) with Temperature and humidity sensor
    # https://developer.tuya.com/en/docs/iot/f?id=Kavck4sr3o5ek
    "wsdcg": (
        SwitchEntityDescription(
            key=DPCode.SWITCH,
            name="Switch",
            device_class=SwitchDeviceClass.OUTLET,
        ),
    ),
    # Ceiling Light
    # https://developer.tuya.com/en/docs/iot/ceiling-light?id=Kaiuz03xxfc4r
    "xdd": (
        SwitchEntityDescription(
            key=DPCode.DO_NOT_DISTURB,
            name="Do not disturb",
            icon="mdi:minus-circle-outline",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    # Diffuser
    # https://developer.tuya.com/en/docs/iot/categoryxxj?id=Kaiuz1f9mo6bl
    "xxj": (
        SwitchEntityDescription(
            key=DPCode.SWITCH,
            name="Power",
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_SPRAY,
            name="Spray",
            icon="mdi:spray",
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_VOICE,
            name="Voice",
            icon="mdi:account-voice",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    # Smart Electricity Meter
    # https://developer.tuya.com/en/docs/iot/smart-meter?id=Kaiuz4gv6ack7
    "zndb": (
        SwitchEntityDescription(
            key=DPCode.SWITCH,
            name="Switch",
        ),
    ),
    # Fan
    # https://developer.tuya.com/en/docs/iot/categoryfs?id=Kaiuz1xweel1c
    "fs": (
        SwitchEntityDescription(
            key=DPCode.ANION,
            name="Anion",
            icon="mdi:atom",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.HUMIDIFIER,
            name="Humidification",
            icon="mdi:air-humidifier",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.OXYGEN,
            name="Oxygen bar",
            icon="mdi:molecule",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.FAN_COOL,
            name="Natural wind",
            icon="mdi:weather-windy",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.FAN_BEEP,
            name="Sound",
            icon="mdi:minus-circle",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.CHILD_LOCK,
            name="Child lock",
            icon="mdi:account-lock",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    # Curtain
    # https://developer.tuya.com/en/docs/iot/f?id=K9gf46o5mtfyc
    "cl": (
        SwitchEntityDescription(
            key=DPCode.CONTROL_BACK,
            name="Reverse",
            icon="mdi:swap-horizontal",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.OPPOSITE,
            name="Reverse",
            icon="mdi:swap-horizontal",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    # Humidifier
    # https://developer.tuya.com/en/docs/iot/categoryjsq?id=Kaiuz1smr440b
    "jsq": (
        SwitchEntityDescription(
            key=DPCode.SWITCH_SOUND,
            name="Voice",
            icon="mdi:account-voice",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.SLEEP,
            name="Sleep",
            icon="mdi:power-sleep",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.STERILIZATION,
            name="Sterilization",
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
