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

# Commonly used, that are re-used in the select down below.
LANGUAGE_SELECT: tuple[SelectEntityDescription, ...] = (
    SelectEntityDescription(
        key=DPCode.LANGUAGE,
        entity_category=EntityCategory.CONFIG,
        icon="mdi:translate",
        entity_registry_enabled_default=False,
        translation_key="language",
    ),
)


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
    # Smart Lock
    # https://developer.tuya.com/en/docs/iot/f?id=Kb0o2vbzuzl81
    "ms": (
        SelectEntityDescription(
            key=DPCode.ALARM_VOLUME,
            entity_category=EntityCategory.CONFIG,
            icon="mdi:volume-high",
            translation_key="lock_alarm_volume",
        ),
        SelectEntityDescription(
            key=DPCode.BASIC_NIGHTVISION,
            entity_category=EntityCategory.CONFIG,
            icon="mdi:weather-night",
            translation_key="lock_basic_nightvision",
        ),
        SelectEntityDescription(
            key=DPCode.BEEP_VOLUME,
            entity_category=EntityCategory.CONFIG,
            icon="mdi:volume-high",
            translation_key="lock_voice_volume",
        ),
        SelectEntityDescription(
            key=DPCode.DOOR_UNCLOSED_TRIGGER,
            entity_category=EntityCategory.CONFIG,
            icon="mdi:timer-cog-outline",
            translation_key="lock_door_unclosed_trigger",
        ),
        SelectEntityDescription(
            key=DPCode.DOORBELL_SONG,
            entity_category=EntityCategory.CONFIG,
            icon="mdi:music-box-multiple-outline",
            translation_key="lock_doorbell_song",
        ),
        SelectEntityDescription(
            key=DPCode.DOORBELL_VOLUME,
            entity_category=EntityCategory.CONFIG,
            icon="mdi:volume-high",
            translation_key="lock_doorbell_volume",
        ),
        SelectEntityDescription(
            key=DPCode.KEY_TONE,
            entity_category=EntityCategory.CONFIG,
            icon="mdi:music-box-multiple-outline",
            translation_key="lock_keypress_volume",
        ),
        SelectEntityDescription(
            key=DPCode.LOCK_MOTOR_DIRECTION,
            entity_category=EntityCategory.CONFIG,
            icon="mdi:swap-horizontal",
            translation_key="lock_motor_direction",
        ),
        SelectEntityDescription(
            key=DPCode.LOW_POWER_THRESHOLD,
            entity_category=EntityCategory.CONFIG,
            icon="mdi:battery-alert-variant-outline",
            translation_key="lock_low_power_threshold",
        ),
        SelectEntityDescription(
            key=DPCode.MOTOR_TORQUE,
            entity_category=EntityCategory.CONFIG,
            icon="mdi:hexagon-multiple-outline",
            translation_key="lock_motor_torque",
        ),
        SelectEntityDescription(
            key=DPCode.OPEN_SPEED_STATE,
            entity_category=EntityCategory.CONFIG,
            icon="mdi:speedometer",
            translation_key="lock_open_speed_state",
        ),
        SelectEntityDescription(
            key=DPCode.PHOTO_MODE,
            entity_category=EntityCategory.CONFIG,
            icon="mdi:image-multiple-outline",
            translation_key="lock_photo_mode",
        ),
        SelectEntityDescription(
            key=DPCode.RINGTONE,
            entity_category=EntityCategory.CONFIG,
            icon="mdi:music-box-multiple-outline",
            translation_key="lock_ringtone",
        ),
        SelectEntityDescription(
            key=DPCode.SOUND_MODE,
            entity_category=EntityCategory.CONFIG,
            icon="mdi:music-box-multiple-outline",
            translation_key="lock_sound_mode",
        ),
        SelectEntityDescription(
            key=DPCode.STAY_ALARM_MODE,
            entity_category=EntityCategory.CONFIG,
            icon="mdi:star-box-multiple-outline",
            translation_key="lock_stay_alarm_mode",
        ),
        SelectEntityDescription(
            key=DPCode.STAY_CAPTURE_MODE,
            entity_category=EntityCategory.CONFIG,
            icon="mdi:image-multiple-outline",
            translation_key="lock_stay_capture_mode",
        ),
        SelectEntityDescription(
            key=DPCode.STAY_TRIGGER_DISTANCE,
            entity_category=EntityCategory.CONFIG,
            icon="mdi:signal-distance-variant",
            translation_key="lock_stay_trigger_distance",
        ),
        SelectEntityDescription(
            key=DPCode.UNLOCK_SWITCH,
            entity_category=EntityCategory.CONFIG,
            icon="mdi:shield-lock-open-outline",
            translation_key="lock_unlock_switch",
        ),
        *LANGUAGE_SELECT,
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
    # Smart Lock
    # https://developer.tuya.com/en/docs/iot/f?id=Kb0o2vbzuzl81
    "ms": (
        SelectEntityDescription(
            key=DPCode.ALARM_VOLUME,
            name="Alert Volume",
            entity_category=EntityCategory.CONFIG,
            icon="mdi:volume-high",
        ),
        SelectEntityDescription(
            key=DPCode.BASIC_NIGHTVISION,
            name="Infrared (IR) Night Vision",
            entity_category=EntityCategory.CONFIG,
            icon="mdi:weather-night",
        ),
        SelectEntityDescription(
            key=DPCode.BEEP_VOLUME,
            name="Local Voice Volume",
            entity_category=EntityCategory.CONFIG,
            icon="mdi:volume-high",
        ),
        SelectEntityDescription(
            key=DPCode.DOOR_UNCLOSED_TRIGGER,
            name="Trigger Time of Unclosed",
            entity_category=EntityCategory.CONFIG,
            icon="mdi:timer-cog-outline",
        ),
        SelectEntityDescription(
            key=DPCode.DOORBELL_SONG,
            name="Doorbell Ringtone",
            entity_category=EntityCategory.CONFIG,
            icon="mdi:music-box-multiple-outline",
        ),
        SelectEntityDescription(
            key=DPCode.DOORBELL_VOLUME,
            name="Doorbell Volume",
            entity_category=EntityCategory.CONFIG,
            icon="mdi:volume-high",
        ),
        SelectEntityDescription(
            key=DPCode.KEY_TONE,
            name="Volume on Keypress",
            entity_category=EntityCategory.CONFIG,
            icon="mdi:music-box-multiple-outline",
        ),
        SelectEntityDescription(
            key=DPCode.LOCK_MOTOR_DIRECTION,
            name="Rotation Direction of Motor",
            entity_category=EntityCategory.CONFIG,
            icon="mdi:swap-horizontal",
        ),
        SelectEntityDescription(
            key=DPCode.LOW_POWER_THRESHOLD,
            name="Low Battery Alert",
            entity_category=EntityCategory.CONFIG,
            icon="mdi:battery-alert-variant-outline",
        ),
        SelectEntityDescription(
            key=DPCode.MOTOR_TORQUE,
            name="Torque Force of Motor",
            entity_category=EntityCategory.CONFIG,
            icon="mdi:hexagon-multiple-outline",
        ),
        SelectEntityDescription(
            key=DPCode.OPEN_SPEED_STATE,
            name="Unlocking Speed",
            entity_category=EntityCategory.CONFIG,
            icon="mdi:speedometer",
        ),
        SelectEntityDescription(
            key=DPCode.PHOTO_MODE,
            name="Photo Mode",
            entity_category=EntityCategory.CONFIG,
            icon="mdi:image-multiple-outline",
        ),
        SelectEntityDescription(
            key=DPCode.RINGTONE,
            name="Local Ringtone",
            entity_category=EntityCategory.CONFIG,
            icon="mdi:music-box-multiple-outline",
        ),
        SelectEntityDescription(
            key=DPCode.SOUND_MODE,
            name="Sound Mode",
            entity_category=EntityCategory.CONFIG,
            icon="mdi:music-box-multiple-outline",
        ),
        SelectEntityDescription(
            key=DPCode.STAY_ALARM_MODE,
            name="Loitering Alert Mode",
            entity_category=EntityCategory.CONFIG,
            icon="mdi:star-box-multiple-outline",
        ),
        SelectEntityDescription(
            key=DPCode.STAY_CAPTURE_MODE,
            name="Loitering Photo Capture Mode",
            entity_category=EntityCategory.CONFIG,
            icon="mdi:image-multiple-outline",
        ),
        SelectEntityDescription(
            key=DPCode.STAY_TRIGGER_DISTANCE,
            name="Loitering Sensing Range",
            entity_category=EntityCategory.CONFIG,
            icon="mdi:signal-distance-variant",
        ),
        SelectEntityDescription(
            key=DPCode.UNLOCK_SWITCH,
            name="Unlock Mode",
            entity_category=EntityCategory.CONFIG,
            icon="mdi:shield-lock-open-outline",
        ),
        *LANGUAGE_SELECT,
    ),
}

# Socket (duplicate of `kg`)
# https://developer.tuya.com/en/docs/iot/s?id=K9gf7o5prgf7s
SELECTS["cz"] = SELECTS["kg"]

# Power Socket (duplicate of `kg`)
# https://developer.tuya.com/en/docs/iot/s?id=K9gf7o5prgf7s
SELECTS["pc"] = SELECTS["kg"]

# Lock (duplicate of 'ms')
# https://developer.tuya.com/en/docs/iot/f?id=Kb0o2vbzuzl81
SELECTS["bxx"] = SELECTS["ms"]
SELECTS["gyms"] = SELECTS["ms"]
SELECTS["jtmspro"] = SELECTS["ms"]
SELECTS["hotelms"] = SELECTS["ms"]
SELECTS["ms_category"] = SELECTS["ms"]
SELECTS["jtmsbh"] = SELECTS["ms"]
SELECTS["mk"] = SELECTS["ms"]
SELECTS["videolock"] = SELECTS["ms"]
SELECTS["photolock"] = SELECTS["ms"]


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
