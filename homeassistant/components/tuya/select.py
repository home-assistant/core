"""Support for Tuya select."""
from __future__ import annotations

from typing import cast

from tuya_iot import TuyaDevice, TuyaDeviceManager
from tuya_iot.device import TuyaDeviceStatusRange

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ENTITY_CATEGORY_CONFIG
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HomeAssistantTuyaData
from .base import EnumTypeData, TuyaEntity
from .const import (
    DEVICE_CLASS_TUYA_BASIC_ANTI_FLICKR,
    DEVICE_CLASS_TUYA_BASIC_NIGHTVISION,
    DEVICE_CLASS_TUYA_DECIBEL_SENSITIVITY,
    DEVICE_CLASS_TUYA_IPC_WORK_MODE,
    DEVICE_CLASS_TUYA_LED_TYPE,
    DEVICE_CLASS_TUYA_LIGHT_MODE,
    DEVICE_CLASS_TUYA_MOTION_SENSITIVITY,
    DEVICE_CLASS_TUYA_RECORD_MODE,
    DEVICE_CLASS_TUYA_RELAY_STATUS,
    DOMAIN,
    TUYA_DISCOVERY_NEW,
    DPCode,
)

# All descriptions can be found here. Mostly the Enum data types in the
# default instructions set of each category end up being a select.
# https://developer.tuya.com/en/docs/iot/standarddescription?id=K9i5ql6waswzq
SELECTS: dict[str, tuple[SelectEntityDescription, ...]] = {
    # Coffee maker
    # https://developer.tuya.com/en/docs/iot/categorykfj?id=Kaiuz2p12pc7f
    "kfj": (
        SelectEntityDescription(
            key=DPCode.CUP_NUMBER,
            name="Cups",
            icon="mdi:numeric",
        ),
        SelectEntityDescription(
            key=DPCode.CONCENTRATION_SET,
            name="Concentration",
            icon="mdi:altimeter",
            entity_category=ENTITY_CATEGORY_CONFIG,
        ),
        SelectEntityDescription(
            key=DPCode.MATERIAL,
            name="Material",
            entity_category=ENTITY_CATEGORY_CONFIG,
        ),
        SelectEntityDescription(
            key=DPCode.MODE,
            name="Mode",
            icon="mdi:coffee",
        ),
    ),
    # Switch
    # https://developer.tuya.com/en/docs/iot/s?id=K9gf7o5prgf7s
    "kg": (
        SelectEntityDescription(
            key=DPCode.RELAY_STATUS,
            name="Power on Behavior",
            device_class=DEVICE_CLASS_TUYA_RELAY_STATUS,
            entity_category=ENTITY_CATEGORY_CONFIG,
        ),
        SelectEntityDescription(
            key=DPCode.LIGHT_MODE,
            name="Indicator Light Mode",
            device_class=DEVICE_CLASS_TUYA_LIGHT_MODE,
            entity_category=ENTITY_CATEGORY_CONFIG,
        ),
    ),
    # Heater
    # https://developer.tuya.com/en/docs/iot/categoryqn?id=Kaiuz18kih0sm
    "qn": (
        SelectEntityDescription(
            key=DPCode.LEVEL,
            name="Temperature Level",
            icon="mdi:thermometer-lines",
        ),
    ),
    # Siren Alarm
    # https://developer.tuya.com/en/docs/iot/categorysgbj?id=Kaiuz37tlpbnu
    "sgbj": (
        SelectEntityDescription(
            key=DPCode.ALARM_VOLUME,
            name="Volume",
            entity_category=ENTITY_CATEGORY_CONFIG,
        ),
        SelectEntityDescription(
            key=DPCode.BRIGHT_STATE,
            name="Brightness",
            entity_category=ENTITY_CATEGORY_CONFIG,
        ),
    ),
    # Smart Camera
    # https://developer.tuya.com/en/docs/iot/categorysp?id=Kaiuz35leyo12
    "sp": (
        SelectEntityDescription(
            key=DPCode.IPC_WORK_MODE,
            name="IPC Mode",
            device_class=DEVICE_CLASS_TUYA_IPC_WORK_MODE,
            entity_category=ENTITY_CATEGORY_CONFIG,
        ),
        SelectEntityDescription(
            key=DPCode.DECIBEL_SENSITIVITY,
            name="Sound Detection Sensitivity",
            icon="mdi:volume-vibrate",
            device_class=DEVICE_CLASS_TUYA_DECIBEL_SENSITIVITY,
            entity_category=ENTITY_CATEGORY_CONFIG,
        ),
        SelectEntityDescription(
            key=DPCode.RECORD_MODE,
            name="Record Mode",
            icon="mdi:record-rec",
            device_class=DEVICE_CLASS_TUYA_RECORD_MODE,
            entity_category=ENTITY_CATEGORY_CONFIG,
        ),
        SelectEntityDescription(
            key=DPCode.BASIC_NIGHTVISION,
            name="Night Vision",
            icon="mdi:theme-light-dark",
            device_class=DEVICE_CLASS_TUYA_BASIC_NIGHTVISION,
            entity_category=ENTITY_CATEGORY_CONFIG,
        ),
        SelectEntityDescription(
            key=DPCode.BASIC_ANTI_FLICKER,
            name="Anti-flicker",
            icon="mdi:image-outline",
            device_class=DEVICE_CLASS_TUYA_BASIC_ANTI_FLICKR,
            entity_category=ENTITY_CATEGORY_CONFIG,
        ),
        SelectEntityDescription(
            key=DPCode.MOTION_SENSITIVITY,
            name="Motion Detection Sensitivity",
            icon="mdi:motion-sensor",
            device_class=DEVICE_CLASS_TUYA_MOTION_SENSITIVITY,
            entity_category=ENTITY_CATEGORY_CONFIG,
        ),
    ),
    # IoT Switch?
    # Note: Undocumented
    "tdq": (
        SelectEntityDescription(
            key=DPCode.RELAY_STATUS,
            name="Power on Behavior",
            device_class=DEVICE_CLASS_TUYA_RELAY_STATUS,
            entity_category=ENTITY_CATEGORY_CONFIG,
        ),
        SelectEntityDescription(
            key=DPCode.LIGHT_MODE,
            name="Indicator Light Mode",
            device_class=DEVICE_CLASS_TUYA_LIGHT_MODE,
            entity_category=ENTITY_CATEGORY_CONFIG,
        ),
    ),
    # Dimmer Switch
    # https://developer.tuya.com/en/docs/iot/categorytgkg?id=Kaiuz0ktx7m0o
    "tgkg": (
        SelectEntityDescription(
            key=DPCode.RELAY_STATUS,
            name="Power on Behavior",
            device_class=DEVICE_CLASS_TUYA_RELAY_STATUS,
            entity_category=ENTITY_CATEGORY_CONFIG,
        ),
        SelectEntityDescription(
            key=DPCode.LIGHT_MODE,
            name="Indicator Light Mode",
            device_class=DEVICE_CLASS_TUYA_LIGHT_MODE,
            entity_category=ENTITY_CATEGORY_CONFIG,
        ),
        SelectEntityDescription(
            key=DPCode.LED_TYPE_1,
            name="Light Source Type",
            device_class=DEVICE_CLASS_TUYA_LED_TYPE,
            entity_category=ENTITY_CATEGORY_CONFIG,
        ),
        SelectEntityDescription(
            key=DPCode.LED_TYPE_2,
            name="Light 2 Source Type",
            device_class=DEVICE_CLASS_TUYA_LED_TYPE,
            entity_category=ENTITY_CATEGORY_CONFIG,
        ),
        SelectEntityDescription(
            key=DPCode.LED_TYPE_3,
            name="Light 3 Source Type",
            device_class=DEVICE_CLASS_TUYA_LED_TYPE,
            entity_category=ENTITY_CATEGORY_CONFIG,
        ),
    ),
    # Dimmer
    # https://developer.tuya.com/en/docs/iot/tgq?id=Kaof8ke9il4k4
    "tgq": (
        SelectEntityDescription(
            key=DPCode.LED_TYPE_1,
            name="Light Source Type",
            device_class=DEVICE_CLASS_TUYA_LED_TYPE,
            entity_category=ENTITY_CATEGORY_CONFIG,
        ),
        SelectEntityDescription(
            key=DPCode.LED_TYPE_2,
            name="Light 2 Source Type",
            device_class=DEVICE_CLASS_TUYA_LED_TYPE,
            entity_category=ENTITY_CATEGORY_CONFIG,
        ),
    ),
}


