"""Support for Guntamatic sensors in Home Assistant."""

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
    StateType,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN

PARALLEL_UPDATES = 0

# Mapping from unit of measurement to sensor description.
GUNTAMATIC_SENSORS: list[SensorEntityDescription] = [
    SensorEntityDescription(
        key="Status",
        device_class=SensorDeviceClass.ENUM,
    ),
    SensorEntityDescription(
        key="Program",
        device_class=SensorDeviceClass.ENUM,
    ),
    SensorEntityDescription(
        key="Serial",
        device_class=SensorDeviceClass.ENUM,
    ),
    SensorEntityDescription(
        key="Version",
        device_class=SensorDeviceClass.ENUM,
    ),
    SensorEntityDescription(
        key="Boiler Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="°C",
    ),
    SensorEntityDescription(
        key="Outdoor Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="°C",
    ),
    SensorEntityDescription(
        key="Buffer Top Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="°C",
    ),
    SensorEntityDescription(
        key="Buffer Center Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="°C",
    ),
    SensorEntityDescription(
        key="Buffer Bottom Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="°C",
    ),
    SensorEntityDescription(
        key="Domestic Home Water Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="°C",
    ),
    SensorEntityDescription(
        key="Room 1 Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="°C",
    ),
    SensorEntityDescription(
        key="Room 2 Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="°C",
    ),
    SensorEntityDescription(
        key="Buffer Load",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="%",
    ),
]

type GuntamaticCoordinator = DataUpdateCoordinator[dict[str, list[str]]]


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
        entitydescription: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = entitydescription

        self._name = entitydescription.key
        self._attr_name = entitydescription.key

        serial = coordinator.data["Serial"][0]

        self._attr_unique_id = (
            f"{serial.replace('.', '_')}_{entitydescription.key.replace(' ', '_')}"
        )

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial)},
            name="Guntamatic Heater",
            manufacturer="Guntamatic",
            serial_number=serial,
            sw_version=coordinator.data.get("Version", [None])[0],
        )

    @property
    def native_value(self) -> StateType:
        """Return the current value of the sensor."""
        return self.coordinator.data[self._name][0]

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self._name in self.coordinator.data
