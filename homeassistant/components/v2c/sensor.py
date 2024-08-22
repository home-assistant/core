"""Support for V2C EVSE sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging

from pytrydan import TrydanData
from pytrydan.models.trydan import SlaveCommunicationState

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    EntityCategory,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import V2CConfigEntry
from .coordinator import V2CUpdateCoordinator
from .entity import V2CBaseEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class V2CSensorEntityDescription(SensorEntityDescription):
    """Describes an EVSE Power sensor entity."""

    value_fn: Callable[[TrydanData], StateType]


def get_meter_value(value: SlaveCommunicationState) -> str:
    """Return the value of the enum and replace slave by meter."""
    return value.name.lower().replace("slave", "meter")


_METER_ERROR_OPTIONS = [get_meter_value(error) for error in SlaveCommunicationState]

TRYDAN_SENSORS = (
    V2CSensorEntityDescription(
        key="charge_power",
        translation_key="charge_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        value_fn=lambda evse_data: evse_data.charge_power,
    ),
    V2CSensorEntityDescription(
        key="voltage_installation",
        translation_key="voltage_installation",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLTAGE,
        value_fn=lambda evse_data: evse_data.voltage_installation,
        entity_registry_enabled_default=False,
    ),
    V2CSensorEntityDescription(
        key="charge_energy",
        translation_key="charge_energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
        value_fn=lambda evse_data: evse_data.charge_energy,
    ),
    V2CSensorEntityDescription(
        key="charge_time",
        translation_key="charge_time",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.DURATION,
        value_fn=lambda evse_data: evse_data.charge_time,
    ),
    V2CSensorEntityDescription(
        key="house_power",
        translation_key="house_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        value_fn=lambda evse_data: evse_data.house_power,
    ),
    V2CSensorEntityDescription(
        key="fv_power",
        translation_key="fv_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        value_fn=lambda evse_data: evse_data.fv_power,
    ),
    V2CSensorEntityDescription(
        key="meter_error",
        translation_key="meter_error",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda evse_data: get_meter_value(evse_data.slave_error),
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.ENUM,
        options=_METER_ERROR_OPTIONS,
    ),
    V2CSensorEntityDescription(
        key="battery_power",
        translation_key="battery_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        value_fn=lambda evse_data: evse_data.battery_power,
        entity_registry_enabled_default=False,
    ),
    V2CSensorEntityDescription(
        key="ssid",
        translation_key="ssid",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda evse_data: evse_data.SSID,
        entity_registry_enabled_default=False,
    ),
    V2CSensorEntityDescription(
        key="ip_address",
        translation_key="ip_address",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda evse_data: evse_data.IP,
        entity_registry_enabled_default=False,
    ),
    V2CSensorEntityDescription(
        key="signal_status",
        translation_key="signal_status",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda evse_data: evse_data.signal_status,
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: V2CConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up V2C sensor platform."""
    coordinator = config_entry.runtime_data

    async_add_entities(
        V2CSensorBaseEntity(coordinator, description, config_entry.entry_id)
        for description in TRYDAN_SENSORS
    )


class V2CSensorBaseEntity(V2CBaseEntity, SensorEntity):
    """Defines a base v2c sensor entity."""

    entity_description: V2CSensorEntityDescription

    def __init__(
        self,
        coordinator: V2CUpdateCoordinator,
        description: SensorEntityDescription,
        entry_id: str,
    ) -> None:
        """Initialize V2C Power entity."""
        super().__init__(coordinator, description)
        self._attr_unique_id = f"{entry_id}_{description.key}"

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.data)
