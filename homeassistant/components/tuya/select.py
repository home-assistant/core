"""Support for Tuya select."""
from __future__ import annotations

from tuya_iot import TuyaDevice, TuyaDeviceManager

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HomeAssistantTuyaData
from .base import TuyaEntity
from .const import DOMAIN, TUYA_DISCOVERY_NEW, DPCode, DPType

# All descriptions can be found here. Mostly the Enum data types in the
# default instructions set of each category end up being a select.
# https://developer.tuya.com/en/docs/iot/standarddescription?id=K9i5ql6waswzq
SELECTS: dict[str, tuple[SelectEntityDescription, ...]] = {
    # Multi-functional Sensor
    # https://developer.tuya.com/en/docs/iot/categorydgnbj?id=Kaiuz3yorvzg3
    "dgnbj": (
        SelectEntityDescription(
            key=DPCode.ALARM_VOLUME,
            translation_key="volume",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    # Coffee maker
    # https://developer.tuya.com/en/docs/iot/categorykfj?id=Kaiuz2p12pc7f
    "kfj": (
        SelectEntityDescription(
            key=DPCode.CUP_NUMBER,
            translation_key="cups",
            icon="mdi:numeric",
        ),
        SelectEntityDescription(
            key=DPCode.CONCENTRATION_SET,
            translation_key="concentration",
            icon="mdi:altimeter",
            entity_category=EntityCategory.CONFIG,
        ),
        SelectEntityDescription(
            key=DPCode.MATERIAL,
            translation_key="material",
            entity_category=EntityCategory.CONFIG,
        ),
        SelectEntityDescription(
            key=DPCode.MODE,
            translation_key="mode",
            icon="mdi:coffee",
        ),
    ),
    # Switch
    # https://developer.tuya.com/en/docs/iot/s?id=K9gf7o5prgf7s
    "kg": (
        SelectEntityDescription(
            key=DPCode.RELAY_STATUS,
            entity_category=EntityCategory.CONFIG,
            translation_key="relay_status",
        ),
        SelectEntityDescription(
            key=DPCode.LIGHT_MODE,
            entity_category=EntityCategory.CONFIG,
            translation_key="light_mode",
        ),
    ),
    # Heater
    # https://developer.tuya.com/en/docs/iot/categoryqn?id=Kaiuz18kih0sm
    "qn": (
        SelectEntityDescription(
            key=DPCode.LEVEL,
            translation_key="temperature_level",
            icon="mdi:thermometer-lines",
        ),
    ),
    # Siren Alarm
    # https://developer.tuya.com/en/docs/iot/categorysgbj?id=Kaiuz37tlpbnu
    "sgbj": (
        SelectEntityDescription(
            key=DPCode.ALARM_VOLUME,
            translation_key="volume",
            entity_category=EntityCategory.CONFIG,
        ),
        SelectEntityDescription(
            key=DPCode.BRIGHT_STATE,
            translation_key="brightness",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    # Smart Camera
    # https://developer.tuya.com/en/docs/iot/categorysp?id=Kaiuz35leyo12
    "sp": (
        SelectEntityDescription(
            key=DPCode.IPC_WORK_MODE,
            entity_category=EntityCategory.CONFIG,
            translation_key="ipc_work_mode",
        ),
        SelectEntityDescription(
            key=DPCode.DECIBEL_SENSITIVITY,
            icon="mdi:volume-vibrate",
            entity_category=EntityCategory.CONFIG,
            translation_key="decibel_sensitivity",
        ),
        SelectEntityDescription(
            key=DPCode.RECORD_MODE,
            icon="mdi:record-rec",
            entity_category=EntityCategory.CONFIG,
            translation_key="record_mode",
        ),
        SelectEntityDescription(
            key=DPCode.BASIC_NIGHTVISION,
            icon="mdi:theme-light-dark",
            entity_category=EntityCategory.CONFIG,
            translation_key="basic_nightvision",
        ),
        SelectEntityDescription(
            key=DPCode.BASIC_ANTI_FLICKER,
            icon="mdi:image-outline",
            entity_category=EntityCategory.CONFIG,
            translation_key="basic_anti_flicker",
        ),
        SelectEntityDescription(
            key=DPCode.MOTION_SENSITIVITY,
            icon="mdi:motion-sensor",
            entity_category=EntityCategory.CONFIG,
            translation_key="motion_sensitivity",
        ),
    ),
    # IoT Switch?
    # Note: Undocumented
    "tdq": (
        SelectEntityDescription(
            key=DPCode.RELAY_STATUS,
            entity_category=EntityCategory.CONFIG,
            translation_key="relay_status",
        ),
        SelectEntityDescription(
            key=DPCode.LIGHT_MODE,
            entity_category=EntityCategory.CONFIG,
            translation_key="light_mode",
        ),
    ),
    # Dimmer Switch
    # https://developer.tuya.com/en/docs/iot/categorytgkg?id=Kaiuz0ktx7m0o
    "tgkg": (
        SelectEntityDescription(
            key=DPCode.RELAY_STATUS,
            entity_category=EntityCategory.CONFIG,
            translation_key="relay_status",
        ),
        SelectEntityDescription(
            key=DPCode.LIGHT_MODE,
            entity_category=EntityCategory.CONFIG,
            translation_key="light_mode",
        ),
        SelectEntityDescription(
            key=DPCode.LED_TYPE_1,
            entity_category=EntityCategory.CONFIG,
            translation_key="led_type",
        ),
        SelectEntityDescription(
            key=DPCode.LED_TYPE_2,
            entity_category=EntityCategory.CONFIG,
            translation_key="led_type_2",
        ),
        SelectEntityDescription(
            key=DPCode.LED_TYPE_3,
            entity_category=EntityCategory.CONFIG,
            translation_key="led_type_3",
        ),
    ),
    # Dimmer
    # https://developer.tuya.com/en/docs/iot/tgq?id=Kaof8ke9il4k4
    "tgq": (
        SelectEntityDescription(
            key=DPCode.LED_TYPE_1,
            entity_category=EntityCategory.CONFIG,
            translation_key="led_type",
        ),
        SelectEntityDescription(
            key=DPCode.LED_TYPE_2,
            entity_category=EntityCategory.CONFIG,
            translation_key="led_type_2",
        ),
    ),
    # Fingerbot
    "szjqr": (
        SelectEntityDescription(
            key=DPCode.MODE,
            entity_category=EntityCategory.CONFIG,
            translation_key="fingerbot_mode",
        ),
    ),
    # Robot Vacuum
    # https://developer.tuya.com/en/docs/iot/fsd?id=K9gf487ck1tlo
    "sd": (
        SelectEntityDescription(
            key=DPCode.CISTERN,
            entity_category=EntityCategory.CONFIG,
            icon="mdi:water-opacity",
            translation_key="vacuum_cistern",
        ),
        SelectEntityDescription(
            key=DPCode.COLLECTION_MODE,
            entity_category=EntityCategory.CONFIG,
            icon="mdi:air-filter",
            translation_key="vacuum_collection",
        ),
        SelectEntityDescription(
            key=DPCode.MODE,
            entity_category=EntityCategory.CONFIG,
            icon="mdi:layers-outline",
            translation_key="vacuum_mode",
        ),
    ),
    # Fan
    # https://developer.tuya.com/en/docs/iot/f?id=K9gf45vs7vkge
    "fs": (
        SelectEntityDescription(
            key=DPCode.FAN_VERTICAL,
            entity_category=EntityCategory.CONFIG,
            icon="mdi:format-vertical-align-center",
            translation_key="vertical_fan_angle",
        ),
        SelectEntityDescription(
            key=DPCode.FAN_HORIZONTAL,
            entity_category=EntityCategory.CONFIG,
            icon="mdi:format-horizontal-align-center",
            translation_key="horizontal_fan_angle",
        ),
        SelectEntityDescription(
            key=DPCode.COUNTDOWN,
            entity_category=EntityCategory.CONFIG,
            icon="mdi:timer-cog-outline",
            translation_key="countdown",
        ),
        SelectEntityDescription(
            key=DPCode.COUNTDOWN_SET,
            entity_category=EntityCategory.CONFIG,
            icon="mdi:timer-cog-outline",
            translation_key="countdown",
        ),
    ),
    # Curtain
    # https://developer.tuya.com/en/docs/iot/f?id=K9gf46o5mtfyc
    "cl": (
        SelectEntityDescription(
            key=DPCode.CONTROL_BACK_MODE,
            entity_category=EntityCategory.CONFIG,
            icon="mdi:swap-horizontal",
            translation_key="curtain_motor_mode",
        ),
        SelectEntityDescription(
            key=DPCode.MODE,
            entity_category=EntityCategory.CONFIG,
            translation_key="curtain_mode",
        ),
    ),
    # Humidifier
    # https://developer.tuya.com/en/docs/iot/categoryjsq?id=Kaiuz1smr440b
    "jsq": (
        SelectEntityDescription(
            key=DPCode.SPRAY_MODE,
            entity_category=EntityCategory.CONFIG,
            icon="mdi:spray",
            translation_key="humidifier_spray_mode",
        ),
        SelectEntityDescription(
            key=DPCode.LEVEL,
            entity_category=EntityCategory.CONFIG,
            icon="mdi:spray",
            translation_key="humidifier_level",
        ),
        SelectEntityDescription(
            key=DPCode.MOODLIGHTING,
            entity_category=EntityCategory.CONFIG,
            icon="mdi:lightbulb-multiple",
            translation_key="humidifier_moodlighting",
        ),
        SelectEntityDescription(
            key=DPCode.COUNTDOWN,
            entity_category=EntityCategory.CONFIG,
            icon="mdi:timer-cog-outline",
            translation_key="countdown",
        ),
        SelectEntityDescription(
            key=DPCode.COUNTDOWN_SET,
            entity_category=EntityCategory.CONFIG,
            icon="mdi:timer-cog-outline",
            translation_key="countdown",
        ),
    ),
    # Air Purifier
    # https://developer.tuya.com/en/docs/iot/f?id=K9gf46h2s6dzm
    "kj": (
        SelectEntityDescription(
            key=DPCode.COUNTDOWN,
            entity_category=EntityCategory.CONFIG,
            icon="mdi:timer-cog-outline",
            translation_key="countdown",
        ),
        SelectEntityDescription(
            key=DPCode.COUNTDOWN_SET,
            entity_category=EntityCategory.CONFIG,
            icon="mdi:timer-cog-outline",
            translation_key="countdown",
        ),
    ),
    # Dehumidifier
    # https://developer.tuya.com/en/docs/iot/categorycs?id=Kaiuz1vcz4dha
    "cs": (
        SelectEntityDescription(
            key=DPCode.COUNTDOWN_SET,
            entity_category=EntityCategory.CONFIG,
            icon="mdi:timer-cog-outline",
            translation_key="countdown",
        ),
        SelectEntityDescription(
            key=DPCode.DEHUMIDITY_SET_ENUM,
            translation_key="target_humidity",
            entity_category=EntityCategory.CONFIG,
            icon="mdi:water-percent",
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
                    if description.key in device.status:
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

        self._attr_options: list[str] = []
        if enum_type := self.find_dpcode(
            description.key, dptype=DPType.ENUM, prefer_function=True
        ):
            self._attr_options = enum_type.range

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