# Socket (duplicate of `kg`)
# https://developer.tuya.com/en/docs/iot/s?id=K9gf7o5prgf7s
SELECTS["cz"] = SELECTS["kg"]

# Power Socket (duplicate of `kg`)
# https://developer.tuya.com/en/docs/iot/s?id=K9gf7o5prgf7s
SELECTS["pc"] = SELECTS["kg"]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Tuya select dynamically through Tuya discovery."""
    hass_data: HomeAssistantTuyaData = hass.data[DOMAIN][entry.entry_id]

    @callback
    def async_discover_device(device_ids: list[str]) -> None:
        """Discover and add a discovered Tuya select."""
        entities: list[TuyaSelectEntity] = []
        for device_id in device_ids:
            device = hass_data.device_manager.device_map[device_id]
            if descriptions := SELECTS.get(device.category):
                for description in descriptions:
                    if (
                        description.key in device.function
                        or description.key in device.status
                    ):
                        entities.append(
                            TuyaSelectEntity(
                                device, hass_data.device_manager, description
                            )
                        )

        async_add_entities(entities)

    async_discover_device([*hass_data.device_manager.device_map])

    entry.async_on_unload(
        async_dispatcher_connect(hass, TUYA_DISCOVERY_NEW, async_discover_device)
    )


class TuyaSelectEntity(TuyaEntity, SelectEntity):
    """Tuya Select Entity."""

    def __init__(
        self,
        device: TuyaDevice,
        device_manager: TuyaDeviceManager,
        description: SelectEntityDescription,
    ) -> None:
        """Init Tuya sensor."""
        super().__init__(device, device_manager)
        self.entity_description = description
        self._attr_unique_id = f"{super().unique_id}{description.key}"

        self._attr_opions: list[str] = []
        if status_range := device.status_range.get(description.key):
            self._status_range = cast(TuyaDeviceStatusRange, status_range)

            # Extract type data from enum status range,
            if self._status_range.type == "Enum":
                type_data = EnumTypeData.from_json(self._status_range.values)
                self._attr_options = type_data.range

    @property
    def current_option(self) -> str | None:
        """Return the selected entity option to represent the entity state."""
        # Raw value
        value = self.device.status.get(self.entity_description.key)
        if value is None or value not in self._attr_options:
            return None

        return value

    def select_option(self, option: str) -> None:
        """Change the selected option."""
        self._send_command(
            [
                {
                    "code": self.entity_description.key,
                    "value": option,
                }
            ]
        )
