"""Support for Tuya select."""

from __future__ import annotations

from tuya_sharing import CustomerDevice, Manager

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import TuyaConfigEntry
from .const import TUYA_DISCOVERY_NEW, DeviceCategory, DPCode, DPType
from .entity import TuyaEntity
from .xternal_tuya_quirks import TUYA_QUIRKS_REGISTRY
from .xternal_tuya_quirks.select import CommonSelectType, TuyaSelectDefinition

# All descriptions can be found here. Mostly the Enum data types in the
# default instructions set of each category end up being a select.
SELECTS: dict[DeviceCategory, tuple[SelectEntityDescription, ...]] = {
    DeviceCategory.CL: (
        SelectEntityDescription(
            key=DPCode.CONTROL_BACK_MODE,
            entity_category=EntityCategory.CONFIG,
            translation_key="curtain_motor_mode",
        ),
        SelectEntityDescription(
            key=DPCode.MODE,
            entity_category=EntityCategory.CONFIG,
            translation_key="curtain_mode",
        ),
    ),
    DeviceCategory.CO2BJ: (
        SelectEntityDescription(
            key=DPCode.ALARM_VOLUME,
            translation_key="volume",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.CS: (
        SelectEntityDescription(
            key=DPCode.COUNTDOWN_SET,
            entity_category=EntityCategory.CONFIG,
            translation_key="countdown",
        ),
        SelectEntityDescription(
            key=DPCode.DEHUMIDITY_SET_ENUM,
            translation_key="target_humidity",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.CWJWQ: (
        SelectEntityDescription(
            key=DPCode.WORK_MODE,
            entity_category=EntityCategory.CONFIG,
            translation_key="odor_elimination_mode",
        ),
    ),
    DeviceCategory.DGNBJ: (
        SelectEntityDescription(
            key=DPCode.ALARM_VOLUME,
            translation_key="volume",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.DR: (
        SelectEntityDescription(
            key=DPCode.LEVEL,
            icon="mdi:thermometer-lines",
            translation_key="blanket_level",
        ),
        SelectEntityDescription(
            key=DPCode.LEVEL_1,
            icon="mdi:thermometer-lines",
            translation_key="indexed_blanket_level",
            translation_placeholders={"index": "1"},
        ),
        SelectEntityDescription(
            key=DPCode.LEVEL_2,
            icon="mdi:thermometer-lines",
            translation_key="indexed_blanket_level",
            translation_placeholders={"index": "2"},
        ),
    ),
    DeviceCategory.FS: (
        SelectEntityDescription(
            key=DPCode.FAN_VERTICAL,
            entity_category=EntityCategory.CONFIG,
            translation_key="vertical_fan_angle",
        ),
        SelectEntityDescription(
            key=DPCode.FAN_HORIZONTAL,
            entity_category=EntityCategory.CONFIG,
            translation_key="horizontal_fan_angle",
        ),
        SelectEntityDescription(
            key=DPCode.COUNTDOWN,
            entity_category=EntityCategory.CONFIG,
            translation_key="countdown",
        ),
        SelectEntityDescription(
            key=DPCode.COUNTDOWN_SET,
            entity_category=EntityCategory.CONFIG,
            translation_key="countdown",
        ),
    ),
    DeviceCategory.JSQ: (
        SelectEntityDescription(
            key=DPCode.SPRAY_MODE,
            entity_category=EntityCategory.CONFIG,
            translation_key="humidifier_spray_mode",
        ),
        SelectEntityDescription(
            key=DPCode.LEVEL,
            entity_category=EntityCategory.CONFIG,
            translation_key="humidifier_level",
        ),
        SelectEntityDescription(
            key=DPCode.MOODLIGHTING,
            entity_category=EntityCategory.CONFIG,
            translation_key="humidifier_moodlighting",
        ),
        SelectEntityDescription(
            key=DPCode.COUNTDOWN,
            entity_category=EntityCategory.CONFIG,
            translation_key="countdown",
        ),
        SelectEntityDescription(
            key=DPCode.COUNTDOWN_SET,
            entity_category=EntityCategory.CONFIG,
            translation_key="countdown",
        ),
    ),
    DeviceCategory.KFJ: (
        SelectEntityDescription(
            key=DPCode.CUP_NUMBER,
            translation_key="cups",
        ),
        SelectEntityDescription(
            key=DPCode.CONCENTRATION_SET,
            translation_key="concentration",
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
        ),
    ),
    DeviceCategory.KG: (
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
    DeviceCategory.KJ: (
        SelectEntityDescription(
            key=DPCode.COUNTDOWN,
            entity_category=EntityCategory.CONFIG,
            translation_key="countdown",
        ),
        SelectEntityDescription(
            key=DPCode.COUNTDOWN_SET,
            entity_category=EntityCategory.CONFIG,
            translation_key="countdown",
        ),
    ),
    DeviceCategory.QN: (
        SelectEntityDescription(
            key=DPCode.LEVEL,
            translation_key="temperature_level",
        ),
    ),
    DeviceCategory.SD: (
        SelectEntityDescription(
            key=DPCode.CISTERN,
            entity_category=EntityCategory.CONFIG,
            translation_key="vacuum_cistern",
        ),
        SelectEntityDescription(
            key=DPCode.COLLECTION_MODE,
            entity_category=EntityCategory.CONFIG,
            translation_key="vacuum_collection",
        ),
        SelectEntityDescription(
            key=DPCode.MODE,
            entity_category=EntityCategory.CONFIG,
            translation_key="vacuum_mode",
        ),
    ),
    DeviceCategory.SFKZQ: (
        # Irrigation will not be run within this set delay period
        SelectEntityDescription(
            key=DPCode.WEATHER_DELAY,
            translation_key="weather_delay",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.SGBJ: (
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
    DeviceCategory.SJZ: (
        SelectEntityDescription(
            key=DPCode.LEVEL,
            translation_key="desk_level",
            entity_category=EntityCategory.CONFIG,
        ),
        SelectEntityDescription(
            key=DPCode.UP_DOWN,
            translation_key="desk_up_down",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.SP: (
        SelectEntityDescription(
            key=DPCode.IPC_WORK_MODE,
            entity_category=EntityCategory.CONFIG,
            translation_key="ipc_work_mode",
        ),
        SelectEntityDescription(
            key=DPCode.DECIBEL_SENSITIVITY,
            entity_category=EntityCategory.CONFIG,
            translation_key="decibel_sensitivity",
        ),
        SelectEntityDescription(
            key=DPCode.RECORD_MODE,
            entity_category=EntityCategory.CONFIG,
            translation_key="record_mode",
        ),
        SelectEntityDescription(
            key=DPCode.BASIC_NIGHTVISION,
            entity_category=EntityCategory.CONFIG,
            translation_key="basic_nightvision",
        ),
        SelectEntityDescription(
            key=DPCode.BASIC_ANTI_FLICKER,
            entity_category=EntityCategory.CONFIG,
            translation_key="basic_anti_flicker",
        ),
        SelectEntityDescription(
            key=DPCode.MOTION_SENSITIVITY,
            entity_category=EntityCategory.CONFIG,
            translation_key="motion_sensitivity",
        ),
    ),
    DeviceCategory.SZJQR: (
        SelectEntityDescription(
            key=DPCode.MODE,
            entity_category=EntityCategory.CONFIG,
            translation_key="fingerbot_mode",
        ),
    ),
    DeviceCategory.TDQ: (
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
    DeviceCategory.TGKG: (
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
            translation_key="indexed_led_type",
            translation_placeholders={"index": "1"},
        ),
        SelectEntityDescription(
            key=DPCode.LED_TYPE_2,
            entity_category=EntityCategory.CONFIG,
            translation_key="indexed_led_type",
            translation_placeholders={"index": "2"},
        ),
        SelectEntityDescription(
            key=DPCode.LED_TYPE_3,
            entity_category=EntityCategory.CONFIG,
            translation_key="indexed_led_type",
            translation_placeholders={"index": "3"},
        ),
    ),
    DeviceCategory.TGQ: (
        SelectEntityDescription(
            key=DPCode.LED_TYPE_1,
            entity_category=EntityCategory.CONFIG,
            translation_key="indexed_led_type",
            translation_placeholders={"index": "1"},
        ),
        SelectEntityDescription(
            key=DPCode.LED_TYPE_2,
            entity_category=EntityCategory.CONFIG,
            translation_key="indexed_led_type",
            translation_placeholders={"index": "2"},
        ),
    ),
    DeviceCategory.XNYJCN: (
        SelectEntityDescription(
            key=DPCode.WORK_MODE,
            translation_key="inverter_work_mode",
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

COMMON_SELECT_DEFINITIONS: dict[CommonSelectType, SelectEntityDescription] = {
    CommonSelectType.CONTROL_BACK_MODE: SelectEntityDescription(
        key="tbc",
        entity_category=EntityCategory.CONFIG,
        translation_key="curtain_motor_mode",
    )
}


def _create_quirk_description(
    definition: TuyaSelectDefinition,
) -> SelectEntityDescription:
    common_definition = COMMON_SELECT_DEFINITIONS[definition.common_type]
    return SelectEntityDescription(
        key=DPCode(definition.key),
        translation_key=common_definition.translation_key,
        entity_category=common_definition.entity_category,
    )


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
            if quirk := TUYA_QUIRKS_REGISTRY.get_quirk_for_device(device):
                entities.extend(
                    TuyaSelectEntity(
                        device, manager, _create_quirk_description(definition)
                    )
                    for definition in quirk.select_definitions
                    if definition.key in device.status
                )
            elif descriptions := SELECTS.get(device.category):
                entities.extend(
                    TuyaSelectEntity(device, manager, description)
                    for description in descriptions
                    if description.key in device.status
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
