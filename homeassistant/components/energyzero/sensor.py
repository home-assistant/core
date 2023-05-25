"""Support for EnergyZero sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from homeassistant.components.sensor import (
    DOMAIN as SENSOR_DOMAIN,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CURRENCY_EURO, PERCENTAGE, UnitOfEnergy, UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, SERVICE_TYPE_DEVICE_NAMES
from .coordinator import EnergyZeroData, EnergyZeroDataUpdateCoordinator


@dataclass
class EnergyZeroSensorEntityDescriptionMixin:
    """Mixin for required keys."""

    value_fn: Callable[[EnergyZeroData], float | datetime | None]
    service_type: str


@dataclass
class EnergyZeroSensorEntityDescription(
    SensorEntityDescription, EnergyZeroSensorEntityDescriptionMixin
):
    """Describes a EnergyZero sensor entity."""


SENSORS: tuple[EnergyZeroSensorEntityDescription, ...] = (
    EnergyZeroSensorEntityDescription(
        key="current_hour_price",
        name="Current hour",
        service_type="today_gas",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=f"{CURRENCY_EURO}/{UnitOfVolume.CUBIC_METERS}",
        value_fn=lambda data: data.gas.current_price if data.gas else None,
    ),
    EnergyZeroSensorEntityDescription(
        key="next_hour_price",
        name="Next hour",
        service_type="today_gas",
        native_unit_of_measurement=f"{CURRENCY_EURO}/{UnitOfVolume.CUBIC_METERS}",
        value_fn=lambda data: data.gas.price_at_time(
            data.gas.utcnow() + timedelta(hours=1)
        )
        if data.gas
        else None,
    ),
    EnergyZeroSensorEntityDescription(
        key="current_hour_price",
        name="Current hour",
        service_type="today_energy",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=f"{CURRENCY_EURO}/{UnitOfEnergy.KILO_WATT_HOUR}",
        value_fn=lambda data: data.energy_today.current_price,
    ),
    EnergyZeroSensorEntityDescription(
        key="next_hour_price",
        name="Next hour",
        service_type="today_energy",
        native_unit_of_measurement=f"{CURRENCY_EURO}/{UnitOfEnergy.KILO_WATT_HOUR}",
        value_fn=lambda data: data.energy_today.price_at_time(
            data.energy_today.utcnow() + timedelta(hours=1)
        ),
    ),
    EnergyZeroSensorEntityDescription(
        key="average_price",
        name="Average - today",
        service_type="today_energy",
        native_unit_of_measurement=f"{CURRENCY_EURO}/{UnitOfEnergy.KILO_WATT_HOUR}",
        value_fn=lambda data: data.energy_today.average_price,
    ),
    EnergyZeroSensorEntityDescription(
        key="max_price",
        name="Highest price - today",
        service_type="today_energy",
        native_unit_of_measurement=f"{CURRENCY_EURO}/{UnitOfEnergy.KILO_WATT_HOUR}",
        value_fn=lambda data: data.energy_today.extreme_prices[1],
    ),
    EnergyZeroSensorEntityDescription(
        key="min_price",
        name="Lowest price - today",
        service_type="today_energy",
        native_unit_of_measurement=f"{CURRENCY_EURO}/{UnitOfEnergy.KILO_WATT_HOUR}",
        value_fn=lambda data: data.energy_today.extreme_prices[0],
    ),
    EnergyZeroSensorEntityDescription(
        key="highest_price_time",
        name="Time of highest price - today",
        service_type="today_energy",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: data.energy_today.highest_price_time,
    ),
    EnergyZeroSensorEntityDescription(
        key="lowest_price_time",
        name="Time of lowest price - today",
        service_type="today_energy",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: data.energy_today.lowest_price_time,
    ),
    EnergyZeroSensorEntityDescription(
        key="percentage_of_max",
        name="Current percentage of highest price - today",
        service_type="today_energy",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:percent",
        value_fn=lambda data: data.energy_today.pct_of_max_price,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up EnergyZero Sensors based on a config entry."""
    coordinator: EnergyZeroDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        EnergyZeroSensorEntity(
            coordinator=coordinator,
            description=description,
        )
        for description in SENSORS
    )


class EnergyZeroSensorEntity(
    CoordinatorEntity[EnergyZeroDataUpdateCoordinator], SensorEntity
):
    """Defines a EnergyZero sensor."""

    _attr_has_entity_name = True
    _attr_attribution = "Data provided by EnergyZero"
    entity_description: EnergyZeroSensorEntityDescription

    def __init__(
        self,
        *,
        coordinator: EnergyZeroDataUpdateCoordinator,
        description: EnergyZeroSensorEntityDescription,
    ) -> None:
        """Initialize EnergyZero sensor."""
        super().__init__(coordinator=coordinator)
        self.entity_description = description
        self.entity_id = (
            f"{SENSOR_DOMAIN}.{DOMAIN}_{description.service_type}_{description.key}"
        )
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{description.service_type}_{description.key}"
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={
                (
                    DOMAIN,
                    f"{coordinator.config_entry.entry_id}_{description.service_type}",
                )
            },
            manufacturer="EnergyZero",
            name=SERVICE_TYPE_DEVICE_NAMES[self.entity_description.service_type],
        )

    @property
    def native_value(self) -> float | datetime | None:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, None | dict[datetime, float]]:
        """Return the state attributes."""
        data = self.coordinator.data

        return {
            "energy": data.energy.prices,
            "energy_template": self.coordinator.energy_modifyer.template,
            "gas": data.gas.prices if data.gas is not None else None,
            "gas_template": self.coordinator.gas_modifyer.template,
        }
