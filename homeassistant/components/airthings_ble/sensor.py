"""Support for airthings ble sensors."""
from __future__ import annotations

import logging

from airthings_ble import AirthingsDevice

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_BILLION,
    CONCENTRATION_PARTS_PER_MILLION,
    LIGHT_LUX,
    PERCENTAGE,
    EntityCategory,
    UnitOfPressure,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import (
    CONNECTION_BLUETOOTH,
    DeviceInfo,
    async_get as device_async_get,
)
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity_registry import (
    async_entries_for_device,
    async_get as entity_async_get,
)
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from homeassistant.util.unit_system import METRIC_SYSTEM

from .const import DOMAIN, VOLUME_BECQUEREL, VOLUME_PICOCURIE

_LOGGER = logging.getLogger(__name__)

SENSORS_MAPPING_TEMPLATE: dict[str, SensorEntityDescription] = {
    "radon_1day_avg": SensorEntityDescription(
        key="radon_1day_avg",
        translation_key="radon_1day_avg",
        native_unit_of_measurement=VOLUME_BECQUEREL,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:radioactive",
    ),
    "radon_longterm_avg": SensorEntityDescription(
        key="radon_longterm_avg",
        translation_key="radon_longterm_avg",
        native_unit_of_measurement=VOLUME_BECQUEREL,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:radioactive",
    ),
    "radon_1day_level": SensorEntityDescription(
        key="radon_1day_level",
        translation_key="radon_1day_level",
        icon="mdi:radioactive",
    ),
    "radon_longterm_level": SensorEntityDescription(
        key="radon_longterm_level",
        translation_key="radon_longterm_level",
        icon="mdi:radioactive",
    ),
    "temperature": SensorEntityDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "humidity": SensorEntityDescription(
        key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "pressure": SensorEntityDescription(
        key="pressure",
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=UnitOfPressure.MBAR,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "battery": SensorEntityDescription(
        key="battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "co2": SensorEntityDescription(
        key="co2",
        device_class=SensorDeviceClass.CO2,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "voc": SensorEntityDescription(
        key="voc",
        device_class=SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS_PARTS,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_BILLION,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:cloud",
    ),
    "illuminance": SensorEntityDescription(
        key="illuminance",
        device_class=SensorDeviceClass.ILLUMINANCE,
        native_unit_of_measurement=LIGHT_LUX,
        state_class=SensorStateClass.MEASUREMENT,
    ),
}


@callback
def async_migrate(hass: HomeAssistant, address: str, sensor_name: str):
    """Migrate entities to new unique ids (with BLE Address)."""

    ent_reg = entity_async_get(hass)

    device_registry = device_async_get(hass)
    entity_registry = entity_async_get(hass)

    device = device_registry.async_get_device(identifiers={(DOMAIN, address)})

    if not device:
        return

    entities = async_entries_for_device(
        entity_registry,
        device_id=device.id,
        include_disabled_entities=True,
    )

    filtered_entities = (
        entity for entity in entities if entity.unique_id.endswith(sensor_name)
    )

    unique_ids: dict[str, str] = {}

    for entity in filtered_entities:
        if entity.unique_id.startswith(address):
            unique_ids["v3"] = entity.entity_id
        elif "(" in entity.unique_id:
            unique_ids["v2"] = entity.entity_id
        else:
            unique_ids["v1"] = entity.entity_id

    def _migrate_unique_id(entity_id: str, new_unique_id: str):
        ent_reg.async_update_entity(entity_id=entity_id, new_unique_id=new_unique_id)
        _LOGGER.info("Migrated entity '%s' to unique id '%s'", entity_id, new_unique_id)

    if unique_ids.get("v3"):
        # Already has the newest unique id format
        return

    new_unique_id = f"{address}_{sensor_name}"

    # Try to migrate the pre 2023.9.0 unique id first
    if entity_id := unique_ids.get("v1"):
        _migrate_unique_id(
            entity_id=entity_id,
            new_unique_id=new_unique_id,
        )

    # If pre 2023.9.0 unique id is not found, try to migrate the unique id
    # introduced in 2023.9.0
    elif entity_id := unique_ids.get("v2"):
        _migrate_unique_id(entity_id=entity_id, new_unique_id=new_unique_id)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Airthings BLE sensors."""
    is_metric = hass.config.units is METRIC_SYSTEM

    coordinator: DataUpdateCoordinator[AirthingsDevice] = hass.data[DOMAIN][
        entry.entry_id
    ]

    # we need to change some units
    sensors_mapping = SENSORS_MAPPING_TEMPLATE.copy()
    if not is_metric:
        for val in sensors_mapping.values():
            if val.native_unit_of_measurement is not VOLUME_BECQUEREL:
                continue
            val.native_unit_of_measurement = VOLUME_PICOCURIE

    entities = []
    _LOGGER.debug("got sensors: %s", coordinator.data.sensors)
    for sensor_type, sensor_value in coordinator.data.sensors.items():
        if sensor_type not in sensors_mapping:
            _LOGGER.debug(
                "Unknown sensor type detected: %s, %s",
                sensor_type,
                sensor_value,
            )
            continue
        async_migrate(hass, coordinator.data.address, sensor_type)
        entities.append(
            AirthingsSensor(coordinator, coordinator.data, sensors_mapping[sensor_type])
        )

    async_add_entities(entities)


class AirthingsSensor(
    CoordinatorEntity[DataUpdateCoordinator[AirthingsDevice]], SensorEntity
):
    """Airthings BLE sensors for the device."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[AirthingsDevice],
        airthings_device: AirthingsDevice,
        entity_description: SensorEntityDescription,
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
                ),
            },
            identifiers={
                (
                    DOMAIN,
                    airthings_device.address,
                )
            },
            name=name,
            manufacturer=airthings_device.manufacturer,
            hw_version=airthings_device.hw_version,
            sw_version=airthings_device.sw_version,
            model=airthings_device.model,
        )

    @property
    def native_value(self) -> StateType:
        """Return the value reported by the sensor."""
        return self.coordinator.data.sensors[self.entity_description.key]
