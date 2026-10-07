"""Support for airthings ble sensors."""

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import override

from airthings_ble import AirthingsConnectivityMode, AirthingsDevice

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    LIGHT_LUX,
    EntityCategory,
    UnitOfPressure,
    UnitOfRadiationConcentration,
    UnitOfRatio,
    UnitOfSoundPressure,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import AirthingsBLEConfigEntry, AirthingsBLEDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

CONNECTIVITY_MODE_MAP = {
    AirthingsConnectivityMode.BLE.value: "bluetooth",
    AirthingsConnectivityMode.SMARTLINK.value: "smartlink",
    AirthingsConnectivityMode.NOT_CONFIGURED.value: "not_configured",
}


def get_connectivity_mode(value: str | float | None) -> str | None:
    """Get connectivity mode."""
    if not isinstance(value, str):
        return None
    return CONNECTIVITY_MODE_MAP.get(value)


@dataclass(frozen=True, kw_only=True)
class AirthingsBLESensorEntityDescription(SensorEntityDescription):
    """Describes Airthings BLE sensor entity."""

    value_fn: Callable[[str | float | None], str | float | None] = lambda x: x


SENSORS_MAPPING_TEMPLATE: dict[str, AirthingsBLESensorEntityDescription] = {
    "radon_1day_avg": AirthingsBLESensorEntityDescription(
        key="radon_1day_avg",
        translation_key="radon_1day_avg",
        device_class=SensorDeviceClass.RADON,
        native_unit_of_measurement=UnitOfRadiationConcentration.BECQUEREL_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "radon_longterm_avg": AirthingsBLESensorEntityDescription(
        key="radon_longterm_avg",
        translation_key="radon_longterm_avg",
        device_class=SensorDeviceClass.RADON,
        native_unit_of_measurement=UnitOfRadiationConcentration.BECQUEREL_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "radon_1day_level": AirthingsBLESensorEntityDescription(
        key="radon_1day_level",
        translation_key="radon_1day_level",
        device_class=SensorDeviceClass.ENUM,
        options=["good", "fair", "poor"],
        value_fn=lambda value: value if value != "unknown" else None,
    ),
    "radon_longterm_level": AirthingsBLESensorEntityDescription(
        key="radon_longterm_level",
        translation_key="radon_longterm_level",
        device_class=SensorDeviceClass.ENUM,
        options=["good", "fair", "poor"],
        value_fn=lambda value: value if value != "unknown" else None,
    ),
    "temperature": AirthingsBLESensorEntityDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    "humidity": AirthingsBLESensorEntityDescription(
        key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    "pressure": AirthingsBLESensorEntityDescription(
        key="pressure",
        device_class=SensorDeviceClass.ATMOSPHERIC_PRESSURE,
        native_unit_of_measurement=UnitOfPressure.MBAR,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    "battery": AirthingsBLESensorEntityDescription(
        key="battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=0,
    ),
    "co2": AirthingsBLESensorEntityDescription(
        key="co2",
        device_class=SensorDeviceClass.CO2,
        native_unit_of_measurement=UnitOfRatio.PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    "voc": AirthingsBLESensorEntityDescription(
        key="voc",
        device_class=SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS_PARTS,
        native_unit_of_measurement=UnitOfRatio.PARTS_PER_BILLION,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    "illuminance": AirthingsBLESensorEntityDescription(
        key="illuminance",
        translation_key="illuminance",
        native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    "lux": AirthingsBLESensorEntityDescription(
        key="lux",
        device_class=SensorDeviceClass.ILLUMINANCE,
        native_unit_of_measurement=LIGHT_LUX,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    "noise": AirthingsBLESensorEntityDescription(
        key="noise",
        translation_key="ambient_noise",
        device_class=SensorDeviceClass.SOUND_PRESSURE,
        native_unit_of_measurement=UnitOfSoundPressure.WEIGHTED_DECIBEL_A,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    "connectivity_mode": AirthingsBLESensorEntityDescription(
        key="connectivity_mode",
        translation_key="connectivity_mode",
        device_class=SensorDeviceClass.ENUM,
        options=list(CONNECTIVITY_MODE_MAP.values()),
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=get_connectivity_mode,
    ),
}

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AirthingsBLEConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Airthings BLE sensors."""
    coordinator = entry.runtime_data

    entities = []
    _LOGGER.debug("got sensors: %s", coordinator.data.sensors)
    for sensor_type, sensor_value in coordinator.data.sensors.items():
        if sensor_type not in SENSORS_MAPPING_TEMPLATE:
            _LOGGER.debug(
                "Unknown sensor type detected: %s, %s",
                sensor_type,
                sensor_value,
            )
            continue
        entities.append(
            AirthingsSensor(
                coordinator, coordinator.data, SENSORS_MAPPING_TEMPLATE[sensor_type]
            )
        )

    async_add_entities(entities)


class AirthingsSensor(
    CoordinatorEntity[AirthingsBLEDataUpdateCoordinator], SensorEntity
):
    """Airthings BLE sensors for the device."""

    _attr_has_entity_name = True
    entity_description: AirthingsBLESensorEntityDescription

    def __init__(
        self,
        coordinator: AirthingsBLEDataUpdateCoordinator,
        airthings_device: AirthingsDevice,
        entity_description: AirthingsBLESensorEntityDescription,
    ) -> None:
        """Populate the airthings entity with relevant data."""
        super().__init__(coordinator)
        self.entity_description = entity_description

        name = airthings_device.name
        if identifier := airthings_device.identifier:
            name += f" ({identifier})"

        self._attr_unique_id = f"{airthings_device.address}_{entity_description.key}"
        self._attr_device_info = DeviceInfo(
            connections={
                (
                    CONNECTION_BLUETOOTH,
                    airthings_device.address,
                )
            },
            name=name,
            manufacturer=airthings_device.manufacturer,
            hw_version=airthings_device.hw_version,
            sw_version=airthings_device.sw_version,
            model=airthings_device.model.product_name,
        )

    @property
    @override
    def available(self) -> bool:
        """Check if device and sensor is available in data."""
        return (
            super().available
            and self.entity_description.key in self.coordinator.data.sensors
        )

    @property
    @override
    def native_value(self) -> StateType:
        """Return the value reported by the sensor."""
        value = self.coordinator.data.sensors[self.entity_description.key]
        return self.entity_description.value_fn(value)
