"""Support for Tuya number."""

from __future__ import annotations

from tuya_sharing import CustomerDevice, Manager

from homeassistant.components.number import (
    DEVICE_CLASS_UNITS as NUMBER_DEVICE_CLASS_UNITS,
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import TuyaConfigEntry
from .const import (
    DEVICE_CLASS_UNITS,
    DOMAIN,
    LOGGER,
    TUYA_DISCOVERY_NEW,
    DeviceCategory,
    DPCode,
    DPType,
)
from .entity import TuyaEntity
from .models import IntegerTypeData
from .util import ActionDPCodeNotFoundError

NUMBERS: dict[DeviceCategory, tuple[NumberEntityDescription, ...]] = {
    DeviceCategory.BH: (
        NumberEntityDescription(
            key=DPCode.TEMP_SET,
            translation_key="temperature",
            device_class=NumberDeviceClass.TEMPERATURE,
            entity_category=EntityCategory.CONFIG,
        ),
        NumberEntityDescription(
            key=DPCode.TEMP_SET_F,
            translation_key="temperature",
            device_class=NumberDeviceClass.TEMPERATURE,
            entity_category=EntityCategory.CONFIG,
        ),
        NumberEntityDescription(
            key=DPCode.TEMP_BOILING_C,
            translation_key="temperature_after_boiling",
            device_class=NumberDeviceClass.TEMPERATURE,
            entity_category=EntityCategory.CONFIG,
        ),
        NumberEntityDescription(
            key=DPCode.TEMP_BOILING_F,
            translation_key="temperature_after_boiling",
            device_class=NumberDeviceClass.TEMPERATURE,
            entity_category=EntityCategory.CONFIG,
        ),
        NumberEntityDescription(
            key=DPCode.WARM_TIME,
            translation_key="heat_preservation_time",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.BZYD: (
        NumberEntityDescription(
            key=DPCode.VOLUME_SET,
            translation_key="volume",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.CO2BJ: (
        NumberEntityDescription(
            key=DPCode.ALARM_TIME,
            translation_key="alarm_duration",
            native_unit_of_measurement=UnitOfTime.SECONDS,
            device_class=NumberDeviceClass.DURATION,
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.CWWSQ: (
        NumberEntityDescription(
            key=DPCode.MANUAL_FEED,
            translation_key="feed",
        ),
        NumberEntityDescription(
            key=DPCode.VOICE_TIMES,
            translation_key="voice_times",
        ),
    ),
    DeviceCategory.DGNBJ: (
        NumberEntityDescription(
            key=DPCode.ALARM_TIME,
            translation_key="time",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.FS: (
        NumberEntityDescription(
            key=DPCode.TEMP,
            translation_key="temperature",
            device_class=NumberDeviceClass.TEMPERATURE,
        ),
    ),
    DeviceCategory.HPS: (
        NumberEntityDescription(
            key=DPCode.SENSITIVITY,
            translation_key="sensitivity",
            entity_category=EntityCategory.CONFIG,
        ),
        NumberEntityDescription(
            key=DPCode.NEAR_DETECTION,
            translation_key="near_detection",
            device_class=NumberDeviceClass.DISTANCE,
            entity_category=EntityCategory.CONFIG,
        ),
        NumberEntityDescription(
            key=DPCode.FAR_DETECTION,
            translation_key="far_detection",
            device_class=NumberDeviceClass.DISTANCE,
            entity_category=EntityCategory.CONFIG,
        ),
        NumberEntityDescription(
            key=DPCode.TARGET_DIS_CLOSEST,
            translation_key="target_dis_closest",
            device_class=NumberDeviceClass.DISTANCE,
        ),
    ),
    DeviceCategory.JSQ: (
        NumberEntityDescription(
            key=DPCode.TEMP_SET,
            translation_key="temperature",
            device_class=NumberDeviceClass.TEMPERATURE,
        ),
        NumberEntityDescription(
            key=DPCode.TEMP_SET_F,
            translation_key="temperature",
            device_class=NumberDeviceClass.TEMPERATURE,
        ),
    ),
    DeviceCategory.KFJ: (
        NumberEntityDescription(
            key=DPCode.WATER_SET,
            translation_key="water_level",
            entity_category=EntityCategory.CONFIG,
        ),
        NumberEntityDescription(
            key=DPCode.TEMP_SET,
            translation_key="temperature",
            device_class=NumberDeviceClass.TEMPERATURE,
            entity_category=EntityCategory.CONFIG,
        ),
        NumberEntityDescription(
            key=DPCode.WARM_TIME,
            translation_key="heat_preservation_time",
            entity_category=EntityCategory.CONFIG,
        ),
        NumberEntityDescription(
            key=DPCode.POWDER_SET,
            translation_key="powder",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.MAL: (
        NumberEntityDescription(
            key=DPCode.DELAY_SET,
            # This setting is called "Arm Delay" in the official Tuya app
            translation_key="arm_delay",
            device_class=NumberDeviceClass.DURATION,
            entity_category=EntityCategory.CONFIG,
        ),
        NumberEntityDescription(
            key=DPCode.ALARM_DELAY_TIME,
            translation_key="alarm_delay",
            device_class=NumberDeviceClass.DURATION,
            entity_category=EntityCategory.CONFIG,
        ),
        NumberEntityDescription(
            key=DPCode.ALARM_TIME,
            # This setting is called "Siren Duration" in the official Tuya app
            translation_key="siren_duration",
            device_class=NumberDeviceClass.DURATION,
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.MZJ: (
        NumberEntityDescription(
            key=DPCode.COOK_TEMPERATURE,
            translation_key="cook_temperature",
            entity_category=EntityCategory.CONFIG,
        ),
        NumberEntityDescription(
            key=DPCode.COOK_TIME,
            translation_key="cook_time",
            native_unit_of_measurement=UnitOfTime.MINUTES,
            entity_category=EntityCategory.CONFIG,
        ),
        NumberEntityDescription(
            key=DPCode.CLOUD_RECIPE_NUMBER,
            translation_key="cloud_recipe",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.SWTZ: (
        NumberEntityDescription(
            key=DPCode.COOK_TEMPERATURE,
            translation_key="cook_temperature",
            entity_category=EntityCategory.CONFIG,
        ),
        NumberEntityDescription(
            key=DPCode.COOK_TEMPERATURE_2,
            translation_key="indexed_cook_temperature",
            translation_placeholders={"index": "2"},
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.SD: (
        NumberEntityDescription(
            key=DPCode.VOLUME_SET,
            translation_key="volume",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.SFKZQ: (
        # Controls the irrigation duration for the water valve
        NumberEntityDescription(
            key=DPCode.COUNTDOWN_1,
            translation_key="indexed_irrigation_duration",
            translation_placeholders={"index": "1"},
            device_class=NumberDeviceClass.DURATION,
            entity_category=EntityCategory.CONFIG,
        ),
        NumberEntityDescription(
            key=DPCode.COUNTDOWN_2,
            translation_key="indexed_irrigation_duration",
            translation_placeholders={"index": "2"},
            device_class=NumberDeviceClass.DURATION,
            entity_category=EntityCategory.CONFIG,
        ),
        NumberEntityDescription(
            key=DPCode.COUNTDOWN_3,
            translation_key="indexed_irrigation_duration",
            translation_placeholders={"index": "3"},
            device_class=NumberDeviceClass.DURATION,
            entity_category=EntityCategory.CONFIG,
        ),
        NumberEntityDescription(
            key=DPCode.COUNTDOWN_4,
            translation_key="indexed_irrigation_duration",
            translation_placeholders={"index": "4"},
            device_class=NumberDeviceClass.DURATION,
            entity_category=EntityCategory.CONFIG,
        ),
        NumberEntityDescription(
            key=DPCode.COUNTDOWN_5,
            translation_key="indexed_irrigation_duration",
            translation_placeholders={"index": "5"},
            device_class=NumberDeviceClass.DURATION,
            entity_category=EntityCategory.CONFIG,
        ),
        NumberEntityDescription(
            key=DPCode.COUNTDOWN_6,
            translation_key="indexed_irrigation_duration",
            translation_placeholders={"index": "6"},
            device_class=NumberDeviceClass.DURATION,
            entity_category=EntityCategory.CONFIG,
        ),
        NumberEntityDescription(
            key=DPCode.COUNTDOWN_7,
            translation_key="indexed_irrigation_duration",
            translation_placeholders={"index": "7"},
            device_class=NumberDeviceClass.DURATION,
            entity_category=EntityCategory.CONFIG,
        ),
        NumberEntityDescription(
            key=DPCode.COUNTDOWN_8,
            translation_key="indexed_irrigation_duration",
            translation_placeholders={"index": "8"},
            device_class=NumberDeviceClass.DURATION,
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.SGBJ: (
        NumberEntityDescription(
            key=DPCode.ALARM_TIME,
            translation_key="time",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.SP: (
        NumberEntityDescription(
            key=DPCode.BASIC_DEVICE_VOLUME,
            translation_key="volume",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.SZJQR: (
        NumberEntityDescription(
            key=DPCode.ARM_DOWN_PERCENT,
            translation_key="move_down",
            native_unit_of_measurement=PERCENTAGE,
            entity_category=EntityCategory.CONFIG,
        ),
        NumberEntityDescription(
            key=DPCode.ARM_UP_PERCENT,
            translation_key="move_up",
            native_unit_of_measurement=PERCENTAGE,
            entity_category=EntityCategory.CONFIG,
        ),
        NumberEntityDescription(
            key=DPCode.CLICK_SUSTAIN_TIME,
            translation_key="down_delay",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.TGKG: (
        NumberEntityDescription(
            key=DPCode.BRIGHTNESS_MIN_1,
            translation_key="indexed_minimum_brightness",
            translation_placeholders={"index": "1"},
            entity_category=EntityCategory.CONFIG,
        ),
        NumberEntityDescription(
            key=DPCode.BRIGHTNESS_MAX_1,
            translation_key="indexed_maximum_brightness",
            translation_placeholders={"index": "1"},
            entity_category=EntityCategory.CONFIG,
        ),
        NumberEntityDescription(
            key=DPCode.BRIGHTNESS_MIN_2,
            translation_key="indexed_minimum_brightness",
            translation_placeholders={"index": "2"},
            entity_category=EntityCategory.CONFIG,
        ),
        NumberEntityDescription(
            key=DPCode.BRIGHTNESS_MAX_2,
            translation_key="indexed_maximum_brightness",
            translation_placeholders={"index": "2"},
            entity_category=EntityCategory.CONFIG,
        ),
        NumberEntityDescription(
            key=DPCode.BRIGHTNESS_MIN_3,
            translation_key="indexed_minimum_brightness",
            translation_placeholders={"index": "3"},
            entity_category=EntityCategory.CONFIG,
        ),
        NumberEntityDescription(
            key=DPCode.BRIGHTNESS_MAX_3,
            translation_key="indexed_maximum_brightness",
            translation_placeholders={"index": "3"},
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.TGQ: (
        NumberEntityDescription(
            key=DPCode.BRIGHTNESS_MIN_1,
            translation_key="indexed_minimum_brightness",
            translation_placeholders={"index": "1"},
            entity_category=EntityCategory.CONFIG,
        ),
        NumberEntityDescription(
            key=DPCode.BRIGHTNESS_MAX_1,
            translation_key="indexed_maximum_brightness",
            translation_placeholders={"index": "1"},
            entity_category=EntityCategory.CONFIG,
        ),
        NumberEntityDescription(
            key=DPCode.BRIGHTNESS_MIN_2,
            translation_key="indexed_minimum_brightness",
            translation_placeholders={"index": "2"},
            entity_category=EntityCategory.CONFIG,
        ),
        NumberEntityDescription(
            key=DPCode.BRIGHTNESS_MAX_2,
            translation_key="indexed_maximum_brightness",
            translation_placeholders={"index": "2"},
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.WK: (
        NumberEntityDescription(
            key=DPCode.TEMP_CORRECTION,
            translation_key="temp_correction",
            entity_category=EntityCategory.CONFIG,
        ),
        NumberEntityDescription(
            key=DPCode.LOWER_TEMP,
            translation_key="lower_temperature",
            device_class=NumberDeviceClass.TEMPERATURE,
            entity_category=EntityCategory.CONFIG,
        ),
        NumberEntityDescription(
            key=DPCode.UPPER_TEMP,
            translation_key="upper_temperature",
            device_class=NumberDeviceClass.TEMPERATURE,
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.XNYJCN: (
        NumberEntityDescription(
            key=DPCode.BACKUP_RESERVE,
            translation_key="battery_backup_reserve",
            entity_category=EntityCategory.CONFIG,
        ),
        NumberEntityDescription(
            key=DPCode.OUTPUT_POWER_LIMIT,
            translation_key="inverter_output_power_limit",
            device_class=NumberDeviceClass.POWER,
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.YWCGQ: (
        NumberEntityDescription(
            key=DPCode.MAX_SET,
            translation_key="alarm_maximum",
            entity_category=EntityCategory.CONFIG,
        ),
        NumberEntityDescription(
            key=DPCode.MINI_SET,
            translation_key="alarm_minimum",
            entity_category=EntityCategory.CONFIG,
        ),
        NumberEntityDescription(
            key=DPCode.INSTALLATION_HEIGHT,
            translation_key="installation_height",
            device_class=NumberDeviceClass.DISTANCE,
            entity_category=EntityCategory.CONFIG,
        ),
        NumberEntityDescription(
            key=DPCode.LIQUID_DEPTH_MAX,
            translation_key="maximum_liquid_depth",
            device_class=NumberDeviceClass.DISTANCE,
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.ZD: (
        NumberEntityDescription(
            key=DPCode.SENSITIVITY,
            translation_key="sensitivity",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.ZNRB: (
        NumberEntityDescription(
            key=DPCode.TEMP_SET,
            translation_key="temperature",
            device_class=NumberDeviceClass.TEMPERATURE,
        ),
    ),
}

# Smart Camera - Low power consumption camera (duplicate of `sp`)
NUMBERS[DeviceCategory.DGHSXJ] = NUMBERS[DeviceCategory.SP]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TuyaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Tuya number dynamically through Tuya discovery."""
    manager = entry.runtime_data.manager

    @callback
    def async_discover_device(device_ids: list[str]) -> None:
        """Discover and add a discovered Tuya number."""
        entities: list[TuyaNumberEntity] = []
        for device_id in device_ids:
            device = manager.device_map[device_id]
            if descriptions := NUMBERS.get(device.category):
                entities.extend(
                    TuyaNumberEntity(device, manager, description)
                    for description in descriptions
                    if description.key in device.status
                )

        async_add_entities(entities)

    async_discover_device([*manager.device_map])

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
            if description.native_unit_of_measurement is None:
                self._attr_native_unit_of_measurement = int_type.unit

        # Logic to ensure the set device class and API received Unit Of Measurement
        # match Home Assistants requirements.
        if (
            self.device_class is not None
            and not self.device_class.startswith(DOMAIN)
            and description.native_unit_of_measurement is None
            # we do not need to check mappings if the API UOM is allowed
            and self.native_unit_of_measurement
            not in NUMBER_DEVICE_CLASS_UNITS[self.device_class]
        ):
            # We cannot have a device class, if the UOM isn't set or the
            # device class cannot be found in the validation mapping.
            if (
                self.native_unit_of_measurement is None
                or self.device_class not in DEVICE_CLASS_UNITS
            ):
                LOGGER.debug(
                    "Device class %s ignored for incompatible unit %s in number entity %s",
                    self.device_class,
                    self.native_unit_of_measurement,
                    self.unique_id,
                )
                self._attr_device_class = None
                return

            uoms = DEVICE_CLASS_UNITS[self.device_class]
            uom = uoms.get(self.native_unit_of_measurement) or uoms.get(
                self.native_unit_of_measurement.lower()
            )

            # Unknown unit of measurement, device class should not be used.
            if uom is None:
                self._attr_device_class = None
                return

            # Found unit of measurement, use the standardized Unit
            # Use the target conversion unit (if set)
            self._attr_native_unit_of_measurement = uom.unit

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
            raise ActionDPCodeNotFoundError(self.device, self.entity_description.key)

        self._send_command(
            [
                {
                    "code": self.entity_description.key,
                    "value": self._number.scale_value_back(value),
                }
            ]
        )
