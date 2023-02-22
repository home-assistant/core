"""Asuswrt status sensors."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    EntityCategory,
    UnitOfDataRate,
    UnitOfInformation,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import (
    DATA_ASUSWRT,
    DOMAIN,
    SENSORS_BYTES,
    SENSORS_CONNECTED_DEVICE,
    SENSORS_LOAD_AVG,
    SENSORS_RATES,
    SENSORS_TEMPERATURES,
)
from .router import KEY_COORDINATOR, KEY_SENSORS, AsusWrtRouter


@dataclass
class AsusWrtSensorEntityDescription(SensorEntityDescription):
    """A class that describes AsusWrt sensor entities."""

    factor: int | None = None


UNIT_DEVICES = "Devices"

CONNECTION_SENSORS: tuple[AsusWrtSensorEntityDescription, ...] = (
    AsusWrtSensorEntityDescription(
        key=SENSORS_CONNECTED_DEVICE[0],
        name="Devices Connected",
        icon="mdi:router-network",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UNIT_DEVICES,
    ),
    AsusWrtSensorEntityDescription(
        key=SENSORS_RATES[0],
        name="Download Speed",
        icon="mdi:download-network",
        device_class=SensorDeviceClass.DATA_RATE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfDataRate.MEGABITS_PER_SECOND,
        entity_registry_enabled_default=False,
        suggested_display_precision=2,
        factor=125000,
    ),
    AsusWrtSensorEntityDescription(
        key=SENSORS_RATES[1],
        name="Upload Speed",
        icon="mdi:upload-network",
        device_class=SensorDeviceClass.DATA_RATE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfDataRate.MEGABITS_PER_SECOND,
        entity_registry_enabled_default=False,
        suggested_display_precision=2,
        factor=125000,
    ),
    AsusWrtSensorEntityDescription(
        key=SENSORS_BYTES[0],
        name="Download",
        icon="mdi:download",
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfInformation.GIGABYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        entity_registry_enabled_default=False,
        suggested_display_precision=2,
        factor=1000000000,
    ),
    AsusWrtSensorEntityDescription(
        key=SENSORS_BYTES[1],
        name="Upload",
        icon="mdi:upload",
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfInformation.GIGABYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        entity_registry_enabled_default=False,
        suggested_display_precision=2,
        factor=1000000000,
    ),
    AsusWrtSensorEntityDescription(
        key=SENSORS_LOAD_AVG[0],
        name="Load Avg (1m)",
        icon="mdi:cpu-32-bit",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        suggested_display_precision=1,
    ),
    AsusWrtSensorEntityDescription(
        key=SENSORS_LOAD_AVG[1],
        name="Load Avg (5m)",
        icon="mdi:cpu-32-bit",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        suggested_display_precision=1,
    ),
    AsusWrtSensorEntityDescription(
        key=SENSORS_LOAD_AVG[2],
        name="Load Avg (15m)",
        icon="mdi:cpu-32-bit",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        suggested_display_precision=1,
    ),
    AsusWrtSensorEntityDescription(
        key=SENSORS_TEMPERATURES[0],
        name="2.4GHz Temperature",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        suggested_display_precision=1,
    ),
    AsusWrtSensorEntityDescription(
        key=SENSORS_TEMPERATURES[1],
        name="5GHz Temperature",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        suggested_display_precision=1,
    ),
    AsusWrtSensorEntityDescription(
        key=SENSORS_TEMPERATURES[2],
        name="CPU Temperature",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        suggested_display_precision=1,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the sensors."""
    router: AsusWrtRouter = hass.data[DOMAIN][entry.entry_id][DATA_ASUSWRT]
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

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        router: AsusWrtRouter,
        description: AsusWrtSensorEntityDescription,
    ) -> None:
        """Initialize a AsusWrt sensor."""
        super().__init__(coordinator)
        self.entity_description: AsusWrtSensorEntityDescription = description

        self._attr_name = f"{router.name} {description.name}"
        if router.unique_id:
            self._attr_unique_id = f"{DOMAIN} {router.unique_id} {description.name}"
        else:
            self._attr_unique_id = f"{DOMAIN} {self.name}"
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
