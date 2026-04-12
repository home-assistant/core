"""Support for Guntamatic sensors in Home Assistant."""

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
    StateType,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import GuntamaticCoordinator

PARALLEL_UPDATES = 0

GUNTAMATIC_SENSORS: list[SensorEntityDescription] = [
    SensorEntityDescription(
        key="Status",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="Program",
        device_class=SensorDeviceClass.ENUM,
        options=[
            "OFF",
            "TIMER",
            "DHW",
            "HEAT",
            "HIBERNAT",
            "HIBERNATE TO",
            "DHW BOOST",
        ],
    ),
    SensorEntityDescription(key="Serial", entity_category=EntityCategory.DIAGNOSTIC),
    SensorEntityDescription(key="Version", entity_category=EntityCategory.DIAGNOSTIC),
    SensorEntityDescription(
        key="Boiler Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    SensorEntityDescription(
        key="Outdoor Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    SensorEntityDescription(
        key="Buffer Top Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    SensorEntityDescription(
        key="Buffer Center Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    SensorEntityDescription(
        key="Buffer Bottom Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    SensorEntityDescription(
        key="Domestic Home Water Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    SensorEntityDescription(
        key="Room 1 Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    SensorEntityDescription(
        key="Room 2 Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    SensorEntityDescription(
        key="Buffer Load",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Guntamatic sensors from config entry."""

    coordinator = entry.runtime_data

    sensors = [
        GuntamaticSensor(coordinator, description)
        for description in GUNTAMATIC_SENSORS
        if description.key in coordinator.data
    ]

    async_add_entities(sensors)


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

        self._name = entity_description.key
        self._attr_name = entity_description.key

        serial = coordinator.data["Serial"][0]

        self._attr_unique_id = (
            f"{serial.replace('.', '_')}_{entity_description.key.replace(' ', '_')}"
        )

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial)},
            name="Guntamatic Heater",
            manufacturer="Guntamatic",
            serial_number=serial,
            sw_version=coordinator.data.get("Version", [""])[0] or None,
        )

    @property
    def native_value(self) -> StateType:
        """Return the current value of the sensor."""
        value = self.coordinator.data[self._name][0]

        if self.entity_description.state_class == SensorStateClass.MEASUREMENT:
            try:
                return float(value)
            except TypeError, ValueError:
                return value
        return value

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self._name in self.coordinator.data
