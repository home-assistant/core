"""Asuswrt status sensors."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfDataRate,
    UnitOfInformation,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from homeassistant.util import slugify

from . import AsusWrtConfigEntry
from .const import (
    KEY_COORDINATOR,
    KEY_SENSORS,
    SENSORS_BYTES,
    SENSORS_CONNECTED_DEVICE,
    SENSORS_CPU,
    SENSORS_LOAD_AVG,
    SENSORS_MEMORY,
    SENSORS_RATES,
    SENSORS_TEMPERATURES,
    SENSORS_UPTIME,
)
from .router import AsusWrtRouter


@dataclass(frozen=True)
class AsusWrtSensorEntityDescription(SensorEntityDescription):
    """A class that describes AsusWrt sensor entities."""

    factor: int | None = None


UNIT_DEVICES = "Devices"

CPU_CORE_SENSORS: tuple[AsusWrtSensorEntityDescription, ...] = tuple(
    AsusWrtSensorEntityDescription(
        key=sens_key,
        translation_key="cpu_core_usage",
        translation_placeholders={"core_id": str(core_id)},
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        suggested_display_precision=1,
    )
    for core_id, sens_key in enumerate(SENSORS_CPU[1:], start=1)
)
CONNECTION_SENSORS: tuple[AsusWrtSensorEntityDescription, ...] = (
    AsusWrtSensorEntityDescription(
        key=SENSORS_CONNECTED_DEVICE[0],
        translation_key="devices_connected",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UNIT_DEVICES,
    ),
    AsusWrtSensorEntityDescription(
        key=SENSORS_RATES[0],
        translation_key="download_speed",
        device_class=SensorDeviceClass.DATA_RATE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfDataRate.MEGABITS_PER_SECOND,
        entity_registry_enabled_default=False,
        suggested_display_precision=2,
        factor=125000,
    ),
    AsusWrtSensorEntityDescription(
        key=SENSORS_RATES[1],
        translation_key="upload_speed",
        device_class=SensorDeviceClass.DATA_RATE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfDataRate.MEGABITS_PER_SECOND,
        entity_registry_enabled_default=False,
        suggested_display_precision=2,
        factor=125000,
    ),
    AsusWrtSensorEntityDescription(
        key=SENSORS_BYTES[0],
        translation_key="download",
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfInformation.GIGABYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        entity_registry_enabled_default=False,
        suggested_display_precision=2,
        factor=1000000000,
    ),
    AsusWrtSensorEntityDescription(
        key=SENSORS_BYTES[1],
        translation_key="upload",
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfInformation.GIGABYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        entity_registry_enabled_default=False,
        suggested_display_precision=2,
        factor=1000000000,
    ),
    AsusWrtSensorEntityDescription(
        key=SENSORS_LOAD_AVG[0],
        translation_key="load_avg_1m",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        suggested_display_precision=1,
    ),
    AsusWrtSensorEntityDescription(
        key=SENSORS_LOAD_AVG[1],
        translation_key="load_avg_5m",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        suggested_display_precision=1,
    ),
    AsusWrtSensorEntityDescription(
        key=SENSORS_LOAD_AVG[2],
        translation_key="load_avg_15m",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        suggested_display_precision=1,
    ),
    AsusWrtSensorEntityDescription(
        key=SENSORS_TEMPERATURES[0],
        translation_key="24ghz_temperature",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        suggested_display_precision=1,
    ),
    AsusWrtSensorEntityDescription(
        key=SENSORS_TEMPERATURES[1],
        translation_key="5ghz_temperature",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        suggested_display_precision=1,
    ),
    AsusWrtSensorEntityDescription(
        key=SENSORS_TEMPERATURES[2],
        translation_key="cpu_temperature",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        suggested_display_precision=1,
    ),
    AsusWrtSensorEntityDescription(
        key=SENSORS_TEMPERATURES[3],
        translation_key="5ghz_2_temperature",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        suggested_display_precision=1,
    ),
    AsusWrtSensorEntityDescription(
        key=SENSORS_TEMPERATURES[4],
        translation_key="6ghz_temperature",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        suggested_display_precision=1,
    ),
    AsusWrtSensorEntityDescription(
        key=SENSORS_MEMORY[0],
        translation_key="memory_usage",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        suggested_display_precision=1,
    ),
    AsusWrtSensorEntityDescription(
        key=SENSORS_MEMORY[1],
        translation_key="memory_free",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.MEGABYTES,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        suggested_display_precision=2,
        factor=1024,
    ),
    AsusWrtSensorEntityDescription(
        key=SENSORS_MEMORY[2],
        translation_key="memory_used",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.MEGABYTES,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        suggested_display_precision=2,
        factor=1024,
    ),
    AsusWrtSensorEntityDescription(
        key=SENSORS_UPTIME[0],
        translation_key="last_boot",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    AsusWrtSensorEntityDescription(
        key=SENSORS_UPTIME[1],
        translation_key="uptime",
        state_class=SensorStateClass.TOTAL,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    AsusWrtSensorEntityDescription(
        key=SENSORS_CPU[0],
        translation_key="cpu_usage",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        suggested_display_precision=1,
    ),
    *CPU_CORE_SENSORS,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AsusWrtConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensors."""
    router = entry.runtime_data
    entities = []

    for sensor_data in router.sensors_coordinator.values():
        coordinator = sensor_data[KEY_COORDINATOR]
        sensors = sensor_data[KEY_SENSORS]
        entities.extend(
            [
                AsusWrtSensor(coordinator, router, sensor_descr)
                for sensor_descr in CONNECTION_SENSORS
                if sensor_descr.key in sensors
            ]
        )

    async_add_entities(entities, True)


class AsusWrtSensor(CoordinatorEntity, SensorEntity):
    """Representation of a AsusWrt sensor."""

    entity_description: AsusWrtSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        router: AsusWrtRouter,
        description: AsusWrtSensorEntityDescription,
    ) -> None:
        """Initialize a AsusWrt sensor."""
        super().__init__(coordinator)
        self.entity_description = description

        self._attr_unique_id = slugify(f"{router.unique_id}_{description.key}")
        self._attr_device_info = router.device_info
        self._attr_extra_state_attributes = {"hostname": router.host}

    @property
    def native_value(self) -> float | int | str | None:
        """Return current state."""
        descr = self.entity_description
        state: float | int | str | None = self.coordinator.data.get(descr.key)
        if state is not None and descr.factor and isinstance(state, (float, int)):
            return state / descr.factor
        return state
