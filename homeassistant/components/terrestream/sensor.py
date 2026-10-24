"""Sensor entities for Terrestream measurements."""

from typing import override

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    LIGHT_LUX,
    UnitOfDensity,
    UnitOfPressure,
    UnitOfRatio,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TerrestreamConfigEntry, TerrestreamCoordinator

PARALLEL_UPDATES = 0

SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="co2",
        device_class=SensorDeviceClass.CO2,
        native_unit_of_measurement=UnitOfRatio.PARTS_PER_MILLION,
    ),
    SensorEntityDescription(
        key="pm1",
        device_class=SensorDeviceClass.PM1,
        native_unit_of_measurement=UnitOfDensity.MICROGRAMS_PER_CUBIC_METER,
    ),
    SensorEntityDescription(
        key="pm25",
        device_class=SensorDeviceClass.PM25,
        native_unit_of_measurement=UnitOfDensity.MICROGRAMS_PER_CUBIC_METER,
    ),
    SensorEntityDescription(
        key="pm4",
        translation_key="pm4",
        device_class=SensorDeviceClass.PM4,
        native_unit_of_measurement=UnitOfDensity.MICROGRAMS_PER_CUBIC_METER,
    ),
    SensorEntityDescription(
        key="pm10",
        device_class=SensorDeviceClass.PM10,
        native_unit_of_measurement=UnitOfDensity.MICROGRAMS_PER_CUBIC_METER,
    ),
    SensorEntityDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    SensorEntityDescription(
        key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
    ),
    SensorEntityDescription(
        key="pressure",
        translation_key="pressure",
        device_class=SensorDeviceClass.ATMOSPHERIC_PRESSURE,
        native_unit_of_measurement=UnitOfPressure.HPA,
    ),
    SensorEntityDescription(
        key="illuminance",
        device_class=SensorDeviceClass.ILLUMINANCE,
        native_unit_of_measurement=LIGHT_LUX,
    ),
    SensorEntityDescription(
        key="computed_epa_aqi",
        translation_key="computed_epa_aqi",
        device_class=SensorDeviceClass.AQI,
    ),
    SensorEntityDescription(key="voc_index", translation_key="voc_index"),
    SensorEntityDescription(key="nox_index", translation_key="nox_index"),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TerrestreamConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create the supported measurement entities."""
    async_add_entities(
        TerrestreamSensor(entry.runtime_data, description) for description in SENSORS
    )


class TerrestreamSensor(CoordinatorEntity[TerrestreamCoordinator], SensorEntity):
    """Expose a measurement from the latest completed poll."""

    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: TerrestreamCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the measurement and its device metadata."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = (
            f"{coordinator.client.credentials.uuid}_{description.key}"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.client.credentials.uuid)},
            manufacturer="Terrestream",
            model=coordinator.data["model"],
            sw_version=coordinator.data["firmware"],
            hw_version=coordinator.data.get("hardware"),
        )

    @property
    @override
    def available(self) -> bool:
        """Return whether the latest poll reported a valid measurement."""
        return (
            super().available
            and self.coordinator.data["measurements"][self.entity_description.key][
                "available"
            ]
        )

    @property
    @override
    def native_value(self) -> float | int | None:
        """Return the last reported measurement."""
        return self.coordinator.data["measurements"][self.entity_description.key].get(
            "value"
        )
