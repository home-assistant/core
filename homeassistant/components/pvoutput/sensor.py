"""Support for getting collected information from PVOutput."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from pvo import Status

from homeassistant.components.sensor import (
    DOMAIN as SENSOR_DOMAIN,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_SYSTEM_ID, DOMAIN
from .coordinator import PvOutputConfigEntry, PVOutputDataUpdateCoordinator

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class PVOutputSensorEntityDescription(SensorEntityDescription):
    """Describes a PVOutput sensor entity."""

    value_fn: Callable[[Status], int | float | None]

    # Not every uploader sends these values, so these sensors are only
    # created once the system reports a value for them.
    optional: bool = False


SENSORS: tuple[PVOutputSensorEntityDescription, ...] = (
    PVOutputSensorEntityDescription(
        key="energy_consumption",
        optional=True,
        translation_key="energy_consumption",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda status: status.energy_consumption,
    ),
    PVOutputSensorEntityDescription(
        key="energy_generation",
        translation_key="energy_generation",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda status: status.energy_generation,
    ),
    PVOutputSensorEntityDescription(
        key="normalized_output",
        translation_key="efficiency",
        native_unit_of_measurement=(
            f"{UnitOfEnergy.KILO_WATT_HOUR}/{UnitOfPower.KILO_WATT}"
        ),
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda status: status.normalized_output,
    ),
    PVOutputSensorEntityDescription(
        key="power_consumption",
        optional=True,
        translation_key="power_consumption",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda status: status.power_consumption,
    ),
    PVOutputSensorEntityDescription(
        key="power_generation",
        translation_key="power_generation",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda status: status.power_generation,
    ),
    PVOutputSensorEntityDescription(
        key="temperature",
        optional=True,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda status: status.temperature,
    ),
    PVOutputSensorEntityDescription(
        key="voltage",
        optional=True,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda status: status.voltage,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PvOutputConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up a PVOutput sensors based on a config entry."""
    coordinator = entry.runtime_data
    entity_registry = er.async_get(hass)
    system_id = entry.data[CONF_SYSTEM_ID]
    added_keys: set[str] = set()

    def _should_add(description: PVOutputSensorEntityDescription) -> bool:
        """Return if a sensor should be added."""
        if not description.optional:
            return True

        if description.value_fn(coordinator.data) is not None:
            return True

        # Keep sensors that existed before, even if they have no value now
        return (
            entity_registry.async_get_entity_id(
                SENSOR_DOMAIN, DOMAIN, f"{system_id}_{description.key}"
            )
            is not None
        )

    @callback
    def _async_add_new_sensors() -> None:
        """Add sensors that have not been added yet, if they should be."""
        new_descriptions = [
            description
            for description in SENSORS
            if description.key not in added_keys and _should_add(description)
        ]
        if not new_descriptions:
            return

        added_keys.update(description.key for description in new_descriptions)
        async_add_entities(
            PVOutputSensorEntity(
                coordinator=coordinator,
                description=description,
                system_id=system_id,
            )
            for description in new_descriptions
        )

    _async_add_new_sensors()
    entry.async_on_unload(coordinator.async_add_listener(_async_add_new_sensors))


class PVOutputSensorEntity(
    CoordinatorEntity[PVOutputDataUpdateCoordinator], SensorEntity
):
    """Representation of a PVOutput sensor."""

    entity_description: PVOutputSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        *,
        coordinator: PVOutputDataUpdateCoordinator,
        description: PVOutputSensorEntityDescription,
        system_id: int,
    ) -> None:
        """Initialize a PVOutput sensor."""
        super().__init__(coordinator=coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{system_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            configuration_url=f"https://pvoutput.org/list.jsp?sid={system_id}",
            identifiers={(DOMAIN, str(system_id))},
            manufacturer="PVOutput",
            model=coordinator.system.inverter_brand,
            name=coordinator.system.system_name,
        )

    @property
    @override
    def native_value(self) -> int | float | None:
        """Return the state of the device."""
        return self.entity_description.value_fn(self.coordinator.data)
