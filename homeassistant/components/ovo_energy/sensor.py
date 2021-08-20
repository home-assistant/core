"""Support for OVO Energy sensors."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Callable, cast

from ovoenergy import OVODailyUsage
from ovoenergy.ovoenergy import OVOEnergy

from homeassistant.components.sensor import (
    STATE_CLASS_TOTAL_INCREASING,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_MONETARY,
    DEVICE_CLASS_TIMESTAMP,
    ENERGY_KILO_WATT_HOUR,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from . import OVOEnergyDeviceEntity
from .const import DATA_CLIENT, DATA_COORDINATOR, DOMAIN

SCAN_INTERVAL = timedelta(seconds=300)
PARALLEL_UPDATES = 4


@dataclass
class OVOEnergySensorEntityDescription(SensorEntityDescription):
    """Class describing System Bridge sensor entities."""

    value: Callable = round


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up OVO Energy sensor based on a config entry."""
    coordinator: DataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        DATA_COORDINATOR
    ]
    client: OVOEnergy = hass.data[DOMAIN][entry.entry_id][DATA_CLIENT]

    entities = []

    if coordinator.data:
        if coordinator.data.electricity:
            entities = [
                *entities,
                OVOEnergySensor(
                    coordinator,
                    OVOEnergySensorEntityDescription(
                        key=f"{DOMAIN}_{client.account_id}_last_electricity_reading",
                        name="OVO Last Electricity Reading",
                        device_class=DEVICE_CLASS_ENERGY,
                        state_class=STATE_CLASS_TOTAL_INCREASING,
                        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
                        value=lambda usage: usage.electricity[-1].consumption,
                    ),
                    client,
                ),
                OVOEnergySensor(
                    coordinator,
                    OVOEnergySensorEntityDescription(
                        key=f"{DOMAIN}_{client.account_id}_last_electricity_cost",
                        name="OVO Last Electricity Cost",
                        device_class=DEVICE_CLASS_MONETARY,
                        state_class=STATE_CLASS_TOTAL_INCREASING,
                        native_unit_of_measurement=coordinator.data.electricity[
                            -1
                        ].cost.currency_unit,
                        icon="mdi:cash-multiple",
                        value=lambda usage: usage.electricity[-1].consumption,
                    ),
                    client,
                ),
                OVOEnergySensor(
                    coordinator,
                    OVOEnergySensorEntityDescription(
                        key=f"{DOMAIN}_{client.account_id}_last_electricity_start_time",
                        name="OVO Last Electricity Start Time",
                        entity_registry_enabled_default=False,
                        device_class=DEVICE_CLASS_TIMESTAMP,
                        value=lambda usage: dt_util.as_utc(
                            usage.electricity[-1].interval.start
                        ),
                    ),
                    client,
                ),
                OVOEnergySensor(
                    coordinator,
                    OVOEnergySensorEntityDescription(
                        key=f"{DOMAIN}_{client.account_id}_last_electricity_end_time",
                        name="OVO Last Electricity End Time",
                        entity_registry_enabled_default=False,
                        device_class=DEVICE_CLASS_TIMESTAMP,
                        value=lambda usage: dt_util.as_utc(
                            usage.electricity[-1].interval.end
                        ),
                    ),
                    client,
                ),
            ]
        if coordinator.data.gas:
            entities = [
                *entities,
                OVOEnergySensor(
                    coordinator,
                    OVOEnergySensorEntityDescription(
                        key=f"{DOMAIN}_{client.account_id}_last_gas_reading",
                        name="OVO Last Gas Reading",
                        device_class=DEVICE_CLASS_ENERGY,
                        state_class=STATE_CLASS_TOTAL_INCREASING,
                        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
                        icon="mdi:gas-cylinder",
                        value=lambda usage: usage.gas[-1].consumption,
                    ),
                    client,
                ),
                OVOEnergySensor(
                    coordinator,
                    OVOEnergySensorEntityDescription(
                        key=f"{DOMAIN}_{client.account_id}_last_gas_cost",
                        name="OVO Last Gas Cost",
                        device_class=DEVICE_CLASS_MONETARY,
                        state_class=STATE_CLASS_TOTAL_INCREASING,
                        native_unit_of_measurement=coordinator.data.gas[
                            -1
                        ].cost.currency_unit,
                        icon="mdi:cash-multiple",
                        value=lambda usage: usage.gas[-1].consumption,
                    ),
                    client,
                ),
                OVOEnergySensor(
                    coordinator,
                    OVOEnergySensorEntityDescription(
                        key=f"{DOMAIN}_{client.account_id}_last_gas_start_time",
                        name="OVO Last Gas Start Time",
                        entity_registry_enabled_default=False,
                        device_class=DEVICE_CLASS_TIMESTAMP,
                        value=lambda usage: dt_util.as_utc(
                            usage.gas[-1].interval.start
                        ),
                    ),
                    client,
                ),
                OVOEnergySensor(
                    coordinator,
                    OVOEnergySensorEntityDescription(
                        key=f"{DOMAIN}_{client.account_id}_last_gas_end_time",
                        name="OVO Last Gas End Time",
                        entity_registry_enabled_default=False,
                        device_class=DEVICE_CLASS_TIMESTAMP,
                        value=lambda usage: dt_util.as_utc(usage.gas[-1].interval.end),
                    ),
                    client,
                ),
            ]

    async_add_entities(entities, True)


class OVOEnergySensor(OVOEnergyDeviceEntity, SensorEntity):
    """Define a OVO Energy sensor."""

    coordinator: DataUpdateCoordinator
    entity_description: OVOEnergySensorEntityDescription

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        description: OVOEnergySensorEntityDescription,
        client: OVOEnergy,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, client)
        self.entity_description = description

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this entity."""
        return self.entity_description.key

    @property
    def native_value(self) -> StateType:
        """Return the state."""
        usage: OVODailyUsage = self.coordinator.data
        try:
            return cast(StateType, self.entity_description.value(usage))
        except TypeError:
            return None
