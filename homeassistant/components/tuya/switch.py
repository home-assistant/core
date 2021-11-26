"""Support for Tuya switches."""
from __future__ import annotations

from typing import Any

from tuya_iot import TuyaDevice, TuyaDeviceManager

from homeassistant.components.switch import (
    DEVICE_CLASS_OUTLET,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ENTITY_CATEGORY_CONFIG
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
            name="Heat Preservation",
            entity_category=ENTITY_CATEGORY_CONFIG,
        ),
    ),
    # Pet Water Feeder
    # https://developer.tuya.com/en/docs/iot/f?id=K9gf46aewxem5
    "cwysj": (
        SwitchEntityDescription(
            key=DPCode.FILTER_RESET,
            name="Filter reset",
            icon="mdi:filter",
            entity_category=ENTITY_CATEGORY_CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.PUMP_RESET,
            name="Water pump reset",
            icon="mdi:pump",
            entity_category=ENTITY_CATEGORY_CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH,
            name="Power",
        ),
        SwitchEntityDescription(
            key=DPCode.WATER_RESET,
            name="Reset of water usage days",
            icon="mdi:water-sync",
            entity_category=ENTITY_CATEGORY_CONFIG,
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
            name="Child Lock",
            icon="mdi:account-lock",
            entity_category=ENTITY_CATEGORY_CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_1,
            name="Switch",
        ),
    ),
    # Switch
    # https://developer.tuya.com/en/docs/iot/s?id=K9gf7o5prgf7s
    "kg": (
        SwitchEntityDescription(
            key=DPCode.CHILD_LOCK,
            name="Child Lock",
            icon="mdi:account-lock",
            entity_category=ENTITY_CATEGORY_CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_1,
            name="Switch 1",
            device_class=DEVICE_CLASS_OUTLET,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_2,
            name="Switch 2",
            device_class=DEVICE_CLASS_OUTLET,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_3,
            name="Switch 3",
            device_class=DEVICE_CLASS_OUTLET,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_4,
            name="Switch 4",
            device_class=DEVICE_CLASS_OUTLET,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_5,
            name="Switch 5",
            device_class=DEVICE_CLASS_OUTLET,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_6,
            name="Switch 6",
            device_class=DEVICE_CLASS_OUTLET,
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
            device_class=DEVICE_CLASS_OUTLET,
        ),
    ),
    # Air Purifier
    # https://developer.tuya.com/en/docs/iot/f?id=K9gf46h2s6dzm
    "kj": (
        SwitchEntityDescription(
            key=DPCode.ANION,
            name="Ionizer",
            icon="mdi:minus-circle-outline",
            entity_category=ENTITY_CATEGORY_CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.FILTER_RESET,
            name="Filter cartridge reset",
            icon="mdi:filter",
            entity_category=ENTITY_CATEGORY_CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.LOCK,
            name="Child lock",
            icon="mdi:account-lock",
            entity_category=ENTITY_CATEGORY_CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH,
            name="Power",
        ),
        SwitchEntityDescription(
            key=DPCode.WET,
            name="Humidification",
            icon="mdi:water-percent",
            entity_category=ENTITY_CATEGORY_CONFIG,
        ),
    ),
    # Air conditioner
    # https://developer.tuya.com/en/docs/iot/categorykt?id=Kaiuz0z71ov2n
    "kt": (
        SwitchEntityDescription(
            key=DPCode.ANION,
            name="Ionizer",
            icon="mdi:minus-circle-outline",
            entity_category=ENTITY_CATEGORY_CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.LOCK,
            name="Child Lock",
            icon="mdi:account-lock",
            entity_category=ENTITY_CATEGORY_CONFIG,
        ),
    ),
    # Power Socket
    # https://developer.tuya.com/en/docs/iot/s?id=K9gf7o5prgf7s
    "pc": (
        SwitchEntityDescription(
            key=DPCode.CHILD_LOCK,
            name="Child Lock",
            icon="mdi:account-lock",
            entity_category=ENTITY_CATEGORY_CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_1,
            name="Socket 1",
            device_class=DEVICE_CLASS_OUTLET,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_2,
            name="Socket 2",
            device_class=DEVICE_CLASS_OUTLET,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_3,
            name="Socket 3",
            device_class=DEVICE_CLASS_OUTLET,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_4,
            name="Socket 4",
            device_class=DEVICE_CLASS_OUTLET,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_5,
            name="Socket 5",
            device_class=DEVICE_CLASS_OUTLET,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_6,
            name="Socket 6",
            device_class=DEVICE_CLASS_OUTLET,
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
            device_class=DEVICE_CLASS_OUTLET,
        ),
    ),
    # Heater
    # https://developer.tuya.com/en/docs/iot/categoryqn?id=Kaiuz18kih0sm
    "qn": (
        SwitchEntityDescription(
            key=DPCode.ANION,
            name="Ionizer",
            icon="mdi:minus-circle-outline",
            entity_category=ENTITY_CATEGORY_CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.LOCK,
            name="Child Lock",
            icon="mdi:account-lock",
            entity_category=ENTITY_CATEGORY_CONFIG,
        ),
    ),
    # Robot Vacuum
    # https://developer.tuya.com/en/docs/iot/fsd?id=K9gf487ck1tlo
    "sd": (
        SwitchEntityDescription(
            key=DPCode.SWITCH_DISTURB,
            name="Do Not Disturb",
            icon="mdi:minus-circle",
            entity_category=ENTITY_CATEGORY_CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.VOICE_SWITCH,
            name="Voice",
            icon="mdi:account-voice",
            entity_category=ENTITY_CATEGORY_CONFIG,
        ),
    ),
    # Siren Alarm
    # https://developer.tuya.com/en/docs/iot/categorysgbj?id=Kaiuz37tlpbnu
    "sgbj": (
        SwitchEntityDescription(
            key=DPCode.MUFFLING,
            name="Mute",
            entity_category=ENTITY_CATEGORY_CONFIG,
        ),
    ),
    # Smart Camera
    # https://developer.tuya.com/en/docs/iot/categorysp?id=Kaiuz35leyo12
    "sp": (
        SwitchEntityDescription(
            key=DPCode.WIRELESS_BATTERYLOCK,
            name="Battery Lock",
            icon="mdi:battery-lock",
            entity_category=ENTITY_CATEGORY_CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.CRY_DETECTION_SWITCH,
            icon="mdi:emoticon-cry",
            name="Cry Detection",
            entity_category=ENTITY_CATEGORY_CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.DECIBEL_SWITCH,
            icon="mdi:microphone-outline",
            name="Sound Detection",
            entity_category=ENTITY_CATEGORY_CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.RECORD_SWITCH,
            icon="mdi:record-rec",
            name="Video Recording",
            entity_category=ENTITY_CATEGORY_CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.MOTION_RECORD,
            icon="mdi:record-rec",
            name="Motion Recording",
            entity_category=ENTITY_CATEGORY_CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.BASIC_PRIVATE,
            icon="mdi:eye-off",
            name="Privacy Mode",
            entity_category=ENTITY_CATEGORY_CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.BASIC_FLIP,
            icon="mdi:flip-horizontal",
            name="Flip",
            entity_category=ENTITY_CATEGORY_CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.BASIC_OSD,
            icon="mdi:watermark",
            name="Time Watermark",
            entity_category=ENTITY_CATEGORY_CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.BASIC_WDR,
            icon="mdi:watermark",
            name="Wide Dynamic Range",
            entity_category=ENTITY_CATEGORY_CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.MOTION_TRACKING,
            icon="mdi:motion-sensor",
            name="Motion Tracking",
            entity_category=ENTITY_CATEGORY_CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.MOTION_SWITCH,
            icon="mdi:motion-sensor",
            name="Motion Alarm",
            entity_category=ENTITY_CATEGORY_CONFIG,
        ),
    ),
    # IoT Switch?
    # Note: Undocumented
    "tdq": (
        SwitchEntityDescription(
            key=DPCode.SWITCH_1,
            name="Switch 1",
            device_class=DEVICE_CLASS_OUTLET,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_2,
            name="Switch 2",
            device_class=DEVICE_CLASS_OUTLET,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH_3,
            name="Switch 3",
            device_class=DEVICE_CLASS_OUTLET,
        ),
        SwitchEntityDescription(
            key=DPCode.CHILD_LOCK,
            name="Child Lock",
            icon="mdi:account-lock",
            entity_category=ENTITY_CATEGORY_CONFIG,
        ),
    ),
    # Solar Light
    # https://developer.tuya.com/en/docs/iot/tynd?id=Kaof8j02e1t98
    "tyndj": (
        SwitchEntityDescription(
            key=DPCode.SWITCH_SAVE_ENERGY,
            name="Energy Saving",
            icon="mdi:leaf",
            entity_category=ENTITY_CATEGORY_CONFIG,
        ),
    ),
    # Ceiling Light
    # https://developer.tuya.com/en/docs/iot/ceiling-light?id=Kaiuz03xxfc4r
    "xdd": (
        SwitchEntityDescription(
            key=DPCode.DO_NOT_DISTURB,
            name="Do not disturb",
            icon="mdi:minus-circle-outline",
            entity_category=ENTITY_CATEGORY_CONFIG,
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
            entity_category=ENTITY_CATEGORY_CONFIG,
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
                    if (
                        description.key in device.function
                        or description.key in device.status
                    ):
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
