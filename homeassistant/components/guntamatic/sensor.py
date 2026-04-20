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
        key="status",
        translation_key="status",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
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
        key="domestic_home_water_temperature",
        translation_key="domestic_home_water_temperature",
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
        key="buffer_load",
        translation_key="buffer_load",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
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
        [
            GuntamaticSensor(coordinator, description)
            for description in GUNTAMATIC_SENSORS
            if description.key in coordinator.data
        ]
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
