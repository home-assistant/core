"""Support for easyEnergy sensors."""
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
from homeassistant.const import (
    CURRENCY_EURO,
    PERCENTAGE,
    UnitOfEnergy,
    UnitOfTime,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, SERVICE_TYPE_DEVICE_NAMES
from .coordinator import EasyEnergyData, EasyEnergyDataUpdateCoordinator


@dataclass
class EasyEnergySensorEntityDescriptionMixin:
    """Mixin for required keys."""

    value_fn: Callable[[EasyEnergyData], float | datetime | None]
    service_type: str


@dataclass
class EasyEnergySensorEntityDescription(
    SensorEntityDescription, EasyEnergySensorEntityDescriptionMixin
):
    """Describes easyEnergy sensor entity."""


SENSORS: tuple[EasyEnergySensorEntityDescription, ...] = (
    EasyEnergySensorEntityDescription(
        key="current_hour_price",
        name="Current hour",
        service_type="today_gas",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=f"{CURRENCY_EURO}/{UnitOfVolume.CUBIC_METERS}",
        value_fn=lambda data: data.gas_today.current_price if data.gas_today else None,
    ),
    EasyEnergySensorEntityDescription(
        key="next_hour_price",
        name="Next hour",
        service_type="today_gas",
        native_unit_of_measurement=f"{CURRENCY_EURO}/{UnitOfVolume.CUBIC_METERS}",
        value_fn=lambda data: get_gas_price(data, 1),
    ),
    EasyEnergySensorEntityDescription(
        key="current_hour_price",
        name="Current hour",
        service_type="today_energy_usage",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=f"{CURRENCY_EURO}/{UnitOfEnergy.KILO_WATT_HOUR}",
        value_fn=lambda data: data.energy_today.current_usage_price,
    ),
    EasyEnergySensorEntityDescription(
        key="next_hour_price",
        name="Next hour",
        service_type="today_energy_usage",
        native_unit_of_measurement=f"{CURRENCY_EURO}/{UnitOfEnergy.KILO_WATT_HOUR}",
        value_fn=lambda data: data.energy_today.price_at_time(
            data.energy_today.utcnow() + timedelta(hours=1)
        ),
    ),
    EasyEnergySensorEntityDescription(
        key="average_price",
        name="Average - today",
        service_type="today_energy_usage",
        native_unit_of_measurement=f"{CURRENCY_EURO}/{UnitOfEnergy.KILO_WATT_HOUR}",
        value_fn=lambda data: data.energy_today.average_usage_price,
    ),
    EasyEnergySensorEntityDescription(
        key="max_price",
        name="Highest price - today",
        service_type="today_energy_usage",
        native_unit_of_measurement=f"{CURRENCY_EURO}/{UnitOfEnergy.KILO_WATT_HOUR}",
        value_fn=lambda data: data.energy_today.extreme_usage_prices[1],
    ),
    EasyEnergySensorEntityDescription(
        key="min_price",
        name="Lowest price - today",
        service_type="today_energy_usage",
        native_unit_of_measurement=f"{CURRENCY_EURO}/{UnitOfEnergy.KILO_WATT_HOUR}",
        value_fn=lambda data: data.energy_today.extreme_usage_prices[0],
    ),
    EasyEnergySensorEntityDescription(
        key="highest_price_time",
        name="Time of highest price - today",
        service_type="today_energy_usage",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: data.energy_today.highest_usage_price_time,
    ),
    EasyEnergySensorEntityDescription(
        key="lowest_price_time",
        name="Time of lowest price - today",
        service_type="today_energy_usage",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: data.energy_today.lowest_usage_price_time,
    ),
    EasyEnergySensorEntityDescription(
        key="percentage_of_max",
        name="Current percentage of highest price - today",
        service_type="today_energy_usage",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:percent",
        value_fn=lambda data: data.energy_today.pct_of_max_usage,
    ),
    EasyEnergySensorEntityDescription(
        key="current_hour_price",
        name="Current hour",
        service_type="today_energy_return",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=f"{CURRENCY_EURO}/{UnitOfEnergy.KILO_WATT_HOUR}",
        value_fn=lambda data: data.energy_today.current_return_price,
    ),
    EasyEnergySensorEntityDescription(
        key="next_hour_price",
        name="Next hour",
        service_type="today_energy_return",
        native_unit_of_measurement=f"{CURRENCY_EURO}/{UnitOfEnergy.KILO_WATT_HOUR}",
        value_fn=lambda data: data.energy_today.price_at_time(
            data.energy_today.utcnow() + timedelta(hours=1), "return"
        ),
    ),
    EasyEnergySensorEntityDescription(
        key="average_price",
        name="Average - today",
        service_type="today_energy_return",
        native_unit_of_measurement=f"{CURRENCY_EURO}/{UnitOfEnergy.KILO_WATT_HOUR}",
        value_fn=lambda data: data.energy_today.average_return_price,
    ),
    EasyEnergySensorEntityDescription(
        key="max_price",
        name="Highest price - today",
        service_type="today_energy_return",
        native_unit_of_measurement=f"{CURRENCY_EURO}/{UnitOfEnergy.KILO_WATT_HOUR}",
        value_fn=lambda data: data.energy_today.extreme_return_prices[1],
    ),
    EasyEnergySensorEntityDescription(
        key="min_price",
        name="Lowest price - today",
        service_type="today_energy_return",
        native_unit_of_measurement=f"{CURRENCY_EURO}/{UnitOfEnergy.KILO_WATT_HOUR}",
        value_fn=lambda data: data.energy_today.extreme_return_prices[0],
    ),
    EasyEnergySensorEntityDescription(
        key="highest_price_time",
        name="Time of highest price - today",
        service_type="today_energy_return",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: data.energy_today.highest_return_price_time,
    ),
    EasyEnergySensorEntityDescription(
        key="lowest_price_time",
        name="Time of lowest price - today",
        service_type="today_energy_return",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: data.energy_today.lowest_return_price_time,
    ),
    EasyEnergySensorEntityDescription(
        key="percentage_of_max",
        name="Current percentage of highest price - today",
        service_type="today_energy_return",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:percent",
        value_fn=lambda data: data.energy_today.pct_of_max_return,
    ),
    EasyEnergySensorEntityDescription(
        key="hours_priced_equal_or_lower",
        name="Hours priced equal or lower than current - today",
        service_type="today_energy_usage",
        native_unit_of_measurement=UnitOfTime.HOURS,
        icon="mdi:clock",
        value_fn=lambda data: data.energy_today.hours_priced_equal_or_lower_usage,
    ),
    EasyEnergySensorEntityDescription(
        key="hours_priced_equal_or_higher",
        name="Hours priced equal or higher than current - today",
        service_type="today_energy_return",
        native_unit_of_measurement=UnitOfTime.HOURS,
        icon="mdi:clock",
        value_fn=lambda data: data.energy_today.hours_priced_equal_or_higher_return,
    ),
)


def get_gas_price(data: EasyEnergyData, hours: int) -> float | None:
    """Return the gas value.

    Args:
        data: The data object.
        hours: The number of hours to add to the current time.

    Returns:
        The gas market price value.
    """
    if data.gas_today is None:
        return None
    return data.gas_today.price_at_time(
        data.gas_today.utcnow() + timedelta(hours=hours)
    )


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up easyEnergy sensors based on a config entry."""
    coordinator: EasyEnergyDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        EasyEnergySensorEntity(coordinator=coordinator, description=description)
        for description in SENSORS
    )


class EasyEnergySensorEntity(
    CoordinatorEntity[EasyEnergyDataUpdateCoordinator], SensorEntity
):
    """Defines a easyEnergy sensor."""

    _attr_has_entity_name = True
    _attr_attribution = "Data provided by easyEnergy"
    entity_description: EasyEnergySensorEntityDescription

    def __init__(
        self,
        *,
        coordinator: EasyEnergyDataUpdateCoordinator,
        description: EasyEnergySensorEntityDescription,
    ) -> None:
        """Initialize easyEnergy sensor."""
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
            configuration_url="https://www.easyenergy.com",
            manufacturer="easyEnergy",
            name=SERVICE_TYPE_DEVICE_NAMES[self.entity_description.service_type],
        )

    @property
    def native_value(self) -> float | datetime | None:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
