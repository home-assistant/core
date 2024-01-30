"""Support for Tuya number."""
from __future__ import annotations

from tuya_sharing import CustomerDevice, Manager

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HomeAssistantTuyaData
from .base import IntegerTypeData, TuyaEntity
from .const import DEVICE_CLASS_UNITS, DOMAIN, TUYA_DISCOVERY_NEW, DPCode, DPType

# All descriptions can be found here. Mostly the Integer data types in the
# default instructions set of each category end up being a number.
# https://developer.tuya.com/en/docs/iot/standarddescription?id=K9i5ql6waswzq
NUMBERS: dict[str, tuple[NumberEntityDescription, ...]] = {
    # Multi-functional Sensor
    # https://developer.tuya.com/en/docs/iot/categorydgnbj?id=Kaiuz3yorvzg3
    "dgnbj": (
        NumberEntityDescription(
            key=DPCode.ALARM_TIME,
            translation_key="time",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    # Smart Kettle
    # https://developer.tuya.com/en/docs/iot/fbh?id=K9gf484m21yq7
    "bh": (
        NumberEntityDescription(
            key=DPCode.TEMP_SET,
            translation_key="temperature",
            device_class=NumberDeviceClass.TEMPERATURE,
            icon="mdi:thermometer",
            entity_category=EntityCategory.CONFIG,
        ),
        NumberEntityDescription(
            key=DPCode.TEMP_SET_F,
            translation_key="temperature",
            device_class=NumberDeviceClass.TEMPERATURE,
            icon="mdi:thermometer",
            entity_category=EntityCategory.CONFIG,
        ),
        NumberEntityDescription(
            key=DPCode.TEMP_BOILING_C,
            translation_key="temperature_after_boiling",
            device_class=NumberDeviceClass.TEMPERATURE,
            icon="mdi:thermometer",
            entity_category=EntityCategory.CONFIG,
        ),
        NumberEntityDescription(
            key=DPCode.TEMP_BOILING_F,
            translation_key="temperature_after_boiling",
            device_class=NumberDeviceClass.TEMPERATURE,
            icon="mdi:thermometer",
            entity_category=EntityCategory.CONFIG,
        ),
        NumberEntityDescription(
            key=DPCode.WARM_TIME,
            translation_key="heat_preservation_time",
            icon="mdi:timer",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    # Smart Pet Feeder
    # https://developer.tuya.com/en/docs/iot/categorycwwsq?id=Kaiuz2b6vydld
    "cwwsq": (
        NumberEntityDescription(
            key=DPCode.MANUAL_FEED,
            translation_key="feed",
            icon="mdi:bowl",
        ),
        NumberEntityDescription(
            key=DPCode.VOICE_TIMES,
            translation_key="voice_times",
            icon="mdi:microphone",
        ),
    ),
    # Human Presence Sensor
    # https://developer.tuya.com/en/docs/iot/categoryhps?id=Kaiuz42yhn1hs
    "hps": (
        NumberEntityDescription(
            key=DPCode.SENSITIVITY,
            translation_key="sensitivity",
            entity_category=EntityCategory.CONFIG,
        ),
        NumberEntityDescription(
            key=DPCode.NEAR_DETECTION,
            translation_key="near_detection",
            icon="mdi:signal-distance-variant",
            entity_category=EntityCategory.CONFIG,
        ),
        NumberEntityDescription(
            key=DPCode.FAR_DETECTION,
            translation_key="far_detection",
            icon="mdi:signal-distance-variant",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    # Coffee maker
    # https://developer.tuya.com/en/docs/iot/categorykfj?id=Kaiuz2p12pc7f
    "kfj": (
        NumberEntityDescription(
            key=DPCode.WATER_SET,
            translation_key="water_level",
            icon="mdi:cup-water",
            entity_category=EntityCategory.CONFIG,
        ),
        NumberEntityDescription(
            key=DPCode.TEMP_SET,
            translation_key="temperature",
            device_class=NumberDeviceClass.TEMPERATURE,
            icon="mdi:thermometer",
            entity_category=EntityCategory.CONFIG,
        ),
        NumberEntityDescription(
            key=DPCode.WARM_TIME,
            translation_key="heat_preservation_time",
            icon="mdi:timer",
            entity_category=EntityCategory.CONFIG,
        ),
        NumberEntityDescription(
            key=DPCode.POWDER_SET,
            translation_key="powder",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    # Sous Vide Cooker
    # https://developer.tuya.com/en/docs/iot/categorymzj?id=Kaiuz2vy130ux
    "mzj": (
        NumberEntityDescription(
            key=DPCode.COOK_TEMPERATURE,
            translation_key="cook_temperature",
            icon="mdi:thermometer",
            entity_category=EntityCategory.CONFIG,
        ),
        NumberEntityDescription(
            key=DPCode.COOK_TIME,
            translation_key="cook_time",
            icon="mdi:timer",
            native_unit_of_measurement=UnitOfTime.MINUTES,
            entity_category=EntityCategory.CONFIG,
        ),
        NumberEntityDescription(
            key=DPCode.CLOUD_RECIPE_NUMBER,
            translation_key="cloud_recipe",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    # Robot Vacuum
    # https://developer.tuya.com/en/docs/iot/fsd?id=K9gf487ck1tlo
    "sd": (
        NumberEntityDescription(
            key=DPCode.VOLUME_SET,
            translation_key="volume",
            icon="mdi:volume-high",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    # Siren Alarm
    # https://developer.tuya.com/en/docs/iot/categorysgbj?id=Kaiuz37tlpbnu
    "sgbj": (
        NumberEntityDescription(
            key=DPCode.ALARM_TIME,
            translation_key="time",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    # Smart Camera
    # https://developer.tuya.com/en/docs/iot/categorysp?id=Kaiuz35leyo12
    "sp": (
        NumberEntityDescription(
            key=DPCode.BASIC_DEVICE_VOLUME,
            translation_key="volume",
            icon="mdi:volume-high",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    # Dimmer Switch
    # https://developer.tuya.com/en/docs/iot/categorytgkg?id=Kaiuz0ktx7m0o
    "tgkg": (
        NumberEntityDescription(
            key=DPCode.BRIGHTNESS_MIN_1,
            translation_key="minimum_brightness",
            icon="mdi:lightbulb-outline",
            entity_category=EntityCategory.CONFIG,
        ),
        NumberEntityDescription(
            key=DPCode.BRIGHTNESS_MAX_1,
            translation_key="maximum_brightness",
            icon="mdi:lightbulb-on-outline",
            entity_category=EntityCategory.CONFIG,
        ),
        NumberEntityDescription(
            key=DPCode.BRIGHTNESS_MIN_2,
            translation_key="minimum_brightness_2",
            icon="mdi:lightbulb-outline",
            entity_category=EntityCategory.CONFIG,
        ),
        NumberEntityDescription(
            key=DPCode.BRIGHTNESS_MAX_2,
            translation_key="maximum_brightness_2",
            icon="mdi:lightbulb-on-outline",
            entity_category=EntityCategory.CONFIG,
        ),
        NumberEntityDescription(
            key=DPCode.BRIGHTNESS_MIN_3,
            translation_key="minimum_brightness_3",
            icon="mdi:lightbulb-outline",
            entity_category=EntityCategory.CONFIG,
        ),
        NumberEntityDescription(
            key=DPCode.BRIGHTNESS_MAX_3,
            translation_key="maximum_brightness_3",
            icon="mdi:lightbulb-on-outline",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    # Dimmer Switch
    # https://developer.tuya.com/en/docs/iot/categorytgkg?id=Kaiuz0ktx7m0o
    "tgq": (
        NumberEntityDescription(
            key=DPCode.BRIGHTNESS_MIN_1,
            translation_key="minimum_brightness",
            icon="mdi:lightbulb-outline",
            entity_category=EntityCategory.CONFIG,
        ),
        NumberEntityDescription(
            key=DPCode.BRIGHTNESS_MAX_1,
            translation_key="maximum_brightness",
            icon="mdi:lightbulb-on-outline",
            entity_category=EntityCategory.CONFIG,
        ),
        NumberEntityDescription(
            key=DPCode.BRIGHTNESS_MIN_2,
            translation_key="minimum_brightness_2",
            icon="mdi:lightbulb-outline",
            entity_category=EntityCategory.CONFIG,
        ),
        NumberEntityDescription(
            key=DPCode.BRIGHTNESS_MAX_2,
            translation_key="maximum_brightness_2",
            icon="mdi:lightbulb-on-outline",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    # Vibration Sensor
    # https://developer.tuya.com/en/docs/iot/categoryzd?id=Kaiuz3a5vrzno
    "zd": (
        NumberEntityDescription(
            key=DPCode.SENSITIVITY,
            translation_key="sensitivity",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    # Fingerbot
    "szjqr": (
        NumberEntityDescription(
            key=DPCode.ARM_DOWN_PERCENT,
            translation_key="move_down",
            icon="mdi:arrow-down-bold",
            native_unit_of_measurement=PERCENTAGE,
            entity_category=EntityCategory.CONFIG,
        ),
        NumberEntityDescription(
            key=DPCode.ARM_UP_PERCENT,
            translation_key="move_up",
            icon="mdi:arrow-up-bold",
            native_unit_of_measurement=PERCENTAGE,
            entity_category=EntityCategory.CONFIG,
        ),
        NumberEntityDescription(
            key=DPCode.CLICK_SUSTAIN_TIME,
            translation_key="down_delay",
            icon="mdi:timer",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    # Fan
    # https://developer.tuya.com/en/docs/iot/categoryfs?id=Kaiuz1xweel1c
    "fs": (
        NumberEntityDescription(
            key=DPCode.TEMP,
            translation_key="temperature",
            device_class=NumberDeviceClass.TEMPERATURE,
            icon="mdi:thermometer-lines",
        ),
    ),
    # Humidifier
    # https://developer.tuya.com/en/docs/iot/categoryjsq?id=Kaiuz1smr440b
    "jsq": (
        NumberEntityDescription(
            key=DPCode.TEMP_SET,
            translation_key="temperature",
            device_class=NumberDeviceClass.TEMPERATURE,
            icon="mdi:thermometer-lines",
        ),
        NumberEntityDescription(
            key=DPCode.TEMP_SET_F,
            translation_key="temperature",
            device_class=NumberDeviceClass.TEMPERATURE,
            icon="mdi:thermometer-lines",
        ),
    ),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Tuya number dynamically through Tuya discovery."""
    hass_data: HomeAssistantTuyaData = hass.data[DOMAIN][entry.entry_id]

    @callback
    def async_discover_device(device_ids: list[str]) -> None:
        """Discover and add a discovered Tuya number."""
        entities: list[TuyaNumberEntity] = []
        for device_id in device_ids:
            device = hass_data.manager.device_map[device_id]
            if descriptions := NUMBERS.get(device.category):
                for description in descriptions:
                    if description.key in device.status:
                        entities.append(
                            TuyaNumberEntity(device, hass_data.manager, description)
                        )

        async_add_entities(entities)

    async_discover_device([*hass_data.manager.device_map])

    entry.async_on_unload(
        async_dispatcher_connect(hass, TUYA_DISCOVERY_NEW, async_discover_device)
    )


class TuyaNumberEntity(TuyaEntity, NumberEntity):
    """Tuya Number Entity."""

    _number: IntegerTypeData | None = None

    def __init__(
        self,
        device: CustomerDevice,
        device_manager: Manager,
        description: NumberEntityDescription,
    ) -> None:
        """Init Tuya sensor."""
        super().__init__(device, device_manager)
        self.entity_description = description
        self._attr_unique_id = f"{super().unique_id}{description.key}"

        if int_type := self.find_dpcode(
            description.key, dptype=DPType.INTEGER, prefer_function=True
        ):
            self._number = int_type
            self._attr_native_max_value = self._number.max_scaled
            self._attr_native_min_value = self._number.min_scaled
            self._attr_native_step = self._number.step_scaled

        # Logic to ensure the set device class and API received Unit Of Measurement
        # match Home Assistants requirements.
        if (
            self.device_class is not None
            and not self.device_class.startswith(DOMAIN)
            and description.native_unit_of_measurement is None
        ):
            # We cannot have a device class, if the UOM isn't set or the
            # device class cannot be found in the validation mapping.
            if (
                self.native_unit_of_measurement is None
                or self.device_class not in DEVICE_CLASS_UNITS
            ):
                self._attr_device_class = None
                return

            uoms = DEVICE_CLASS_UNITS[self.device_class]
            self._uom = uoms.get(self.native_unit_of_measurement) or uoms.get(
                self.native_unit_of_measurement.lower()
            )

            # Unknown unit of measurement, device class should not be used.
            if self._uom is None:
                self._attr_device_class = None
                return

            # If we still have a device class, we should not use an icon
            if self.device_class:
                self._attr_icon = None

            # Found unit of measurement, use the standardized Unit
            # Use the target conversion unit (if set)
            self._attr_native_unit_of_measurement = (
                self._uom.conversion_unit or self._uom.unit
            )

    @property
    def native_value(self) -> float | None:
        """Return the entity value to represent the entity state."""
        # Unknown or unsupported data type
        if self._number is None:
            return None

        # Raw value
        if (value := self.device.status.get(self.entity_description.key)) is None:
            return None

        return self._number.scale_value(value)

    def set_native_value(self, value: float) -> None:
        """Set new value."""
        if self._number is None:
            raise RuntimeError("Cannot set value, device doesn't provide type data")

        self._send_command(
            [
                {
                    "code": self.entity_description.key,
                    "value": self._number.scale_value_back(value),
                }
            ]
        )
