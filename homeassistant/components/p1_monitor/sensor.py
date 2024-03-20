"""Support for P1 Monitor sensors."""

from __future__ import annotations

from typing import Literal

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CURRENCY_EURO,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
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
        translation_key="gas_consumption",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        device_class=SensorDeviceClass.GAS,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="power_consumption",
        translation_key="power_consumption",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="energy_consumption_high",
        translation_key="energy_consumption_high",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="energy_consumption_low",
        translation_key="energy_consumption_low",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="power_production",
        translation_key="power_production",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="energy_production_high",
        translation_key="energy_production_high",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="energy_production_low",
        translation_key="energy_production_low",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="energy_tariff_period",
        translation_key="energy_tariff_period",
    ),
)

SENSORS_PHASES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="voltage_phase_l1",
        translation_key="voltage_phase_l1",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="voltage_phase_l2",
        translation_key="voltage_phase_l2",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="voltage_phase_l3",
        translation_key="voltage_phase_l3",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="current_phase_l1",
        translation_key="current_phase_l1",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="current_phase_l2",
        translation_key="current_phase_l2",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="current_phase_l3",
        translation_key="current_phase_l3",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="power_consumed_phase_l1",
        translation_key="power_consumed_phase_l1",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="power_consumed_phase_l2",
        translation_key="power_consumed_phase_l2",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="power_consumed_phase_l3",
        translation_key="power_consumed_phase_l3",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="power_produced_phase_l1",
        translation_key="power_produced_phase_l1",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="power_produced_phase_l2",
        translation_key="power_produced_phase_l2",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="power_produced_phase_l3",
        translation_key="power_produced_phase_l3",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)

SENSORS_SETTINGS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="gas_consumption_price",
        translation_key="gas_consumption_price",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=f"{CURRENCY_EURO}/{UnitOfVolume.CUBIC_METERS}",
    ),
    SensorEntityDescription(
        key="energy_consumption_price_low",
        translation_key="energy_consumption_price_low",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=f"{CURRENCY_EURO}/{UnitOfEnergy.KILO_WATT_HOUR}",
    ),
    SensorEntityDescription(
        key="energy_consumption_price_high",
        translation_key="energy_consumption_price_high",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=f"{CURRENCY_EURO}/{UnitOfEnergy.KILO_WATT_HOUR}",
    ),
    SensorEntityDescription(
        key="energy_production_price_low",
        translation_key="energy_production_price_low",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=f"{CURRENCY_EURO}/{UnitOfEnergy.KILO_WATT_HOUR}",
    ),
    SensorEntityDescription(
        key="energy_production_price_high",
        translation_key="energy_production_price_high",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=f"{CURRENCY_EURO}/{UnitOfEnergy.KILO_WATT_HOUR}",
    ),
)

SENSORS_WATERMETER: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="consumption_day",
        translation_key="consumption_day",
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfVolume.LITERS,
        device_class=SensorDeviceClass.WATER,
    ),
    SensorEntityDescription(
        key="consumption_total",
        translation_key="consumption_total",
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        device_class=SensorDeviceClass.WATER,
    ),
    SensorEntityDescription(
        key="pulse_count",
        translation_key="pulse_count",
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
            service=SERVICE_SMARTMETER,
        )
        for description in SENSORS_SMARTMETER
    )
    entities.extend(
        P1MonitorSensorEntity(
            coordinator=coordinator,
            description=description,
            name="Phases",
            service=SERVICE_PHASES,
        )
        for description in SENSORS_PHASES
    )
    entities.extend(
        P1MonitorSensorEntity(
            coordinator=coordinator,
            description=description,
            name="Settings",
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
                service=SERVICE_WATERMETER,
            )
            for description in SENSORS_WATERMETER
        )
    async_add_entities(entities)


class P1MonitorSensorEntity(
    CoordinatorEntity[P1MonitorDataUpdateCoordinator], SensorEntity
):
    """Defines an P1 Monitor sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        *,
        coordinator: P1MonitorDataUpdateCoordinator,
        description: SensorEntityDescription,
        name: str,
        service: Literal["smartmeter", "watermeter", "phases", "settings"],
    ) -> None:
        """Initialize P1 Monitor sensor."""
        super().__init__(coordinator=coordinator)
        self._service_key = service

        self.entity_description = description
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}_{service}_{description.key}"
        )

        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, f"{coordinator.config_entry.entry_id}_{service}")},
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
        return value  # type: ignore[no-any-return]
