"""Support for OVO Energy sensors."""

from collections.abc import Callable
import dataclasses
from datetime import datetime, timedelta
from typing import Final, override

from ovoenergy.models import OVODailyUsage

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import OVOEnergyConfigEntry, OVOEnergyDataUpdateCoordinator
from .entity import OVOEnergyDeviceEntity

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
        value=lambda usage: (
            usage.electricity[-1].consumption if usage.electricity else None
        ),
    ),
    OVOEnergySensorEntityDescription(
        key=KEY_LAST_ELECTRICITY_COST,
        translation_key=KEY_LAST_ELECTRICITY_COST,
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        value=lambda usage: (
            usage.electricity[-1].cost.amount
            if usage.electricity and usage.electricity[-1].cost is not None
            else None
        ),
    ),
    OVOEnergySensorEntityDescription(
        key="last_electricity_start_time",
        translation_key="last_electricity_start_time",
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.TIMESTAMP,
        value=lambda usage: (
            dt_util.as_utc(usage.electricity[-1].interval.start)
            if usage.electricity
            else None
        ),
    ),
    OVOEnergySensorEntityDescription(
        key="last_electricity_end_time",
        translation_key="last_electricity_end_time",
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.TIMESTAMP,
        value=lambda usage: (
            dt_util.as_utc(usage.electricity[-1].interval.end)
            if usage.electricity
            else None
        ),
    ),
)

SENSOR_TYPES_GAS: tuple[OVOEnergySensorEntityDescription, ...] = (
    OVOEnergySensorEntityDescription(
        key="last_gas_reading",
        translation_key="last_gas_reading",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value=lambda usage: usage.gas[-1].consumption if usage.gas else None,
    ),
    OVOEnergySensorEntityDescription(
        key=KEY_LAST_GAS_COST,
        translation_key=KEY_LAST_GAS_COST,
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        value=lambda usage: (
            usage.gas[-1].cost.amount
            if usage.gas and usage.gas[-1].cost is not None
            else None
        ),
    ),
    OVOEnergySensorEntityDescription(
        key="last_gas_start_time",
        translation_key="last_gas_start_time",
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.TIMESTAMP,
        value=lambda usage: (
            dt_util.as_utc(usage.gas[-1].interval.start) if usage.gas else None
        ),
    ),
    OVOEnergySensorEntityDescription(
        key="last_gas_end_time",
        translation_key="last_gas_end_time",
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.TIMESTAMP,
        value=lambda usage: (
            dt_util.as_utc(usage.gas[-1].interval.end) if usage.gas else None
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OVOEnergyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up OVO Energy sensor based on a config entry."""
    coordinator = entry.runtime_data

    added_keys: set[str] = set()

    @callback
    def async_discover_sensors() -> None:
        """Add sensors when their fuel's usage first becomes available."""
        entities = []
        for usage, descriptions in (
            (coordinator.data.electricity, SENSOR_TYPES_ELECTRICITY),
            (coordinator.data.gas, SENSOR_TYPES_GAS),
        ):
            if not usage:
                continue
            for description in descriptions:
                if description.key in added_keys:
                    continue
                if (
                    description.key in (KEY_LAST_ELECTRICITY_COST, KEY_LAST_GAS_COST)
                    and usage[-1].cost is not None
                ):
                    description = dataclasses.replace(
                        description,
                        native_unit_of_measurement=usage[-1].cost.currency_unit,
                    )
                entities.append(OVOEnergySensor(coordinator, description))
                added_keys.add(description.key)
        async_add_entities(entities, True)

    async_discover_sensors()
    entry.async_on_unload(coordinator.async_add_listener(async_discover_sensors))


class OVOEnergySensor(OVOEnergyDeviceEntity, SensorEntity):
    """Define a OVO Energy sensor."""

    entity_description: OVOEnergySensorEntityDescription

    def __init__(
        self,
        coordinator: OVOEnergyDataUpdateCoordinator,
        description: OVOEnergySensorEntityDescription,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        # Legacy format, kept as migrating existing unique IDs is not worth the risk
        self._attr_unique_id = (
            f"{DOMAIN}_{coordinator.client.account_id}_{description.key}"  # pylint: disable=home-assistant-entity-unique-id-redundant-domain
        )
        self.entity_description = description

    @property
    @override
    def native_value(self) -> StateType | datetime:
        """Return the state."""
        usage = self.coordinator.data
        return self.entity_description.value(usage)
