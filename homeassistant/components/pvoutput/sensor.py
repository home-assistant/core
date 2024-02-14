"""Support for getting collected information from PVOutput."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from pvo import Status, System

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_SYSTEM_ID, DOMAIN
from .coordinator import PVOutputDataUpdateCoordinator


@dataclass(frozen=True, kw_only=True)
class PVOutputSensorEntityDescription(SensorEntityDescription):
    """Describes a PVOutput sensor entity."""

    value_fn: Callable[[Status], int | float | None]


SENSORS: tuple[PVOutputSensorEntityDescription, ...] = (
    PVOutputSensorEntityDescription(
        key="energy_consumption",
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
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda status: status.temperature,
    ),
    PVOutputSensorEntityDescription(
        key="voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda status: status.voltage,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a PVOutput sensors based on a config entry."""
    coordinator: PVOutputDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    system = await coordinator.pvoutput.system()

    async_add_entities(
        PVOutputSensorEntity(
            coordinator=coordinator,
            description=description,
            system_id=entry.data[CONF_SYSTEM_ID],
            system=system,
        )
        for description in SENSORS
    )


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
        system_id: str,
        system: System,
    ) -> None:
        """Initialize a PVOutput sensor."""
        super().__init__(coordinator=coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{system_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            configuration_url=f"https://pvoutput.org/list.jsp?sid={system_id}",
            identifiers={(DOMAIN, str(system_id))},
            manufacturer="PVOutput",
            model=system.inverter_brand,
            name=system.system_name,
        )

    @property
    def native_value(self) -> int | float | None:
        """Return the state of the device."""
        return self.entity_description.value_fn(self.coordinator.data)
