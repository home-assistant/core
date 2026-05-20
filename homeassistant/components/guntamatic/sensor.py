"""Support for Guntamatic sensors in Home Assistant."""

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
    StateType,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import GuntamaticConfigEntry, GuntamaticCoordinator

PARALLEL_UPDATES = 0

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
        key="domestic_hot_water_0_temperature",
        translation_key="domestic_hot_water_0_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    SensorEntityDescription(
        key="domestic_hot_water_1_temperature",
        translation_key="domestic_hot_water_1_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    SensorEntityDescription(
        key="domestic_hot_water_2_temperature",
        translation_key="domestic_hot_water_2_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    SensorEntityDescription(
        key="room_0_temperature",
        translation_key="room_0_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    SensorEntityDescription(
        key="room_1_temperature",
        translation_key="room_1_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    SensorEntityDescription(
        key="room_2_temperature",
        translation_key="room_2_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    SensorEntityDescription(
        key="room_3_temperature",
        translation_key="room_3_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    SensorEntityDescription(
        key="room_4_temperature",
        translation_key="room_4_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    SensorEntityDescription(
        key="room_5_temperature",
        translation_key="room_5_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    SensorEntityDescription(
        key="room_6_temperature",
        translation_key="room_6_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    SensorEntityDescription(
        key="room_7_temperature",
        translation_key="room_7_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    SensorEntityDescription(
        key="room_8_temperature",
        translation_key="room_8_temperature",
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
        key="suction_fan",
        translation_key="suction_fan",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="primary_air",
        translation_key="primary_air",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="secondary_air",
        translation_key="secondary_air",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        # This is CO2 content in a flue. It is measured in % and goes really high.
        # It does not make sense to measure this as ppm as one does for air quality.
        key="co2_content",
        translation_key="co2_content",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="dhw_pump_0",
        translation_key="dhw_pump_0",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="dhw_pump_1",
        translation_key="dhw_pump_1",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="dhw_pump_2",
        translation_key="dhw_pump_2",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="heating_circulation_pump_0",
        translation_key="heating_circulation_pump_0",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="heating_circulation_pump_1",
        translation_key="heating_circulation_pump_1",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="heating_circulation_pump_2",
        translation_key="heating_circulation_pump_2",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="heating_circulation_pump_3",
        translation_key="heating_circulation_pump_3",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="heating_circulation_pump_4",
        translation_key="heating_circulation_pump_4",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="heating_circulation_pump_5",
        translation_key="heating_circulation_pump_5",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="heating_circulation_pump_6",
        translation_key="heating_circulation_pump_6",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="heating_circulation_pump_7",
        translation_key="heating_circulation_pump_7",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="heating_circulation_pump_8",
        translation_key="heating_circulation_pump_8",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="circuit_0_temp",
        translation_key="circuit_0_temp",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    SensorEntityDescription(
        key="circuit_1_temp",
        translation_key="circuit_1_temp",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    SensorEntityDescription(
        key="circuit_2_temp",
        translation_key="circuit_2_temp",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    SensorEntityDescription(
        key="circuit_3_temp",
        translation_key="circuit_3_temp",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    SensorEntityDescription(
        key="circuit_4_temp",
        translation_key="circuit_4_temp",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    SensorEntityDescription(
        key="circuit_5_temp",
        translation_key="circuit_5_temp",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    SensorEntityDescription(
        key="circuit_6_temp",
        translation_key="circuit_6_temp",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    SensorEntityDescription(
        key="circuit_7_temp",
        translation_key="circuit_7_temp",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    SensorEntityDescription(
        key="circuit_8_temp",
        translation_key="circuit_8_temp",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    SensorEntityDescription(
        key="heating_circulation_program_0",
        translation_key="heating_circulation_program_0",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="heating_circulation_program_1",
        translation_key="heating_circulation_program_1",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="heating_circulation_program_2",
        translation_key="heating_circulation_program_2",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="heating_circulation_program_3",
        translation_key="heating_circulation_program_3",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="heating_circulation_program_4",
        translation_key="heating_circulation_program_4",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="heating_circulation_program_5",
        translation_key="heating_circulation_program_5",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="heating_circulation_program_6",
        translation_key="heating_circulation_program_6",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="heating_circulation_program_7",
        translation_key="heating_circulation_program_7",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="heating_circulation_program_8",
        translation_key="heating_circulation_program_8",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="interruption_1",
        translation_key="interruption_1",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="interruption_2",
        translation_key="interruption_2",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="operating_time",
        translation_key="operating_time",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="service_hours",
        translation_key="service_hours",
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

    async_add_entities(
        GuntamaticSensor(coordinator, description)
        for description in GUNTAMATIC_SENSORS
        if description.key in coordinator.data
    )


class GuntamaticSensor(CoordinatorEntity[GuntamaticCoordinator], SensorEntity):
    """Representation of a single Guntamatic sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: GuntamaticCoordinator,
        entity_description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = entity_description

        serial = coordinator.data["serial"][0]

        self._attr_unique_id = f"{serial.replace('.', '_')}_{entity_description.key}"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial)},
            manufacturer="Guntamatic",
            serial_number=serial,
            sw_version=coordinator.data["version"][0],
        )

    @property
    def native_value(self) -> StateType:
        """Return the current value of the sensor."""
        return self.coordinator.data[self.entity_description.key][0]
