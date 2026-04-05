"""Support for Guntamatic sensors in Home Assistant."""

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
    StateType,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DIAGNOSTIC_SENSORS, DOMAIN

PARALLEL_UPDATES = 0

# Mapping from unit of measurement to sensor description.
UNIT_TO_DESCRIPTION: dict[str, SensorEntityDescription] = {
    "°C": SensorEntityDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="°C",
    ),
    "%": SensorEntityDescription(
        key="percentage",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="%",
    ),
    "h": SensorEntityDescription(
        key="duration_hours",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement="h",
    ),
    "d": SensorEntityDescription(
        key="duration_days",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement="d",
    ),
}

type GuntamaticCoordinator = DataUpdateCoordinator[dict[str, list[str]]]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Guntamatic sensors from config entry."""

    data = entry.runtime_data
    coordinator = data.coordinator
    heater = data.heater

    # Create one entity per sensor
    sensors = [
        GuntamaticSensor(coordinator, name, heater.host) for name in coordinator.data
    ]

    async_add_entities(sensors)


class GuntamaticSensor(CoordinatorEntity[GuntamaticCoordinator], SensorEntity):
    """Representation of a single Guntamatic sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: GuntamaticCoordinator,
        name: str,
        host: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._name = name
        self._attr_name = name
        serial = coordinator.data["Serial"][0]

        self._attr_unique_id = f"{serial.replace('.', '_')}_{name.replace(' ', '_')}"

        unit = coordinator.data[name][1]
        description = UNIT_TO_DESCRIPTION.get(unit)
        if description is not None:
            self.entity_description = description

        self._attr_entity_category = (
            EntityCategory.DIAGNOSTIC if name in DIAGNOSTIC_SENSORS else None
        )

        # if no unit is given by the guntamatic, it's a string, so set None
        if not unit:
            self._attr_native_unit_of_measurement = None
            self._attr_state_class = None
            self._attr_device_class = SensorDeviceClass.ENUM

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
