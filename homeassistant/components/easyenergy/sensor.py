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
from homeassistant.const import (
    CURRENCY_EURO,
    PERCENTAGE,
    UnitOfEnergy,
    UnitOfTime,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, SERVICE_TYPE_DEVICE_NAMES
from .coordinator import (
    EasyEnergyConfigEntry,
    EasyEnergyData,
    EasyEnergyDataUpdateCoordinator,
)


@dataclass(frozen=True, kw_only=True)
class EasyEnergySensorEntityDescription(SensorEntityDescription):
    """Describes easyEnergy sensor entity."""

    value_fn: Callable[[EasyEnergyData], float | datetime | None]
    service_type: str


SENSORS: tuple[EasyEnergySensorEntityDescription, ...] = (
    EasyEnergySensorEntityDescription(
        key="current_hour_price",
        translation_key="current_hour_price",
        service_type="today_gas",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=f"{CURRENCY_EURO}/{UnitOfVolume.CUBIC_METERS}",
        value_fn=lambda data: data.gas_today.current_price if data.gas_today else None,
    ),
    EasyEnergySensorEntityDescription(
        key="next_hour_price",
        translation_key="next_hour_price",
        service_type="today_gas",
        native_unit_of_measurement=f"{CURRENCY_EURO}/{UnitOfVolume.CUBIC_METERS}",
        value_fn=lambda data: get_gas_price(data, 1),
    ),
    EasyEnergySensorEntityDescription(
        key="current_hour_price",
        translation_key="current_hour_price",
        service_type="today_energy_usage",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=f"{CURRENCY_EURO}/{UnitOfEnergy.KILO_WATT_HOUR}",
        value_fn=lambda data: data.energy_today.current_usage_price,
    ),
    EasyEnergySensorEntityDescription(
        key="next_hour_price",
        translation_key="next_hour_price",
        service_type="today_energy_usage",
        native_unit_of_measurement=f"{CURRENCY_EURO}/{UnitOfEnergy.KILO_WATT_HOUR}",
        value_fn=lambda data: data.energy_today.price_at_time(
            data.energy_today.utcnow() + timedelta(hours=1)
        ),
    ),
    EasyEnergySensorEntityDescription(
        key="average_price",
        translation_key="average_price",
        service_type="today_energy_usage",
        native_unit_of_measurement=f"{CURRENCY_EURO}/{UnitOfEnergy.KILO_WATT_HOUR}",
        value_fn=lambda data: data.energy_today.average_usage_price,
    ),
    EasyEnergySensorEntityDescription(
        key="max_price",
        translation_key="max_price",
        service_type="today_energy_usage",
        native_unit_of_measurement=f"{CURRENCY_EURO}/{UnitOfEnergy.KILO_WATT_HOUR}",
        value_fn=lambda data: data.energy_today.extreme_usage_prices[1],
    ),
    EasyEnergySensorEntityDescription(
        key="min_price",
        translation_key="min_price",
        service_type="today_energy_usage",
        native_unit_of_measurement=f"{CURRENCY_EURO}/{UnitOfEnergy.KILO_WATT_HOUR}",
        value_fn=lambda data: data.energy_today.extreme_usage_prices[0],
    ),
    EasyEnergySensorEntityDescription(
        key="highest_price_time",
        translation_key="highest_price_time",
        service_type="today_energy_usage",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: data.energy_today.highest_usage_price_time,
    ),
    EasyEnergySensorEntityDescription(
        key="lowest_price_time",
        translation_key="lowest_price_time",
        service_type="today_energy_usage",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: data.energy_today.lowest_usage_price_time,
    ),
    EasyEnergySensorEntityDescription(
        key="percentage_of_max",
        translation_key="percentage_of_max",
        service_type="today_energy_usage",
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda data: data.energy_today.pct_of_max_usage,
    ),
    EasyEnergySensorEntityDescription(
        key="current_hour_price",
        translation_key="current_hour_price",
        service_type="today_energy_return",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=f"{CURRENCY_EURO}/{UnitOfEnergy.KILO_WATT_HOUR}",
        value_fn=lambda data: data.energy_today.current_return_price,
    ),
    EasyEnergySensorEntityDescription(
        key="next_hour_price",
        translation_key="next_hour_price",
        service_type="today_energy_return",
        native_unit_of_measurement=f"{CURRENCY_EURO}/{UnitOfEnergy.KILO_WATT_HOUR}",
        value_fn=lambda data: data.energy_today.price_at_time(
            data.energy_today.utcnow() + timedelta(hours=1), "return"
        ),
    ),
    EasyEnergySensorEntityDescription(
        key="average_price",
        translation_key="average_price",
        service_type="today_energy_return",
        native_unit_of_measurement=f"{CURRENCY_EURO}/{UnitOfEnergy.KILO_WATT_HOUR}",
        value_fn=lambda data: data.energy_today.average_return_price,
    ),
    EasyEnergySensorEntityDescription(
        key="max_price",
        translation_key="max_price",
        service_type="today_energy_return",
        native_unit_of_measurement=f"{CURRENCY_EURO}/{UnitOfEnergy.KILO_WATT_HOUR}",
        value_fn=lambda data: data.energy_today.extreme_return_prices[1],
    ),
    EasyEnergySensorEntityDescription(
        key="min_price",
        translation_key="min_price",
        service_type="today_energy_return",
        native_unit_of_measurement=f"{CURRENCY_EURO}/{UnitOfEnergy.KILO_WATT_HOUR}",
        value_fn=lambda data: data.energy_today.extreme_return_prices[0],
    ),
    EasyEnergySensorEntityDescription(
        key="highest_price_time",
        translation_key="highest_price_time",
        service_type="today_energy_return",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: data.energy_today.highest_return_price_time,
    ),
    EasyEnergySensorEntityDescription(
        key="lowest_price_time",
        translation_key="lowest_price_time",
        service_type="today_energy_return",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: data.energy_today.lowest_return_price_time,
    ),
    EasyEnergySensorEntityDescription(
        key="percentage_of_max",
        translation_key="percentage_of_max",
        service_type="today_energy_return",
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda data: data.energy_today.pct_of_max_return,
    ),
    EasyEnergySensorEntityDescription(
        key="hours_priced_equal_or_lower",
        translation_key="hours_priced_equal_or_lower",
        service_type="today_energy_usage",
        native_unit_of_measurement=UnitOfTime.HOURS,
        value_fn=lambda data: data.energy_today.hours_priced_equal_or_lower_usage,
    ),
    EasyEnergySensorEntityDescription(
        key="hours_priced_equal_or_higher",
        translation_key="hours_priced_equal_or_higher",
        service_type="today_energy_return",
        native_unit_of_measurement=UnitOfTime.HOURS,
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
    hass: HomeAssistant,
    entry: EasyEnergyConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up easyEnergy sensors based on a config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        EasyEnergySensorEntity(coordinator=coordinator, description=description)
        for description in SENSORS
    )


class EasyEnergySensorEntity(
    CoordinatorEntity[EasyEnergyDataUpdateCoordinator], SensorEntity
):
    """Defines an easyEnergy sensor."""

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
