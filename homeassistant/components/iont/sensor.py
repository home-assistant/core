"""Support for IONT sensor entities."""

from collections.abc import Callable
from dataclasses import dataclass
from enum import IntEnum
from typing import override

from pyiont import (
    AuthorizedBy,
    ChargingState,
    ChargingStrategy,
    Connector,
    DeviceStatus,
    IontCharger,
    VehicleState,
)

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import LOGGER
from .coordinator import IontConfigEntry
from .entity import IontChargerEntity, IontConnectorEntity

PARALLEL_UPDATES = 0


def _enum_state(value: IntEnum | None) -> str | None:
    """Return an enum's option, or None while the charger reports it as unknown.

    Every enumeration the charger reports carries code 0 for "unknown", which
    is what an entity shows as unknown rather than as a state of its own.
    """
    if value is None or value == 0:
        return None
    return value.name.lower()


def _options(enum_type: type[IntEnum]) -> list[str]:
    """Return the options an enum sensor can take, leaving out "unknown"."""
    return [member.name.lower() for member in enum_type if member != 0]


@dataclass(frozen=True, kw_only=True)
class IontChargerSensorEntityDescription(SensorEntityDescription):
    """Describes an IONT sensor entity on the charger device."""

    value_fn: Callable[[IontCharger], StateType]


@dataclass(frozen=True, kw_only=True)
class IontConnectorSensorEntityDescription(SensorEntityDescription):
    """Describes an IONT sensor entity on a connector sub-device."""

    exists_fn: Callable[[Connector], bool] = lambda _: True
    value_fn: Callable[[Connector], StateType]


CHARGER_SENSORS: tuple[IontChargerSensorEntityDescription, ...] = (
    IontChargerSensorEntityDescription(
        key="available_power",
        translation_key="available_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda charger: charger.device.available_power,
    ),
    IontChargerSensorEntityDescription(
        key="status",
        translation_key="status",
        device_class=SensorDeviceClass.ENUM,
        options=_options(DeviceStatus),
        value_fn=lambda charger: _enum_state(charger.device.status),
    ),
    IontChargerSensorEntityDescription(
        key="charging_strategy",
        translation_key="charging_strategy",
        device_class=SensorDeviceClass.ENUM,
        options=_options(ChargingStrategy),
        value_fn=lambda charger: _enum_state(charger.device.charging_strategy),
    ),
    IontChargerSensorEntityDescription(
        key="power_limit_user",
        translation_key="power_limit_user",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda charger: charger.device.power_limit_user,
    ),
    IontChargerSensorEntityDescription(
        key="main_breaker_current",
        translation_key="main_breaker_current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        entity_category=EntityCategory.DIAGNOSTIC,
        # Installation constants; there for the electrician, not for the day.
        entity_registry_enabled_default=False,
        value_fn=lambda charger: charger.device.main_breaker_current,
    ),
    IontChargerSensorEntityDescription(
        key="charger_breaker_current",
        translation_key="charger_breaker_current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda charger: charger.device.charger_breaker_current,
    ),
    IontChargerSensorEntityDescription(
        key="uptime",
        translation_key="uptime",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.HOURS,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda charger: charger.device.uptime,
    ),
)

