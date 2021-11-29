"""Support for P1 Monitor sensors."""
from __future__ import annotations

from typing import Literal

from homeassistant.components.sensor import (
    DOMAIN as SENSOR_DOMAIN,
    STATE_CLASS_MEASUREMENT,
    STATE_CLASS_TOTAL_INCREASING,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CURRENCY_EURO,
    DEVICE_CLASS_CURRENT,
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_GAS,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_VOLTAGE,
    ELECTRIC_CURRENT_AMPERE,
    ELECTRIC_POTENTIAL_VOLT,
    ENERGY_KILO_WATT_HOUR,
    POWER_WATT,
    VOLUME_CUBIC_METERS,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import P1MonitorDataUpdateCoordinator
from .const import (
    DOMAIN,
    SERVICE_PHASES,
    SERVICE_SETTINGS,
    SERVICE_SMARTMETER,
    SERVICES,
)

SENSORS: dict[
    Literal["smartmeter", "phases", "settings"], tuple[SensorEntityDescription, ...]
] = {
    SERVICE_SMARTMETER: (
        SensorEntityDescription(
            key="gas_consumption",
            name="Gas Consumption",
            entity_registry_enabled_default=False,
            native_unit_of_measurement=VOLUME_CUBIC_METERS,
            device_class=DEVICE_CLASS_GAS,
            state_class=STATE_CLASS_TOTAL_INCREASING,
        ),
        SensorEntityDescription(
            key="power_consumption",
            name="Power Consumption",
            native_unit_of_measurement=POWER_WATT,
            device_class=DEVICE_CLASS_POWER,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        SensorEntityDescription(
            key="energy_consumption_high",
            name="Energy Consumption - High Tariff",
            native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
            device_class=DEVICE_CLASS_ENERGY,
            state_class=STATE_CLASS_TOTAL_INCREASING,
        ),
        SensorEntityDescription(
            key="energy_consumption_low",
            name="Energy Consumption - Low Tariff",
            native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
            device_class=DEVICE_CLASS_ENERGY,
            state_class=STATE_CLASS_TOTAL_INCREASING,
        ),
        SensorEntityDescription(
            key="power_production",
            name="Power Production",
            native_unit_of_measurement=POWER_WATT,
            device_class=DEVICE_CLASS_POWER,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        SensorEntityDescription(
            key="energy_production_high",
            name="Energy Production - High Tariff",
            native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
            device_class=DEVICE_CLASS_ENERGY,
            state_class=STATE_CLASS_TOTAL_INCREASING,
        ),
        SensorEntityDescription(
            key="energy_production_low",
            name="Energy Production - Low Tariff",
            native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
            device_class=DEVICE_CLASS_ENERGY,
            state_class=STATE_CLASS_TOTAL_INCREASING,
        ),
        SensorEntityDescription(
            key="energy_tariff_period",
            name="Energy Tariff Period",
            icon="mdi:calendar-clock",
        ),
    ),
    SERVICE_PHASES: (
        SensorEntityDescription(
            key="voltage_phase_l1",
            name="Voltage Phase L1",
            native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
            device_class=DEVICE_CLASS_VOLTAGE,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        SensorEntityDescription(
            key="voltage_phase_l2",
            name="Voltage Phase L2",
            native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
            device_class=DEVICE_CLASS_VOLTAGE,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        SensorEntityDescription(
            key="voltage_phase_l3",
            name="Voltage Phase L3",
            native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
            device_class=DEVICE_CLASS_VOLTAGE,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        SensorEntityDescription(
            key="current_phase_l1",
            name="Current Phase L1",
            native_unit_of_measurement=ELECTRIC_CURRENT_AMPERE,
            device_class=DEVICE_CLASS_CURRENT,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        SensorEntityDescription(
            key="current_phase_l2",
            name="Current Phase L2",
            native_unit_of_measurement=ELECTRIC_CURRENT_AMPERE,
            device_class=DEVICE_CLASS_CURRENT,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        SensorEntityDescription(
            key="current_phase_l3",
            name="Current Phase L3",
            native_unit_of_measurement=ELECTRIC_CURRENT_AMPERE,
            device_class=DEVICE_CLASS_CURRENT,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        SensorEntityDescription(
            key="power_consumed_phase_l1",
            name="Power Consumed Phase L1",
            native_unit_of_measurement=POWER_WATT,
            device_class=DEVICE_CLASS_POWER,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        SensorEntityDescription(
            key="power_consumed_phase_l2",
            name="Power Consumed Phase L2",
            native_unit_of_measurement=POWER_WATT,
            device_class=DEVICE_CLASS_POWER,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        SensorEntityDescription(
            key="power_consumed_phase_l3",
            name="Power Consumed Phase L3",
            native_unit_of_measurement=POWER_WATT,
            device_class=DEVICE_CLASS_POWER,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        SensorEntityDescription(
            key="power_produced_phase_l1",
            name="Power Produced Phase L1",
            native_unit_of_measurement=POWER_WATT,
            device_class=DEVICE_CLASS_POWER,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        SensorEntityDescription(
            key="power_produced_phase_l2",
            name="Power Produced Phase L2",
            native_unit_of_measurement=POWER_WATT,
            device_class=DEVICE_CLASS_POWER,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        SensorEntityDescription(
            key="power_produced_phase_l3",
            name="Power Produced Phase L3",
            native_unit_of_measurement=POWER_WATT,
            device_class=DEVICE_CLASS_POWER,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
    ),
    SERVICE_SETTINGS: (
        SensorEntityDescription(
            key="gas_consumption_price",
            name="Gas Consumption Price",
            entity_registry_enabled_default=False,
            state_class=STATE_CLASS_MEASUREMENT,
            native_unit_of_measurement=f"{CURRENCY_EURO}/{VOLUME_CUBIC_METERS}",
        ),
        SensorEntityDescription(
            key="energy_consumption_price_low",
            name="Energy Consumption Price - Low",
            state_class=STATE_CLASS_MEASUREMENT,
            native_unit_of_measurement=f"{CURRENCY_EURO}/{ENERGY_KILO_WATT_HOUR}",
        ),
        SensorEntityDescription(
            key="energy_consumption_price_high",
            name="Energy Consumption Price - High",
            state_class=STATE_CLASS_MEASUREMENT,
            native_unit_of_measurement=f"{CURRENCY_EURO}/{ENERGY_KILO_WATT_HOUR}",
        ),
        SensorEntityDescription(
            key="energy_production_price_low",
            name="Energy Production Price - Low",
            state_class=STATE_CLASS_MEASUREMENT,
            native_unit_of_measurement=f"{CURRENCY_EURO}/{ENERGY_KILO_WATT_HOUR}",
        ),
        SensorEntityDescription(
            key="energy_production_price_high",
            name="Energy Production Price - High",
            state_class=STATE_CLASS_MEASUREMENT,
            native_unit_of_measurement=f"{CURRENCY_EURO}/{ENERGY_KILO_WATT_HOUR}",
        ),
    ),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up P1 Monitor Sensors based on a config entry."""
    async_add_entities(
        P1MonitorSensorEntity(
            coordinator=hass.data[DOMAIN][entry.entry_id],
            description=description,
            service_key=service_key,
            name=entry.title,
            service=SERVICES[service_key],
        )
        for service_key, service_sensors in SENSORS.items()
        for description in service_sensors
    )


class P1MonitorSensorEntity(CoordinatorEntity, SensorEntity):
    """Defines an P1 Monitor sensor."""

    coordinator: P1MonitorDataUpdateCoordinator

    def __init__(
        self,
        *,
        coordinator: P1MonitorDataUpdateCoordinator,
        description: SensorEntityDescription,
        service_key: Literal["smartmeter", "phases", "settings"],
        name: str,
        service: str,
    ) -> None:
        """Initialize P1 Monitor sensor."""
        super().__init__(coordinator=coordinator)
        self._service_key = service_key

        self.entity_id = f"{SENSOR_DOMAIN}.{name}_{description.key}"
        self.entity_description = description
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}_{service_key}_{description.key}"
        )

        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={
                (DOMAIN, f"{coordinator.config_entry.entry_id}_{service_key}")
            },
            manufacturer="P1 Monitor",
            name=service,
        )

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        value = getattr(
            self.coordinator.data[self._service_key], self.entity_description.key
        )
        if isinstance(value, str):
            return value.lower()
        return value
