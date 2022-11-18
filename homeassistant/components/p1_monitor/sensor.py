"""Support for P1 Monitor sensors."""
from __future__ import annotations

from typing import Literal

from homeassistant.components.sensor import (
    DOMAIN as SENSOR_DOMAIN,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CURRENCY_EURO,
    ELECTRIC_CURRENT_AMPERE,
    ELECTRIC_POTENTIAL_VOLT,
    ENERGY_KILO_WATT_HOUR,
    POWER_WATT,
    VOLUME_CUBIC_METERS,
    VOLUME_LITERS,
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
    SERVICE_WATERMETER,
)

SENSORS_SMARTMETER: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="gas_consumption",
        name="Gas Consumption",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=VOLUME_CUBIC_METERS,
        device_class=SensorDeviceClass.GAS,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="power_consumption",
        name="Power Consumption",
        native_unit_of_measurement=POWER_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="energy_consumption_high",
        name="Energy Consumption - High Tariff",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="energy_consumption_low",
        name="Energy Consumption - Low Tariff",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="power_production",
        name="Power Production",
        native_unit_of_measurement=POWER_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="energy_production_high",
        name="Energy Production - High Tariff",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="energy_production_low",
        name="Energy Production - Low Tariff",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="energy_tariff_period",
        name="Energy Tariff Period",
        icon="mdi:calendar-clock",
    ),
)

SENSORS_PHASES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="voltage_phase_l1",
        name="Voltage Phase L1",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="voltage_phase_l2",
        name="Voltage Phase L2",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="voltage_phase_l3",
        name="Voltage Phase L3",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="current_phase_l1",
        name="Current Phase L1",
        native_unit_of_measurement=ELECTRIC_CURRENT_AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="current_phase_l2",
        name="Current Phase L2",
        native_unit_of_measurement=ELECTRIC_CURRENT_AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="current_phase_l3",
        name="Current Phase L3",
        native_unit_of_measurement=ELECTRIC_CURRENT_AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="power_consumed_phase_l1",
        name="Power Consumed Phase L1",
        native_unit_of_measurement=POWER_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="power_consumed_phase_l2",
        name="Power Consumed Phase L2",
        native_unit_of_measurement=POWER_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="power_consumed_phase_l3",
        name="Power Consumed Phase L3",
        native_unit_of_measurement=POWER_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="power_produced_phase_l1",
        name="Power Produced Phase L1",
        native_unit_of_measurement=POWER_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="power_produced_phase_l2",
        name="Power Produced Phase L2",
        native_unit_of_measurement=POWER_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="power_produced_phase_l3",
        name="Power Produced Phase L3",
        native_unit_of_measurement=POWER_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)

SENSORS_SETTINGS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="gas_consumption_price",
        name="Gas Consumption Price",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=f"{CURRENCY_EURO}/{VOLUME_CUBIC_METERS}",
    ),
    SensorEntityDescription(
        key="energy_consumption_price_low",
        name="Energy Consumption Price - Low",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=f"{CURRENCY_EURO}/{ENERGY_KILO_WATT_HOUR}",
    ),
    SensorEntityDescription(
        key="energy_consumption_price_high",
        name="Energy Consumption Price - High",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=f"{CURRENCY_EURO}/{ENERGY_KILO_WATT_HOUR}",
    ),
    SensorEntityDescription(
        key="energy_production_price_low",
        name="Energy Production Price - Low",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=f"{CURRENCY_EURO}/{ENERGY_KILO_WATT_HOUR}",
    ),
    SensorEntityDescription(
        key="energy_production_price_high",
        name="Energy Production Price - High",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=f"{CURRENCY_EURO}/{ENERGY_KILO_WATT_HOUR}",
    ),
)

SENSORS_WATERMETER: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="consumption_day",
        name="Consumption Day",
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=VOLUME_LITERS,
        device_class=SensorDeviceClass.WATER,
    ),
    SensorEntityDescription(
        key="consumption_total",
        name="Consumption Total",
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=VOLUME_CUBIC_METERS,
        device_class=SensorDeviceClass.WATER,
    ),
    SensorEntityDescription(
        key="pulse_count",
        name="Pulse Count",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up P1 Monitor Sensors based on a config entry."""
    coordinator: P1MonitorDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[P1MonitorSensorEntity] = []
    entities.extend(
        P1MonitorSensorEntity(
            coordinator=coordinator,
            description=description,
            name="SmartMeter",
            service_key="smartmeter",
            service=SERVICE_SMARTMETER,
        )
        for description in SENSORS_SMARTMETER
    )
    entities.extend(
        P1MonitorSensorEntity(
            coordinator=coordinator,
            description=description,
            name="Phases",
            service_key="phases",
            service=SERVICE_PHASES,
        )
        for description in SENSORS_PHASES
    )
    entities.extend(
        P1MonitorSensorEntity(
            coordinator=coordinator,
            description=description,
            name="Settings",
            service_key="settings",
            service=SERVICE_SETTINGS,
        )
        for description in SENSORS_SETTINGS
    )
    if coordinator.has_water_meter:
        entities.extend(
            P1MonitorSensorEntity(
                coordinator=coordinator,
                description=description,
                name="WaterMeter",
                service_key="watermeter",
                service=SERVICE_WATERMETER,
            )
            for description in SENSORS_WATERMETER
        )
    async_add_entities(entities)


class P1MonitorSensorEntity(
    CoordinatorEntity[P1MonitorDataUpdateCoordinator], SensorEntity
):
    """Defines an P1 Monitor sensor."""

    def __init__(
        self,
        *,
        coordinator: P1MonitorDataUpdateCoordinator,
        description: SensorEntityDescription,
        service_key: Literal["smartmeter", "watermeter", "phases", "settings"],
        name: str,
        service: str,
    ) -> None:
        """Initialize P1 Monitor sensor."""
        super().__init__(coordinator=coordinator)
        self._service_key = service_key

        self.entity_id = f"{SENSOR_DOMAIN}.{service}_{description.key}"
        self.entity_description = description
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}_{service_key}_{description.key}"
        )

        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={
                (DOMAIN, f"{coordinator.config_entry.entry_id}_{service_key}")
            },
            configuration_url=f"http://{coordinator.config_entry.data[CONF_HOST]}",
            manufacturer="P1 Monitor",
            name=name,
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
