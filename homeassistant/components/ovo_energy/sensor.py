"""Support for OVO Energy sensors."""

from __future__ import annotations

from collections.abc import Callable
import dataclasses
from datetime import datetime, timedelta
from typing import Final

from ovoenergy import OVOEnergy
from ovoenergy.models import OVODailyUsage

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from . import OVOEnergyDeviceEntity
from .const import DATA_CLIENT, DATA_COORDINATOR, DOMAIN

SCAN_INTERVAL = timedelta(seconds=300)
PARALLEL_UPDATES = 4

KEY_LAST_ELECTRICITY_COST: Final = "last_electricity_cost"
KEY_LAST_GAS_COST: Final = "last_gas_cost"


@dataclasses.dataclass(frozen=True)
class OVOEnergySensorEntityDescription(SensorEntityDescription):
    """Class describing System Bridge sensor entities."""

    value: Callable[[OVODailyUsage], StateType | datetime] = round


SENSOR_TYPES_ELECTRICITY: tuple[OVOEnergySensorEntityDescription, ...] = (
    OVOEnergySensorEntityDescription(
        key="last_electricity_reading",
        translation_key="last_electricity_reading",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value=lambda usage: usage.electricity[-1].consumption,
    ),
    OVOEnergySensorEntityDescription(
        key=KEY_LAST_ELECTRICITY_COST,
        translation_key=KEY_LAST_ELECTRICITY_COST,
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        value=lambda usage: usage.electricity[-1].cost.amount
        if usage.electricity[-1].cost is not None
        else None,
    ),
    OVOEnergySensorEntityDescription(
        key="last_electricity_start_time",
        translation_key="last_electricity_start_time",
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.TIMESTAMP,
        value=lambda usage: dt_util.as_utc(usage.electricity[-1].interval.start),
    ),
    OVOEnergySensorEntityDescription(
        key="last_electricity_end_time",
        translation_key="last_electricity_end_time",
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.TIMESTAMP,
        value=lambda usage: dt_util.as_utc(usage.electricity[-1].interval.end),
    ),
)

SENSOR_TYPES_GAS: tuple[OVOEnergySensorEntityDescription, ...] = (
    OVOEnergySensorEntityDescription(
        key="last_gas_reading",
        translation_key="last_gas_reading",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value=lambda usage: usage.gas[-1].consumption,
    ),
    OVOEnergySensorEntityDescription(
        key=KEY_LAST_GAS_COST,
        translation_key=KEY_LAST_GAS_COST,
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        value=lambda usage: usage.gas[-1].cost.amount
        if usage.gas[-1].cost is not None
        else None,
    ),
    OVOEnergySensorEntityDescription(
        key="last_gas_start_time",
        translation_key="last_gas_start_time",
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.TIMESTAMP,
        value=lambda usage: dt_util.as_utc(usage.gas[-1].interval.start),
    ),
    OVOEnergySensorEntityDescription(
        key="last_gas_end_time",
        translation_key="last_gas_end_time",
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.TIMESTAMP,
        value=lambda usage: dt_util.as_utc(usage.gas[-1].interval.end),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up OVO Energy sensor based on a config entry."""
    coordinator: DataUpdateCoordinator[OVODailyUsage] = hass.data[DOMAIN][
        entry.entry_id
    ][DATA_COORDINATOR]
    client: OVOEnergy = hass.data[DOMAIN][entry.entry_id][DATA_CLIENT]

    entities = []

    if coordinator.data:
        if coordinator.data.electricity:
            for description in SENSOR_TYPES_ELECTRICITY:
                if (
                    description.key == KEY_LAST_ELECTRICITY_COST
                    and coordinator.data.electricity[-1] is not None
                    and coordinator.data.electricity[-1].cost is not None
                ):
                    description = dataclasses.replace(
                        description,
                        native_unit_of_measurement=(
                            coordinator.data.electricity[-1].cost.currency_unit
                        ),
                    )
                entities.append(OVOEnergySensor(coordinator, description, client))
        if coordinator.data.gas:
            for description in SENSOR_TYPES_GAS:
                if (
                    description.key == KEY_LAST_GAS_COST
                    and coordinator.data.gas[-1] is not None
                    and coordinator.data.gas[-1].cost is not None
                ):
                    description = dataclasses.replace(
                        description,
                        native_unit_of_measurement=coordinator.data.gas[
                            -1
                        ].cost.currency_unit,
                    )
                entities.append(OVOEnergySensor(coordinator, description, client))

    async_add_entities(entities, True)


class OVOEnergySensor(OVOEnergyDeviceEntity, SensorEntity):
    """Define a OVO Energy sensor."""

    coordinator: DataUpdateCoordinator[DataUpdateCoordinator[OVODailyUsage]]
    entity_description: OVOEnergySensorEntityDescription

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[OVODailyUsage],
        description: OVOEnergySensorEntityDescription,
        client: OVOEnergy,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, client)
        self._attr_unique_id = f"{DOMAIN}_{client.account_id}_{description.key}"
        self.entity_description = description

    @property
    def native_value(self) -> StateType | datetime:
        """Return the state."""
        usage = self.coordinator.data
        return self.entity_description.value(usage)