CONNECTOR_SENSORS: tuple[IontConnectorSensorEntityDescription, ...] = (
    IontConnectorSensorEntityDescription(
        key="charging_state",
        translation_key="charging_state",
        device_class=SensorDeviceClass.ENUM,
        options=_options(ChargingState),
        value_fn=lambda connector: _enum_state(connector.charging_state),
    ),
    IontConnectorSensorEntityDescription(
        key="vehicle_state",
        translation_key="vehicle_state",
        device_class=SensorDeviceClass.ENUM,
        options=_options(VehicleState),
        value_fn=lambda connector: _enum_state(connector.vehicle_state),
    ),
    IontConnectorSensorEntityDescription(
        key="authorized_by",
        translation_key="authorized_by",
        device_class=SensorDeviceClass.ENUM,
        options=_options(AuthorizedBy),
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda connector: _enum_state(connector.authorized_by),
    ),
    IontConnectorSensorEntityDescription(
        key="power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda connector: connector.power,
    ),
    IontConnectorSensorEntityDescription(
        key="session_energy",
        translation_key="session_energy",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=2,
        value_fn=lambda connector: connector.session_energy,
    ),
    IontConnectorSensorEntityDescription(
        key="last_session_energy",
        translation_key="last_session_energy",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=2,
        value_fn=lambda connector: connector.last_session_energy,
    ),
    IontConnectorSensorEntityDescription(
        key="total_energy",
        translation_key="total_energy",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=2,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda connector: connector.total_energy,
    ),
    IontConnectorSensorEntityDescription(
        key="battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        # Only a DC charger talks to the vehicle's battery; AC reports 0.
        exists_fn=lambda connector: connector.is_dc,
        value_fn=lambda connector: connector.battery_soc,
    ),
    IontConnectorSensorEntityDescription(
        key="current_l1",
        translation_key="current_l1",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=1,
        value_fn=lambda connector: connector.current_l1,
    ),
    IontConnectorSensorEntityDescription(
        key="current_l2",
        translation_key="current_l2",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=1,
        value_fn=lambda connector: connector.current_l2,
    ),
    IontConnectorSensorEntityDescription(
        key="current_l3",
        translation_key="current_l3",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=1,
        value_fn=lambda connector: connector.current_l3,
    ),
    IontConnectorSensorEntityDescription(
        key="voltage_l1",
        translation_key="voltage_l1",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        # Voltage barely moves and there is a lot of it; ask for it if you want it.
        entity_registry_enabled_default=False,
        suggested_display_precision=1,
        value_fn=lambda connector: connector.voltage_l1,
    ),
    IontConnectorSensorEntityDescription(
        key="voltage_l2",
        translation_key="voltage_l2",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        suggested_display_precision=1,
        value_fn=lambda connector: connector.voltage_l2,
    ),
    IontConnectorSensorEntityDescription(
        key="voltage_l3",
        translation_key="voltage_l3",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        suggested_display_precision=1,
        value_fn=lambda connector: connector.voltage_l3,
    ),
    IontConnectorSensorEntityDescription(
        key="frequency_l1",
        translation_key="frequency_l1",
        device_class=SensorDeviceClass.FREQUENCY,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        suggested_display_precision=2,
        value_fn=lambda connector: connector.frequency_l1,
    ),
    IontConnectorSensorEntityDescription(
        key="frequency_l2",
        translation_key="frequency_l2",
        device_class=SensorDeviceClass.FREQUENCY,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        suggested_display_precision=2,
        value_fn=lambda connector: connector.frequency_l2,
    ),
    IontConnectorSensorEntityDescription(
        key="frequency_l3",
        translation_key="frequency_l3",
        device_class=SensorDeviceClass.FREQUENCY,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        suggested_display_precision=2,
        value_fn=lambda connector: connector.frequency_l3,
    ),
    IontConnectorSensorEntityDescription(
        key="power_limit",
        translation_key="power_limit",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda connector: connector.power_limit,
    ),
    IontConnectorSensorEntityDescription(
        key="temperature_inner",
        translation_key="temperature_inner",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        # Not every connector measures it, and one that does not reports 0.
        entity_registry_enabled_default=False,
        suggested_display_precision=1,
        value_fn=lambda connector: connector.temperature_inner,
    ),
    IontConnectorSensorEntityDescription(
        key="temperature_ambient",
        translation_key="temperature_ambient",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        suggested_display_precision=1,
        value_fn=lambda connector: connector.temperature_ambient,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IontConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up IONT sensor entities based on a config entry."""
    coordinator = entry.runtime_data

    entities: list[SensorEntity] = [
        IontChargerSensorEntity(coordinator, description)
        for description in CHARGER_SENSORS
    ]
    for number, connector in enumerate(coordinator.charger.connectors, 1):
        for description in CONNECTOR_SENSORS:
            if not description.exists_fn(connector):
                continue
            if description.state_class is SensorStateClass.TOTAL_INCREASING:
                entities.append(
                    IontConnectorTotalSensorEntity(
                        coordinator, description, number=number
                    )
                )
            else:
                entities.append(
                    IontConnectorSensorEntity(coordinator, description, number=number)
                )

    async_add_entities(entities)


class IontChargerSensorEntity(IontChargerEntity, SensorEntity):
    """Defines an IONT sensor entity on the charger device."""

    entity_description: IontChargerSensorEntityDescription

    @property
    @override
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.charger)


class IontConnectorSensorEntity(IontConnectorEntity, SensorEntity):
    """Defines an IONT sensor entity on a connector sub-device."""

    entity_description: IontConnectorSensorEntityDescription

    @property
    @override
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.connector)


class IontConnectorTotalSensorEntity(IontConnectorEntity, RestoreSensor):
    """Defines an IONT lifetime energy sensor on a connector sub-device.

    A long-term statistic holds its last value while the charger is offline,
    since a gap damages the statistics and the energy dashboard, and restores
    it across a restart.
    """

    entity_description: IontConnectorSensorEntityDescription

    @property
    @override
    def available(self) -> bool:
        """Stay available: the last total is still the total."""
        return True

    @override
    async def async_added_to_hass(self) -> None:
        """Restore the last total, then take the charger's if it has one."""
        await super().async_added_to_hass()
        if (last := await self.async_get_last_sensor_data()) is not None and isinstance(
            last.native_value, (int, float)
        ):
            self._attr_native_value = last.native_value
        self._process_data()

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Take the charger's total when it answered."""
        self._process_data()
        super()._handle_coordinator_update()

    def _process_data(self) -> None:
        """Hold the last total unless the charger reports a plausible new one."""
        if self._subsystem in self.coordinator.data.failed:
            return
        value = self.entity_description.value_fn(self.connector)
        if not isinstance(value, (int, float)):
            return
        last = self._attr_native_value
        if isinstance(last, (int, float)) and last * 0.99 <= value < last:
            LOGGER.debug(
                "%s: total %s is lower than the last %s; keeping the last",
                self.entity_id,
                value,
                last,
            )
            return
        self._attr_native_value = value
