"""Support for Tuya select."""

from dataclasses import dataclass
from typing import override

from tuya_device_handlers.definition.select import (
    SelectDefinition,
    get_default_definition,
)
from tuya_sharing import CustomerDevice, Manager

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import TUYA_DISCOVERY_NEW, DeviceCategory, DPCode
from .coordinator import TuyaConfigEntry
from .entity import TuyaEntity, TuyaEntityDescription


# All descriptions can be found here. Mostly the Enum data types in the
# default instructions set of each category end up being a select.
@dataclass(frozen=True)
class TuyaSelectEntityDescription(TuyaEntityDescription, SelectEntityDescription):
    """Describes a Tuya select entity."""


SELECTS: dict[DeviceCategory, tuple[TuyaSelectEntityDescription, ...]] = {
    DeviceCategory.BH: (
        TuyaSelectEntityDescription(
            key=DPCode.TEMP_SETTING_QUICK_C,
            entity_category=EntityCategory.CONFIG,
            translation_key="quick_heat_temperature",
        ),
        TuyaSelectEntityDescription(
            key=DPCode.WORK_TYPE,
            entity_category=EntityCategory.CONFIG,
            translation_key="kettle_work_mode",
        ),
    ),
    DeviceCategory.CL: (
        TuyaSelectEntityDescription(
            key=DPCode.CONTROL_BACK_MODE,
            entity_category=EntityCategory.CONFIG,
            translation_key="curtain_motor_mode",
        ),
        TuyaSelectEntityDescription(
            key=DPCode.MODE,
            entity_category=EntityCategory.CONFIG,
            translation_key="curtain_mode",
        ),
    ),
    DeviceCategory.CO2BJ: (
        TuyaSelectEntityDescription(
            key=DPCode.ALARM_VOLUME,
            translation_key="volume",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.CS: (
        TuyaSelectEntityDescription(
            key=DPCode.COUNTDOWN_SET,
            entity_category=EntityCategory.CONFIG,
            translation_key="countdown",
        ),
        TuyaSelectEntityDescription(
            key=DPCode.DEHUMIDITY_SET_ENUM,
            translation_key="target_humidity",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.CWJWQ: (
        TuyaSelectEntityDescription(
            key=DPCode.WORK_MODE,
            entity_category=EntityCategory.CONFIG,
            translation_key="odor_elimination_mode",
        ),
    ),
    DeviceCategory.DGNBJ: (
        TuyaSelectEntityDescription(
            key=DPCode.ALARM_VOLUME,
            translation_key="volume",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.DR: (
        TuyaSelectEntityDescription(
            key=DPCode.LEVEL,
            icon="mdi:thermometer-lines",
            translation_key="blanket_level",
        ),
        TuyaSelectEntityDescription(
            key=DPCode.LEVEL_1,
            icon="mdi:thermometer-lines",
            translation_key="indexed_blanket_level",
            translation_placeholders={"index": "1"},
        ),
        TuyaSelectEntityDescription(
            key=DPCode.LEVEL_2,
            icon="mdi:thermometer-lines",
            translation_key="indexed_blanket_level",
            translation_placeholders={"index": "2"},
        ),
    ),
    DeviceCategory.FS: (
        TuyaSelectEntityDescription(
            key=DPCode.FAN_VERTICAL,
            entity_category=EntityCategory.CONFIG,
            translation_key="vertical_fan_angle",
        ),
        TuyaSelectEntityDescription(
            key=DPCode.FAN_HORIZONTAL,
            entity_category=EntityCategory.CONFIG,
            translation_key="horizontal_fan_angle",
        ),
        TuyaSelectEntityDescription(
            key=DPCode.COUNTDOWN,
            entity_category=EntityCategory.CONFIG,
            translation_key="countdown",
        ),
        TuyaSelectEntityDescription(
            key=DPCode.COUNTDOWN_SET,
            entity_category=EntityCategory.CONFIG,
            translation_key="countdown",
        ),
    ),
    DeviceCategory.JSQ: (
        TuyaSelectEntityDescription(
            key=DPCode.SPRAY_MODE,
            entity_category=EntityCategory.CONFIG,
            translation_key="humidifier_spray_mode",
        ),
        TuyaSelectEntityDescription(
            key=DPCode.LEVEL,
            entity_category=EntityCategory.CONFIG,
            translation_key="humidifier_level",
        ),
        TuyaSelectEntityDescription(
            key=DPCode.MOODLIGHTING,
            entity_category=EntityCategory.CONFIG,
            translation_key="humidifier_moodlighting",
        ),
        TuyaSelectEntityDescription(
            key=DPCode.COUNTDOWN,
            entity_category=EntityCategory.CONFIG,
            translation_key="countdown",
        ),
        TuyaSelectEntityDescription(
            key=DPCode.COUNTDOWN_SET,
            entity_category=EntityCategory.CONFIG,
            translation_key="countdown",
        ),
    ),
    DeviceCategory.KFJ: (
        TuyaSelectEntityDescription(
            key=DPCode.CUP_NUMBER,
            translation_key="cups",
        ),
        TuyaSelectEntityDescription(
            key=DPCode.CONCENTRATION_SET,
            translation_key="concentration",
            entity_category=EntityCategory.CONFIG,
        ),
        TuyaSelectEntityDescription(
            key=DPCode.MATERIAL,
            translation_key="material",
            entity_category=EntityCategory.CONFIG,
        ),
        TuyaSelectEntityDescription(
            key=DPCode.MODE,
            translation_key="mode",
        ),
    ),
    DeviceCategory.KG: (
        TuyaSelectEntityDescription(
            key=DPCode.RELAY_STATUS,
            entity_category=EntityCategory.CONFIG,
            translation_key="relay_status",
        ),
        TuyaSelectEntityDescription(
            key=DPCode.LIGHT_MODE,
            entity_category=EntityCategory.CONFIG,
            translation_key="light_mode",
        ),
    ),
    DeviceCategory.KJ: (
        TuyaSelectEntityDescription(
            key=DPCode.COUNTDOWN,
            entity_category=EntityCategory.CONFIG,
            translation_key="countdown",
        ),
        TuyaSelectEntityDescription(
            key=DPCode.COUNTDOWN_SET,
            entity_category=EntityCategory.CONFIG,
            translation_key="countdown",
        ),
    ),
    DeviceCategory.QCCDZ: (
        TuyaSelectEntityDescription(
            key=DPCode.WORK_MODE,
            translation_key="charger_work_mode",
        ),
    ),
    DeviceCategory.QN: (
        TuyaSelectEntityDescription(
            key=DPCode.LEVEL,
            translation_key="temperature_level",
        ),
    ),
    DeviceCategory.SD: (
        TuyaSelectEntityDescription(
            key=DPCode.CISTERN,
            entity_category=EntityCategory.CONFIG,
            translation_key="vacuum_cistern",
        ),
        TuyaSelectEntityDescription(
            key=DPCode.COLLECTION_MODE,
            entity_category=EntityCategory.CONFIG,
            translation_key="vacuum_collection",
        ),
        TuyaSelectEntityDescription(
            key=DPCode.MODE,
            entity_category=EntityCategory.CONFIG,
            translation_key="vacuum_mode",
        ),
    ),
    DeviceCategory.SFKZQ: (
        # Irrigation will not be run within this set delay period
        TuyaSelectEntityDescription(
            key=DPCode.WEATHER_DELAY,
            translation_key="weather_delay",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.SGBJ: (
        TuyaSelectEntityDescription(
            key=DPCode.ALARM_STATE,
            translation_key="siren_mode",
            entity_category=EntityCategory.CONFIG,
        ),
        TuyaSelectEntityDescription(
            key=DPCode.ALARM_VOLUME,
            translation_key="volume",
            entity_category=EntityCategory.CONFIG,
        ),
        TuyaSelectEntityDescription(
            key=DPCode.BRIGHT_STATE,
            translation_key="brightness",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.SJZ: (
        TuyaSelectEntityDescription(
            key=DPCode.LEVEL,
            translation_key="desk_level",
            entity_category=EntityCategory.CONFIG,
        ),
        TuyaSelectEntityDescription(
            key=DPCode.UP_DOWN,
            translation_key="desk_up_down",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.SP: (
        TuyaSelectEntityDescription(
            key=DPCode.IPC_WORK_MODE,
            entity_category=EntityCategory.CONFIG,
            translation_key="ipc_work_mode",
        ),
        TuyaSelectEntityDescription(
            key=DPCode.DECIBEL_SENSITIVITY,
            entity_category=EntityCategory.CONFIG,
            translation_key="decibel_sensitivity",
        ),
        TuyaSelectEntityDescription(
            key=DPCode.RECORD_MODE,
            entity_category=EntityCategory.CONFIG,
            translation_key="record_mode",
        ),
        TuyaSelectEntityDescription(
            key=DPCode.BASIC_NIGHTVISION,
            entity_category=EntityCategory.CONFIG,
            translation_key="basic_nightvision",
        ),
        TuyaSelectEntityDescription(
            key=DPCode.BASIC_ANTI_FLICKER,
            entity_category=EntityCategory.CONFIG,
            translation_key="basic_anti_flicker",
        ),
        TuyaSelectEntityDescription(
            key=DPCode.MOTION_SENSITIVITY,
            entity_category=EntityCategory.CONFIG,
            translation_key="motion_sensitivity",
        ),
    ),
    DeviceCategory.SZJQR: (
        TuyaSelectEntityDescription(
            key=DPCode.MODE,
            entity_category=EntityCategory.CONFIG,
            translation_key="fingerbot_mode",
        ),
    ),
    DeviceCategory.TDQ: (
        TuyaSelectEntityDescription(
            key=DPCode.RELAY_STATUS,
            entity_category=EntityCategory.CONFIG,
            translation_key="relay_status",
        ),
        TuyaSelectEntityDescription(
            key=DPCode.LIGHT_MODE,
            entity_category=EntityCategory.CONFIG,
            translation_key="light_mode",
        ),
    ),
    DeviceCategory.TGKG: (
        TuyaSelectEntityDescription(
            key=DPCode.RELAY_STATUS,
            entity_category=EntityCategory.CONFIG,
            translation_key="relay_status",
        ),
        TuyaSelectEntityDescription(
            key=DPCode.LIGHT_MODE,
            entity_category=EntityCategory.CONFIG,
            translation_key="light_mode",
        ),
        TuyaSelectEntityDescription(
            key=DPCode.LED_TYPE_1,
            entity_category=EntityCategory.CONFIG,
            translation_key="indexed_led_type",
            translation_placeholders={"index": "1"},
        ),
        TuyaSelectEntityDescription(
            key=DPCode.LED_TYPE_2,
            entity_category=EntityCategory.CONFIG,
            translation_key="indexed_led_type",
            translation_placeholders={"index": "2"},
        ),
        TuyaSelectEntityDescription(
            key=DPCode.LED_TYPE_3,
            entity_category=EntityCategory.CONFIG,
            translation_key="indexed_led_type",
            translation_placeholders={"index": "3"},
        ),
    ),
    DeviceCategory.TGQ: (
        TuyaSelectEntityDescription(
            key=DPCode.LED_TYPE_1,
            entity_category=EntityCategory.CONFIG,
            translation_key="indexed_led_type",
            translation_placeholders={"index": "1"},
        ),
        TuyaSelectEntityDescription(
            key=DPCode.LED_TYPE_2,
            entity_category=EntityCategory.CONFIG,
            translation_key="indexed_led_type",
            translation_placeholders={"index": "2"},
        ),
    ),
    DeviceCategory.XNYJCN: (
        TuyaSelectEntityDescription(
            key=DPCode.WORK_MODE,
            translation_key="inverter_work_mode",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.ZNJDQ: (
        TuyaSelectEntityDescription(
            key=DPCode.RELAY_STATUS,
            translation_key="relay_status",
            entity_category=EntityCategory.CONFIG,
        ),
        TuyaSelectEntityDescription(
            key=DPCode.LIGHT_MODE,
            translation_key="light_mode",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
}

# Socket (duplicate of `kg`)
SELECTS[DeviceCategory.CZ] = SELECTS[DeviceCategory.KG]

# Smart Camera - Low power consumption camera (duplicate of `sp`)
SELECTS[DeviceCategory.DGHSXJ] = SELECTS[DeviceCategory.SP]

# Power Socket (duplicate of `kg`)
SELECTS[DeviceCategory.PC] = SELECTS[DeviceCategory.KG]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TuyaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Tuya select dynamically through Tuya discovery."""
    manager = entry.runtime_data.manager

    @callback
    def async_discover_device(device_ids: list[str]) -> None:
        """Discover and add a discovered Tuya select."""
        entities: list[TuyaSelectEntity] = []
        for device_id in device_ids:
            device = manager.device_map[device_id]
            if descriptions := SELECTS.get(device.category):
                entities.extend(
                    TuyaSelectEntity(device, manager, description, definition)
                    for description in descriptions
                    if (definition := get_default_definition(device, description.key))
                )

        async_add_entities(entities)

    async_discover_device([*manager.device_map])

    entry.async_on_unload(
        async_dispatcher_connect(hass, TUYA_DISCOVERY_NEW, async_discover_device)
    )


class TuyaSelectEntity(TuyaEntity, SelectEntity):
    """Tuya Select Entity."""

    def __init__(
        self,
        device: CustomerDevice,
        device_manager: Manager,
        description: TuyaSelectEntityDescription,
        definition: SelectDefinition,
    ) -> None:
        """Initialize a Tuya select entity."""
        super().__init__(device, device_manager, description)
        self._dpcode_wrapper = definition.select_wrapper
        self._attr_options = definition.select_wrapper.options

    @property
    @override
    def current_option(self) -> str | None:
        """Return the selected entity option to represent the entity state."""
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
    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        await self._async_send_wrapper_updates(self._dpcode_wrapper, option)
