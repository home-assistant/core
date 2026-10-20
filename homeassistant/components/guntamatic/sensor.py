"""Support for Guntamatic sensors in Home Assistant."""

from datetime import date, timedelta
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
    *[
        SensorEntityDescription(
            key=f"room_{i}_temperature",
            translation_key="room_temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        )
        for i in range(9)
    ],
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
    *[
        SensorEntityDescription(
            key=f"auxiliary_pump_{nr}",
            translation_key="auxiliary_pump",
            translation_placeholders={"pump": str(nr + 1)},
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
    *[
        SensorEntityDescription(
            key=f"dhw_pump_{nr}",
            translation_key="dhw_pump",
            translation_placeholders={"circuit": str(nr + 1)},
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=PERCENTAGE,
            entity_registry_enabled_default=False,
            entity_category=EntityCategory.DIAGNOSTIC,
        )
        for nr in range(3)
    ],
    *[
        SensorEntityDescription(
            key=f"extra_dhw_{nr}_temperature",
            translation_key="extra_dhw_temperature",
            translation_placeholders={"circuit": str(nr)},
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            entity_registry_enabled_default=False,
        )
        for nr in range(3)
    ],
    *[
        SensorEntityDescription(
            key=f"extra_dhw_boost_{nr}",
            translation_key="extra_dhw_boost",
            translation_placeholders={"pump": str(nr + 1)},
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
    *[
        SensorEntityDescription(
            key=f"heating_circulation_pump_{i}",
            translation_key="heating_circulation_pump",
            device_class=SensorDeviceClass.ENUM,
            options=[
                "auto",
                "off",
                "nonstop",
            ],
            entity_category=EntityCategory.DIAGNOSTIC,
        )
        for i in range(9)
    ],
    *[
        SensorEntityDescription(
            key=f"circuit_{i}_temp",
            translation_key="circuit_temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            entity_category=EntityCategory.DIAGNOSTIC,
        )
        for i in range(9)
    ],
    *[
        SensorEntityDescription(
            key=f"heating_circulation_program_{i}",
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
        )
        for i in range(9)
    ],
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
            device_info: DeviceInfo | ChildDeviceInfo = ChildDeviceInfo(
                identifiers=identifiers,
                parent_device_id=main_device.id,
                name=f"Heating circuit {circuit}",
            )
        else:
            device_info = DeviceInfo(identifiers={(DOMAIN, serial)})
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
    def native_value(self) -> StateType | date:
        """Return the current value of the sensor."""
        value = self.coordinator.data[self.entity_description.key][0]
        if self.entity_description.device_class is SensorDeviceClass.DATE:
            return (dt_util.now() + timedelta(days=float(value))).date()
        if (
            self.entity_description.device_class is SensorDeviceClass.ENUM
            and value not in (self.entity_description.options or [])
        ):
            # The library passes through unmapped values of new firmware
            # languages; expose them as unknown instead of raising.
            return None
        return value
