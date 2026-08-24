"""Support for Guntamatic sensors in Home Assistant."""

from datetime import timedelta
import re
from typing import override

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
    StateType,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import ChildDeviceInfo, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import GuntamaticConfigEntry, GuntamaticCoordinator

PARALLEL_UPDATES = 0

HEATING_CIRCUIT_REGEX = re.compile(
    r"^(?:room|circuit|heating_circulation_pump|heating_circulation_program)_(\d+)"
)

GUNTAMATIC_SENSORS: list[SensorEntityDescription] = [
    SensorEntityDescription(
        key="program",
        translation_key="program",
        device_class=SensorDeviceClass.ENUM,
        options=[
            "off",
            "timer",
            "dhw",
            "heat",
            "hibernate",
            "hibernate_to",
            "dhw_boost",
        ],
    ),
    SensorEntityDescription(
        key="status",
        translation_key="status",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="boiler_temperature",
        translation_key="boiler_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    SensorEntityDescription(
        key="outdoor_temperature",
        translation_key="outdoor_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    SensorEntityDescription(
        key="buffer_top_temperature",
        translation_key="buffer_top_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    SensorEntityDescription(
        key="buffer_top_0_temperature",
        translation_key="buffer_stage_top_temperature",
        translation_placeholders={"tank": "1"},
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="buffer_top_1_temperature",
        translation_key="buffer_stage_top_temperature",
        translation_placeholders={"tank": "2"},
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="buffer_top_2_temperature",
        translation_key="buffer_stage_top_temperature",
        translation_placeholders={"tank": "3"},
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="buffer_center_temperature",
        translation_key="buffer_center_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    SensorEntityDescription(
        key="buffer_bottom_temperature",
        translation_key="buffer_bottom_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    SensorEntityDescription(
        key="buffer_bottom_0_temperature",
        translation_key="buffer_stage_bottom_temperature",
        translation_placeholders={"tank": "1"},
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="buffer_bottom_1_temperature",
        translation_key="buffer_stage_bottom_temperature",
        translation_placeholders={"tank": "2"},
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="buffer_bottom_2_temperature",
        translation_key="buffer_stage_bottom_temperature",
        translation_placeholders={"tank": "3"},
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="domestic_hot_water_0_temperature",
        translation_key="domestic_hot_water_temperature",
        translation_placeholders={"circuit": "1"},
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    SensorEntityDescription(
        key="domestic_hot_water_1_temperature",
        translation_key="domestic_hot_water_temperature",
        translation_placeholders={"circuit": "2"},
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    SensorEntityDescription(
        key="domestic_hot_water_2_temperature",
        translation_key="domestic_hot_water_temperature",
        translation_placeholders={"circuit": "3"},
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    SensorEntityDescription(
        key="room_0_temperature",
        translation_key="room_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    SensorEntityDescription(
        key="room_1_temperature",
        translation_key="room_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    SensorEntityDescription(
        key="room_2_temperature",
        translation_key="room_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    SensorEntityDescription(
        key="room_3_temperature",
        translation_key="room_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    SensorEntityDescription(
        key="room_4_temperature",
        translation_key="room_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    SensorEntityDescription(
        key="room_5_temperature",
        translation_key="room_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    SensorEntityDescription(
        key="room_6_temperature",
        translation_key="room_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    SensorEntityDescription(
        key="room_7_temperature",
        translation_key="room_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    SensorEntityDescription(
        key="room_8_temperature",
        translation_key="room_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    SensorEntityDescription(
        key="buffer_load",
        translation_key="buffer_load",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
    ),
    SensorEntityDescription(
        key="boiler_shunt_pump",
        translation_key="boiler_shunt_pump",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="auxiliary_pump_0",
        translation_key="auxiliary_pump",
        device_class=SensorDeviceClass.ENUM,
        options=[
            "auto",
            "off",
            "nonstop",
        ],
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="auxiliary_pump_1",
        translation_key="auxiliary_pump",
        device_class=SensorDeviceClass.ENUM,
        options=[
            "auto",
            "off",
            "nonstop",
        ],
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="auxiliary_pump_2",
        translation_key="auxiliary_pump",
        device_class=SensorDeviceClass.ENUM,
        options=[
            "auto",
            "off",
            "nonstop",
        ],
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="suction_fan",
        translation_key="suction_fan",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="primary_air",
        translation_key="primary_air",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="secondary_air",
        translation_key="secondary_air",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        # This is CO2 content in a flue. It is measured in % and goes really high.
        # It does not make sense to measure this as ppm as one does for air quality.
        key="co2_content",
        translation_key="co2_content",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="dhw_pump_0",
        translation_key="dhw_pump",
        translation_placeholders={"circuit": "1"},
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="dhw_pump_1",
        translation_key="dhw_pump",
        translation_placeholders={"circuit": "2"},
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="dhw_pump_2",
        translation_key="dhw_pump",
        translation_placeholders={"circuit": "3"},
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    *[
        SensorEntityDescription(
            key=f"extra_dhw_{nr}_temperature",
            translation_key="extra_dhw_temperature",
            translation_placeholders={"circuit": str(nr + 1)},
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            entity_registry_enabled_default=False,
        )
        for nr in (1, 2)
    ],
    *[
        SensorEntityDescription(
            key=f"extra_dhw_boost_{nr}",
            translation_key="extra_dhw_boost",
            device_class=SensorDeviceClass.ENUM,
            options=[
                "auto",
                "off",
                "nonstop",
            ],
            entity_registry_enabled_default=False,
            entity_category=EntityCategory.DIAGNOSTIC,
        )
        for nr in range(3)
    ],
    SensorEntityDescription(
        key="heating_circulation_pump_0",
        translation_key="heating_circulation_pump",
        device_class=SensorDeviceClass.ENUM,
        options=[
            "auto",
            "off",
            "nonstop",
        ],
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="heating_circulation_pump_1",
        translation_key="heating_circulation_pump",
        device_class=SensorDeviceClass.ENUM,
        options=[
            "auto",
            "off",
            "nonstop",
        ],
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="heating_circulation_pump_2",
        translation_key="heating_circulation_pump",
        device_class=SensorDeviceClass.ENUM,
        options=[
            "auto",
            "off",
            "nonstop",
        ],
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="heating_circulation_pump_3",
        translation_key="heating_circulation_pump",
        device_class=SensorDeviceClass.ENUM,
        options=[
            "auto",
            "off",
            "nonstop",
        ],
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="heating_circulation_pump_4",
        translation_key="heating_circulation_pump",
        device_class=SensorDeviceClass.ENUM,
        options=[
            "auto",
            "off",
            "nonstop",
        ],
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="heating_circulation_pump_5",
        translation_key="heating_circulation_pump",
        device_class=SensorDeviceClass.ENUM,
        options=[
            "auto",
            "off",
            "nonstop",
        ],
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="heating_circulation_pump_6",
        translation_key="heating_circulation_pump",
        device_class=SensorDeviceClass.ENUM,
        options=[
            "auto",
            "off",
            "nonstop",
        ],
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="heating_circulation_pump_7",
        translation_key="heating_circulation_pump",
        device_class=SensorDeviceClass.ENUM,
        options=[
            "auto",
            "off",
            "nonstop",
        ],
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="heating_circulation_pump_8",
        translation_key="heating_circulation_pump",
        device_class=SensorDeviceClass.ENUM,
        options=[
            "auto",
            "off",
            "nonstop",
        ],
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="circuit_0_temp",
        translation_key="circuit_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="circuit_1_temp",
        translation_key="circuit_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="circuit_2_temp",
        translation_key="circuit_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="circuit_3_temp",
        translation_key="circuit_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="circuit_4_temp",
        translation_key="circuit_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="circuit_5_temp",
        translation_key="circuit_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="circuit_6_temp",
        translation_key="circuit_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="circuit_7_temp",
        translation_key="circuit_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="circuit_8_temp",
        translation_key="circuit_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="heating_circulation_program_0",
        translation_key="heating_circulation_program",
        device_class=SensorDeviceClass.ENUM,
        options=[
            "off",
            "timer",
            "heat",
            "hibernate",
            "hibernate_to",
        ],
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="heating_circulation_program_1",
        translation_key="heating_circulation_program",
        device_class=SensorDeviceClass.ENUM,
        options=[
            "off",
            "timer",
            "heat",
            "hibernate",
            "hibernate_to",
        ],
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="heating_circulation_program_2",
        translation_key="heating_circulation_program",
        device_class=SensorDeviceClass.ENUM,
        options=[
            "off",
            "timer",
            "heat",
            "hibernate",
            "hibernate_to",
        ],
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="heating_circulation_program_3",
        translation_key="heating_circulation_program",
        device_class=SensorDeviceClass.ENUM,
        options=[
            "off",
            "timer",
            "heat",
            "hibernate",
            "hibernate_to",
        ],
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="heating_circulation_program_4",
        translation_key="heating_circulation_program",
        device_class=SensorDeviceClass.ENUM,
        options=[
            "off",
            "timer",
            "heat",
            "hibernate",
            "hibernate_to",
        ],
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="heating_circulation_program_5",
        translation_key="heating_circulation_program",
        device_class=SensorDeviceClass.ENUM,
        options=[
            "off",
            "timer",
            "heat",
            "hibernate",
            "hibernate_to",
        ],
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="heating_circulation_program_6",
        translation_key="heating_circulation_program",
        device_class=SensorDeviceClass.ENUM,
        options=[
            "off",
            "timer",
            "heat",
            "hibernate",
            "hibernate_to",
        ],
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="heating_circulation_program_7",
        translation_key="heating_circulation_program",
        device_class=SensorDeviceClass.ENUM,
        options=[
            "off",
            "timer",
            "heat",
            "hibernate",
            "hibernate_to",
        ],
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="heating_circulation_program_8",
        translation_key="heating_circulation_program",
        device_class=SensorDeviceClass.ENUM,
        options=[
            "off",
            "timer",
            "heat",
            "hibernate",
            "hibernate_to",
        ],
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="interruption_1",
        translation_key="interruption",
        translation_placeholders={"number": "1"},
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="interruption_2",
        translation_key="interruption",
        translation_placeholders={"number": "2"},
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="operating_time",
        translation_key="operating_time",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfTime.HOURS,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="service_days",
        translation_key="service_date",
        device_class=SensorDeviceClass.DATE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GuntamaticConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Guntamatic sensors from config entry."""
    coordinator = entry.runtime_data
    serial = coordinator.data["serial"][0]

    device_registry = dr.async_get(hass)
    main_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, serial)},
        manufacturer="Guntamatic",
        serial_number=serial,
        sw_version=coordinator.data["version"][0],
    )

    entities: list[GuntamaticSensor] = []
    for description in GUNTAMATIC_SENSORS:
        if description.key not in coordinator.data:
            continue
        if match := HEATING_CIRCUIT_REGEX.match(description.key):
            circuit = int(match.group(1))
            identifiers = {(DOMAIN, f"{serial}_hc{circuit}")}
            device_registry.async_get_or_create_child(
                config_entry_id=entry.entry_id,
                identifiers=identifiers,
                parent_device_id=main_device.id,
                name=f"Heating circuit {circuit}",
            )
        else:
            identifiers = {(DOMAIN, serial)}
        if match:
            device_info: DeviceInfo | ChildDeviceInfo = ChildDeviceInfo(
                identifiers=identifiers,
                parent_device_id=main_device.id,
            )
        else:
            device_info = DeviceInfo(identifiers=identifiers)
        entities.append(GuntamaticSensor(coordinator, description, device_info))

    async_add_entities(entities)


class GuntamaticSensor(CoordinatorEntity[GuntamaticCoordinator], SensorEntity):
    """Representation of a single Guntamatic sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: GuntamaticCoordinator,
        entity_description: SensorEntityDescription,
        device_info: DeviceInfo | ChildDeviceInfo,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = entity_description

        serial = coordinator.data["serial"][0]

        self._attr_unique_id = f"{serial.replace('.', '_')}_{entity_description.key}"
        self._attr_device_info = device_info

    @property
    @override
    def available(self) -> bool:
        """Return whether the entity is available."""
        return (
            super().available and self.entity_description.key in self.coordinator.data
        )

    @property
    @override
    def native_value(self) -> StateType:
        """Return the current value of the sensor."""
        value = self.coordinator.data[self.entity_description.key][0]
        if self.entity_description.device_class is SensorDeviceClass.DATE:
            return dt_util.now().date() + timedelta(days=int(value))
        if (
            self.entity_description.device_class is SensorDeviceClass.ENUM
            and value not in (self.entity_description.options or [])
        ):
            # The library passes through unmapped values of new firmware
            # languages; expose them as unknown instead of raising.
            return None
        return value
