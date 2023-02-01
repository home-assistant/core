"""Support for OVO Energy sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Final

from ovoenergy.ovoenergy import OVOEnergy

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

from . import OVOCoordinatorData, OVOEnergyDeviceEntity
from .const import DATA_CLIENT, DATA_COORDINATOR, DOMAIN

SCAN_INTERVAL = timedelta(seconds=300)
PARALLEL_UPDATES = 4

KEY_LAST_ELECTRICITY_COST: Final = "last_electricity_cost"
KEY_LAST_GAS_COST: Final = "last_gas_cost"


@dataclass
class OVOEnergySensorEntityDescription(SensorEntityDescription):
    """Class describing System Bridge sensor entities."""

    value: Callable = round


def get_electricity_unit_rate_amount(
    data: OVOCoordinatorData,
    index: int | None,
) -> float | None:
    """Get the value of the rate."""
    if (
        index is None
        or data.plan is None
        or data.plan.electricity is None
        or len(data.plan.electricity.unit_rates) < 1
        or index >= len(data.plan.electricity.unit_rates)
    ):
        return None
    return data.plan.electricity.unit_rates[index].unit_rate.amount


def get_gas_unit_rate_amount(
    data: OVOCoordinatorData,
    index: int | None,
) -> float | None:
    """Get the value of the rate."""
    if (
        index is None
        or data.plan is None
        or data.plan.gas is None
        or len(data.plan.gas.unit_rates) < 1
        or index >= len(data.plan.gas.unit_rates)
    ):
        return None
    return data.plan.gas.unit_rates[index].unit_rate.amount


SENSOR_TYPES_ELECTRICITY: tuple[OVOEnergySensorEntityDescription, ...] = (
    OVOEnergySensorEntityDescription(
        key="last_electricity_reading",
        name="OVO Last Electricity Reading",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value=lambda data: data.daily_usage.electricity[-1].consumption
        if data.daily_usage is not None
        else None,
    ),
    OVOEnergySensorEntityDescription(
        key=KEY_LAST_ELECTRICITY_COST,
        name="OVO Last Electricity Cost",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value=lambda data: data.daily_usage.electricity[-1].cost.amount
        if data.daily_usage is not None
        and data.daily_usage.electricity[-1].cost is not None
        else None,
    ),
    OVOEnergySensorEntityDescription(
        key="last_electricity_start_time",
        name="OVO Last Electricity Start Time",
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.TIMESTAMP,
        value=lambda data: dt_util.as_utc(
            data.daily_usage.electricity[-1].interval.start
        )
        if data.daily_usage is not None
        and data.daily_usage.electricity[-1].interval is not None
        else None,
    ),
    OVOEnergySensorEntityDescription(
        key="last_electricity_end_time",
        name="OVO Last Electricity End Time",
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.TIMESTAMP,
        value=lambda data: dt_util.as_utc(data.daily_usage.electricity[-1].interval.end)
        if data.daily_usage is not None
        and data.daily_usage.electricity[-1].interval is not None
        else None,
    ),
)

SENSOR_TYPES_GAS: tuple[OVOEnergySensorEntityDescription, ...] = (
    OVOEnergySensorEntityDescription(
        key="last_gas_reading",
        name="OVO Last Gas Reading",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        icon="mdi:gas-cylinder",
        value=lambda data: data.daily_usage.gas[-1].consumption
        if data.daily_usage is not None
        else None,
    ),
    OVOEnergySensorEntityDescription(
        key=KEY_LAST_GAS_COST,
        name="OVO Last Gas Cost",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:cash-multiple",
        value=lambda data: data.daily_usage.gas[-1].cost.amount
        if data.daily_usage is not None and data.daily_usage.gas[-1].cost is not None
        else None,
    ),
    OVOEnergySensorEntityDescription(
        key="last_gas_start_time",
        name="OVO Last Gas Start Time",
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.TIMESTAMP,
        value=lambda data: dt_util.as_utc(data.daily_usage.gas[-1].interval.start)
        if data.daily_usage is not None
        and data.daily_usage.gas[-1].interval is not None
        else None,
    ),
    OVOEnergySensorEntityDescription(
        key="last_gas_end_time",
        name="OVO Last Gas End Time",
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.TIMESTAMP,
        value=lambda data: dt_util.as_utc(data.daily_usage.gas[-1].interval.end)
        if data.daily_usage is not None
        and data.daily_usage.gas[-1].interval is not None
        else None,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up OVO Energy sensor based on a config entry."""
    coordinator: DataUpdateCoordinator[OVOCoordinatorData] = hass.data[DOMAIN][
        entry.entry_id
    ][DATA_COORDINATOR]
    client: OVOEnergy = hass.data[DOMAIN][entry.entry_id][DATA_CLIENT]

    entities = []

    if coordinator.data and coordinator.data.daily_usage:
        if coordinator.data.daily_usage.electricity:
            for description in SENSOR_TYPES_ELECTRICITY:
                if (
                    description.key == KEY_LAST_ELECTRICITY_COST
                    and coordinator.data.daily_usage.electricity[-1] is not None
                    and coordinator.data.daily_usage.electricity[-1].cost is not None
                ):
                    description.native_unit_of_measurement = (
                        coordinator.data.daily_usage.electricity[-1].cost.currency_unit
                    )
                entities.append(OVOEnergySensor(coordinator, description, client))
        if coordinator.data.daily_usage.gas:
            for description in SENSOR_TYPES_GAS:
                if (
                    description.key == KEY_LAST_GAS_COST
                    and coordinator.data.daily_usage.gas[-1] is not None
                    and coordinator.data.daily_usage.gas[-1].cost is not None
                ):
                    description.native_unit_of_measurement = (
                        coordinator.data.daily_usage.gas[-1].cost.currency_unit
                    )
                entities.append(OVOEnergySensor(coordinator, description, client))

    if coordinator.data and coordinator.data.plan:
        if coordinator.data.plan.electricity is not None:
            entities.append(
                OVOEnergySensor(
                    coordinator,
                    OVOEnergySensorEntityDescription(
                        key="plan_electricity_standing_charge",
                        name="OVO Electricity Standing Charge",
                        device_class=SensorDeviceClass.MONETARY,
                        native_unit_of_measurement=coordinator.data.plan.electricity.standing_charge.currency_unit,
                        value=lambda data: data.plan.electricity.standing_charge.amount
                        if data.plan is not None
                        else None,
                    ),
                    client,
                )
            )
            for index, rate in enumerate(coordinator.data.plan.electricity.unit_rates):
                key = rate.name.replace(" ", "_").lower()
                entities.append(
                    OVOEnergySensor(
                        coordinator,
                        OVOEnergySensorEntityDescription(
                            key=f"plan_electricity_rate_{key}",
                            name=f"OVO Electricity Rate - {rate.name[0].upper() + rate.name[1:]}",
                            device_class=SensorDeviceClass.MONETARY,
                            native_unit_of_measurement=rate.unit_rate.currency_unit,
                            value=lambda data, index=index: get_electricity_unit_rate_amount(
                                data, index
                            ),
                        ),
                        client,
                    )
                )
        if coordinator.data.plan.gas is not None:
            entities.append(
                OVOEnergySensor(
                    coordinator,
                    OVOEnergySensorEntityDescription(
                        key="plan_gas_standing_charge",
                        name="OVO Gas Standing Charge",
                        device_class=SensorDeviceClass.MONETARY,
                        native_unit_of_measurement=coordinator.data.plan.gas.standing_charge.currency_unit,
                        value=lambda data: data.plan.gas.standing_charge.amount
                        if data.plan is not None
                        else None,
                    ),
                    client,
                )
            )
            for index, rate in enumerate(coordinator.data.plan.gas.unit_rates):
                key = rate.name.replace(" ", "_").lower()
                entities.append(
                    OVOEnergySensor(
                        coordinator,
                        OVOEnergySensorEntityDescription(
                            key=f"plan_gas_rate_{key}",
                            name=f"OVO Gas Rate - {rate.name[0].upper() + rate.name[1:]}",
                            device_class=SensorDeviceClass.MONETARY,
                            native_unit_of_measurement=rate.unit_rate.currency_unit,
                            value=lambda data, index=index: get_gas_unit_rate_amount(
                                data, index
                            ),
                        ),
                        client,
                    )
                )

    async_add_entities(entities, True)


class OVOEnergySensor(OVOEnergyDeviceEntity, SensorEntity):
    """Define a OVO Energy sensor."""

    coordinator: DataUpdateCoordinator[OVOCoordinatorData]
    entity_description: OVOEnergySensorEntityDescription

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[OVOCoordinatorData],
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
        usage: OVOCoordinatorData = self.coordinator.data
        return self.entity_description.value(usage)
