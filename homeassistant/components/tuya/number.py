"""Support for Tuya number."""

from dataclasses import dataclass
from typing import override

from tuya_device_handlers.definition.number import (
    NumberDefinition,
    get_default_definition,
)
from tuya_sharing import CustomerDevice, Manager

from homeassistant.components.number import (
    DEVICE_CLASS_UNITS as NUMBER_DEVICE_CLASS_UNITS,
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
)
from homeassistant.const import EntityCategory, UnitOfRatio, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import ChildDeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    DEVICE_CLASS_UNITS,
    DOMAIN,
    LOGGER,
    TUYA_DISCOVERY_NEW,
    DeviceCategory,
    DPCode,
)
from .coordinator import TuyaConfigEntry
from .entity import TuyaEntity, TuyaEntityDescription, get_child_device_info
from .util import get_device_temp_unit_convert


@dataclass(frozen=True)
class TuyaNumberEntityDescription(TuyaEntityDescription, NumberEntityDescription):
    """Describes a Tuya number entity."""


NUMBERS: dict[DeviceCategory, tuple[TuyaNumberEntityDescription, ...]] = {
    DeviceCategory.BH: (
        TuyaNumberEntityDescription(
            key=DPCode.TEMP_SET,
            translation_key="temperature",
            device_class=NumberDeviceClass.TEMPERATURE,
            entity_category=EntityCategory.CONFIG,
        ),
        TuyaNumberEntityDescription(
            key=DPCode.TEMP_SET_F,
            translation_key="temperature",
            device_class=NumberDeviceClass.TEMPERATURE,
            entity_category=EntityCategory.CONFIG,
        ),
        TuyaNumberEntityDescription(
            key=DPCode.TEMP_BOILING_C,
            translation_key="temperature_after_boiling",
            device_class=NumberDeviceClass.TEMPERATURE,
            entity_category=EntityCategory.CONFIG,
        ),
        TuyaNumberEntityDescription(
            key=DPCode.TEMP_BOILING_F,
            translation_key="temperature_after_boiling",
            device_class=NumberDeviceClass.TEMPERATURE,
            entity_category=EntityCategory.CONFIG,
        ),
        TuyaNumberEntityDescription(
            key=DPCode.WARM_TIME,
            translation_key="heat_preservation_time",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.BZYD: (
        TuyaNumberEntityDescription(
            key=DPCode.VOLUME_SET,
            translation_key="volume",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.CO2BJ: (
        TuyaNumberEntityDescription(
            key=DPCode.ALARM_TIME,
            translation_key="alarm_duration",
            native_unit_of_measurement=UnitOfTime.SECONDS,
            device_class=NumberDeviceClass.DURATION,
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.CWWSQ: (
        TuyaNumberEntityDescription(
            key=DPCode.MANUAL_FEED,
            translation_key="feed",
        ),
        TuyaNumberEntityDescription(
            key=DPCode.VOICE_TIMES,
            translation_key="voice_times",
        ),
    ),
    DeviceCategory.CZ: (
        # Two-channel current transformer meters warn above these thresholds
        TuyaNumberEntityDescription(
            key=DPCode.WARN_POWER1,
            translation_key="indexed_power_warning_threshold",
            translation_placeholders={"index": "1"},
            device_class=NumberDeviceClass.POWER,
            entity_category=EntityCategory.CONFIG,
        ),
        TuyaNumberEntityDescription(
            key=DPCode.WARN_POWER2,
            translation_key="indexed_power_warning_threshold",
            translation_placeholders={"index": "2"},
            device_class=NumberDeviceClass.POWER,
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.DGNBJ: (
        TuyaNumberEntityDescription(
            key=DPCode.ALARM_TIME,
            translation_key="time",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.FS: (
        TuyaNumberEntityDescription(
            key=DPCode.TEMP,
            translation_key="temperature",
            device_class=NumberDeviceClass.TEMPERATURE,
        ),
    ),
    DeviceCategory.HPS: (
        TuyaNumberEntityDescription(
            key=DPCode.SENSITIVITY,
            translation_key="sensitivity",
            entity_category=EntityCategory.CONFIG,
        ),
        TuyaNumberEntityDescription(
            key=DPCode.NEAR_DETECTION,
            translation_key="near_detection",
            device_class=NumberDeviceClass.DISTANCE,
            entity_category=EntityCategory.CONFIG,
        ),
        TuyaNumberEntityDescription(
            key=DPCode.FAR_DETECTION,
            translation_key="far_detection",
            device_class=NumberDeviceClass.DISTANCE,
            entity_category=EntityCategory.CONFIG,
        ),
        TuyaNumberEntityDescription(
            key=DPCode.TARGET_DIS_CLOSEST,
            translation_key="target_dis_closest",
            device_class=NumberDeviceClass.DISTANCE,
        ),
    ),
    DeviceCategory.JSQ: (
        TuyaNumberEntityDescription(
            key=DPCode.TEMP_SET,
            translation_key="temperature",
            device_class=NumberDeviceClass.TEMPERATURE,
        ),
        TuyaNumberEntityDescription(
            key=DPCode.TEMP_SET_F,
            translation_key="temperature",
            device_class=NumberDeviceClass.TEMPERATURE,
        ),
    ),
    DeviceCategory.KFJ: (
        TuyaNumberEntityDescription(
            key=DPCode.WATER_SET,
            translation_key="water_level",
            entity_category=EntityCategory.CONFIG,
        ),
        TuyaNumberEntityDescription(
            key=DPCode.TEMP_SET,
            translation_key="temperature",
            device_class=NumberDeviceClass.TEMPERATURE,
            entity_category=EntityCategory.CONFIG,
        ),
        TuyaNumberEntityDescription(
            key=DPCode.WARM_TIME,
            translation_key="heat_preservation_time",
            entity_category=EntityCategory.CONFIG,
        ),
        TuyaNumberEntityDescription(
            key=DPCode.POWDER_SET,
            translation_key="powder",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.MAL: (
        TuyaNumberEntityDescription(
            key=DPCode.DELAY_SET,
            # This setting is called "Arm Delay" in the official Tuya app
            translation_key="arm_delay",
            device_class=NumberDeviceClass.DURATION,
            entity_category=EntityCategory.CONFIG,
        ),
        TuyaNumberEntityDescription(
            key=DPCode.ALARM_DELAY_TIME,
            translation_key="alarm_delay",
            device_class=NumberDeviceClass.DURATION,
            entity_category=EntityCategory.CONFIG,
        ),
        TuyaNumberEntityDescription(
            key=DPCode.ALARM_TIME,
            # This setting is called "Siren Duration" in the official Tuya app
            translation_key="siren_duration",
            device_class=NumberDeviceClass.DURATION,
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.MSP: (
        TuyaNumberEntityDescription(
            key=DPCode.DELAY_CLEAN_TIME,
            translation_key="delay_clean_time",
            device_class=NumberDeviceClass.DURATION,
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.MZJ: (
        TuyaNumberEntityDescription(
            key=DPCode.COOK_TEMPERATURE,
            translation_key="cook_temperature",
            entity_category=EntityCategory.CONFIG,
        ),
        TuyaNumberEntityDescription(
            key=DPCode.COOK_TIME,
            translation_key="cook_time",
            native_unit_of_measurement=UnitOfTime.MINUTES,
            entity_category=EntityCategory.CONFIG,
        ),
        TuyaNumberEntityDescription(
            key=DPCode.CLOUD_RECIPE_NUMBER,
            translation_key="cloud_recipe",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.QCCDZ: (
        TuyaNumberEntityDescription(
            key=DPCode.CHARGE_CUR_SET,
            translation_key="charging_current",
            device_class=NumberDeviceClass.CURRENT,
        ),
    ),
    DeviceCategory.SWTZ: (
        TuyaNumberEntityDescription(
            key=DPCode.COOK_TEMPERATURE,
            translation_key="cook_temperature",
            entity_category=EntityCategory.CONFIG,
        ),
        TuyaNumberEntityDescription(
            key=DPCode.COOK_TEMPERATURE_2,
            translation_key="indexed_cook_temperature",
            translation_placeholders={"index": "2"},
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.SD: (
        TuyaNumberEntityDescription(
            key=DPCode.VOLUME_SET,
            translation_key="volume",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.SFKZQ: (
        # Controls the irrigation duration for indexed water valves
        TuyaNumberEntityDescription(
            key=DPCode.COUNTDOWN,
            translation_key="irrigation_duration",
            device_class=NumberDeviceClass.DURATION,
            entity_category=EntityCategory.CONFIG,
        ),
        # Controls the irrigation duration for indexed water valves
        *(
            TuyaNumberEntityDescription(
                key=DPCode(f"countdown_{channel}"),
                translation_key="irrigation_duration",
                device_class=NumberDeviceClass.DURATION,
                entity_category=EntityCategory.CONFIG,
                channel_index=channel,
                channel_condition=lambda device: (
                    DPCode.COUNTDOWN_2 in device.status_range
                ),
            )
            for channel in range(1, 9)
        ),
    ),
    DeviceCategory.SGBJ: (
        TuyaNumberEntityDescription(
            key=DPCode.ALARM_TIME,
            translation_key="time",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.SP: (
        TuyaNumberEntityDescription(
            key=DPCode.BASIC_DEVICE_VOLUME,
            translation_key="volume",
            entity_category=EntityCategory.CONFIG,
        ),
        TuyaNumberEntityDescription(
            key=DPCode.IPC_BRIGHT,
            translation_key="video_brightness",
            entity_category=EntityCategory.CONFIG,
        ),
        TuyaNumberEntityDescription(
            key=DPCode.IPC_CONTRAST,
            translation_key="video_contrast",
            entity_category=EntityCategory.CONFIG,
        ),
        TuyaNumberEntityDescription(
            key=DPCode.IPC_SHARP,
            translation_key="video_sharpness",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.SZJQR: (
        TuyaNumberEntityDescription(
            key=DPCode.ARM_DOWN_PERCENT,
            translation_key="move_down",
            native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
            entity_category=EntityCategory.CONFIG,
        ),
        TuyaNumberEntityDescription(
            key=DPCode.ARM_UP_PERCENT,
            translation_key="move_up",
            native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
            entity_category=EntityCategory.CONFIG,
        ),
        TuyaNumberEntityDescription(
            key=DPCode.CLICK_SUSTAIN_TIME,
            translation_key="down_delay",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.TGKG: (
        TuyaNumberEntityDescription(
            key=DPCode.BRIGHTNESS_MIN_1,
            translation_key="indexed_minimum_brightness",
            translation_placeholders={"index": "1"},
            entity_category=EntityCategory.CONFIG,
        ),
        TuyaNumberEntityDescription(
            key=DPCode.BRIGHTNESS_MAX_1,
            translation_key="indexed_maximum_brightness",
            translation_placeholders={"index": "1"},
            entity_category=EntityCategory.CONFIG,
        ),
        TuyaNumberEntityDescription(
            key=DPCode.BRIGHTNESS_MIN_2,
            translation_key="indexed_minimum_brightness",
            translation_placeholders={"index": "2"},
            entity_category=EntityCategory.CONFIG,
        ),
        TuyaNumberEntityDescription(
            key=DPCode.BRIGHTNESS_MAX_2,
            translation_key="indexed_maximum_brightness",
            translation_placeholders={"index": "2"},
            entity_category=EntityCategory.CONFIG,
        ),
        TuyaNumberEntityDescription(
            key=DPCode.BRIGHTNESS_MIN_3,
            translation_key="indexed_minimum_brightness",
            translation_placeholders={"index": "3"},
            entity_category=EntityCategory.CONFIG,
        ),
        TuyaNumberEntityDescription(
            key=DPCode.BRIGHTNESS_MAX_3,
            translation_key="indexed_maximum_brightness",
            translation_placeholders={"index": "3"},
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.TGQ: (
        TuyaNumberEntityDescription(
            key=DPCode.BRIGHTNESS_MIN_1,
            translation_key="indexed_minimum_brightness",
            translation_placeholders={"index": "1"},
            entity_category=EntityCategory.CONFIG,
        ),
        TuyaNumberEntityDescription(
            key=DPCode.BRIGHTNESS_MAX_1,
            translation_key="indexed_maximum_brightness",
            translation_placeholders={"index": "1"},
            entity_category=EntityCategory.CONFIG,
        ),
        TuyaNumberEntityDescription(
            key=DPCode.BRIGHTNESS_MIN_2,
            translation_key="indexed_minimum_brightness",
            translation_placeholders={"index": "2"},
            entity_category=EntityCategory.CONFIG,
        ),
        TuyaNumberEntityDescription(
            key=DPCode.BRIGHTNESS_MAX_2,
            translation_key="indexed_maximum_brightness",
            translation_placeholders={"index": "2"},
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.WG2: (
        TuyaNumberEntityDescription(
            key=DPCode.DELAY_SET,
            # This setting is called "Arm Delay" in the official Tuya app
            translation_key="arm_delay",
            device_class=NumberDeviceClass.DURATION,
            entity_category=EntityCategory.CONFIG,
        ),
        TuyaNumberEntityDescription(
            key=DPCode.ALARM_DELAY_TIME,
            translation_key="alarm_delay",
            device_class=NumberDeviceClass.DURATION,
            entity_category=EntityCategory.CONFIG,
        ),
        TuyaNumberEntityDescription(
            key=DPCode.ALARM_TIME,
            # This setting is called "Siren Duration" in the official Tuya app
            translation_key="siren_duration",
            device_class=NumberDeviceClass.DURATION,
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.WK: (
        TuyaNumberEntityDescription(
            key=DPCode.TEMP_CORRECTION,
            translation_key="temp_correction",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.XNYJCN: (
        TuyaNumberEntityDescription(
            key=DPCode.BACKUP_RESERVE,
            translation_key="battery_backup_reserve",
            entity_category=EntityCategory.CONFIG,
        ),
        TuyaNumberEntityDescription(
            key=DPCode.OUTPUT_POWER_LIMIT,
            translation_key="inverter_output_power_limit",
            device_class=NumberDeviceClass.POWER,
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.YWCGQ: (
        TuyaNumberEntityDescription(
            key=DPCode.MAX_SET,
            translation_key="alarm_maximum",
            entity_category=EntityCategory.CONFIG,
        ),
        TuyaNumberEntityDescription(
            key=DPCode.MINI_SET,
            translation_key="alarm_minimum",
            entity_category=EntityCategory.CONFIG,
        ),
        TuyaNumberEntityDescription(
            key=DPCode.INSTALLATION_HEIGHT,
            translation_key="installation_height",
            device_class=NumberDeviceClass.DISTANCE,
            entity_category=EntityCategory.CONFIG,
        ),
        TuyaNumberEntityDescription(
            key=DPCode.LIQUID_DEPTH_MAX,
            translation_key="maximum_liquid_depth",
            device_class=NumberDeviceClass.DISTANCE,
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.ZD: (
        TuyaNumberEntityDescription(
            key=DPCode.SENSITIVITY,
            translation_key="sensitivity",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.ZNRB: (
        TuyaNumberEntityDescription(
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
                parent_device_id = dr.async_get_device_id_by_identifier(
                    hass, (DOMAIN, device.id), config_entry_id=entry.entry_id
                )
                entities.extend(
                    TuyaNumberEntity(
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
                )

        async_add_entities(entities)

    async_discover_device([*manager.device_map])

    entry.async_on_unload(
        async_dispatcher_connect(hass, TUYA_DISCOVERY_NEW, async_discover_device)
    )


class TuyaNumberEntity(TuyaEntity, NumberEntity):
    """Tuya Number Entity."""

    def __init__(
        self,
        device: CustomerDevice,
        device_manager: Manager,
        description: TuyaNumberEntityDescription,
        definition: NumberDefinition,
        *,
        device_info: ChildDeviceInfo | None = None,
    ) -> None:
        """Initialize a Tuya number entity."""
        super().__init__(device, device_manager, description, device_info=device_info)
        self._dpcode_wrapper = definition.number_wrapper

        self._attr_native_max_value = definition.number_wrapper.max_value
        self._attr_native_min_value = definition.number_wrapper.min_value
        self._attr_native_step = definition.number_wrapper.value_step

        self._validate_device_class_unit(definition.number_wrapper.native_unit)

    def _validate_device_class_unit(self, tuya_uom: str | None) -> None:
        """Validate device class unit compatibility."""

        # Logic to ensure the set device class and API received Unit Of Measurement
        # match Home Assistants requirements.
        if (
            (device_class := self.device_class) is None
            # we do not need to check mappings if the API UOM is allowed
            or tuya_uom in NUMBER_DEVICE_CLASS_UNITS[device_class]
        ):
            self._attr_native_unit_of_measurement = tuya_uom
            return

        # If the device provides TEMP_UNIT_CONVERT and no unit is set, use it.
        if (
            device_class is NumberDeviceClass.TEMPERATURE
            and not tuya_uom
            and (temp_unit := get_device_temp_unit_convert(self.device)) is not None
        ):
            self._attr_native_unit_of_measurement = temp_unit
            return

        # Check mappings for compatible units of measurement for the device class
        if (
            tuya_uom is not None
            and (uoms := DEVICE_CLASS_UNITS.get(device_class))
            and (uom := uoms.get(tuya_uom) or uoms.get(tuya_uom.lower()))
        ):
            self._attr_native_unit_of_measurement = uom.unit
            return

        if self.entity_description.native_unit_of_measurement is not None:
            LOGGER.debug(
                "Incompatible unit %s replaced by entity description unit %s "
                "for device class %s in number entity %s; use a quirk "
                "(https://github.com/home-assistant-libs/tuya-device-handlers)"
                " to override",
                tuya_uom,
                self.entity_description.native_unit_of_measurement,
                device_class,
                self.unique_id,
            )

            return

        self._attr_native_unit_of_measurement = tuya_uom
        self._attr_device_class = None
        LOGGER.debug(
            "Device class %s ignored for incompatible unit %s in number entity %s",
            device_class,
            tuya_uom,
            self.unique_id,
        )

    @property
    @override
    def native_value(self) -> float | None:
        """Return the entity value to represent the entity state."""
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
    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        await self._async_send_wrapper_updates(self._dpcode_wrapper, value)
