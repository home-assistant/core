"""Platform for sensor integration."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_MILLION,
    PERCENTAGE,
    EntityCategory,
    UnitOfElectricPotential,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import (
    OndiloIcoMeasuresCoordinator,
    OndiloIcoPoolData,
    OndiloIcoPoolsCoordinator,
)

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="orp",
        translation_key="oxydo_reduction_potential",
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="ph",
        device_class=SensorDeviceClass.PH,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="tds",
        translation_key="tds",
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="battery",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="rssi",
        translation_key="rssi",
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="salt",
        translation_key="salt",
        native_unit_of_measurement="mg/L",
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Ondilo ICO sensors."""
    pools_coordinator: OndiloIcoPoolsCoordinator = hass.data[DOMAIN][entry.entry_id]
    known_entities: set[str] = set()

    async_add_entities(get_new_entities(pools_coordinator, known_entities))

    @callback
    def add_new_entities():
        """Add any new entities after update of the pools coordinator."""
        async_add_entities(get_new_entities(pools_coordinator, known_entities))

    entry.async_on_unload(pools_coordinator.async_add_listener(add_new_entities))


@callback
def get_new_entities(
    pools_coordinator: OndiloIcoPoolsCoordinator,
    known_entities: set[str],
) -> list[OndiloICO]:
    """Return new Ondilo ICO sensor entities."""
    entities = []
    for pool_id, pool_data in pools_coordinator.data.items():
        for description in SENSOR_TYPES:
            measurement_id = f"{pool_id}-{description.key}"
            if (
                measurement_id in known_entities
                or (data := pool_data.measures_coordinator.data) is None
                or description.key not in data.sensors
            ):
                continue
            known_entities.add(measurement_id)
            entities.append(
                OndiloICO(
                    pool_data.measures_coordinator, description, pool_id, pool_data
                )
            )

    return entities


class OndiloICO(CoordinatorEntity[OndiloIcoMeasuresCoordinator], SensorEntity):
    """Representation of a Sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: OndiloIcoMeasuresCoordinator,
        description: SensorEntityDescription,
        pool_id: str,
        pool_data: OndiloIcoPoolData,
    ) -> None:
        """Initialize sensor entity with data from coordinator."""
        super().__init__(coordinator)
        self.entity_description = description
        self._pool_id = pool_id
        self._attr_unique_id = f"{pool_data.ico['serial_number']}-{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, pool_data.ico["serial_number"])},
        )

    @property
    def native_value(self) -> StateType:
        """Last value of the sensor."""
        return self.coordinator.data.sensors[self.entity_description.key]
