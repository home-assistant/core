"""Sensor platform for Ista EcoTrend integration."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import datetime
from enum import StrEnum
import logging

from homeassistant.components.recorder.models.statistics import (
    StatisticData,
    StatisticMetaData,
)
from homeassistant.components.recorder.statistics import (
    async_add_external_statistics,
    get_instance,
    get_last_statistics,
)
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfEnergy, UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import (
    DeviceEntry,
    DeviceEntryType,
    DeviceInfo,
)
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import IstaConfigEntry
from .const import DOMAIN
from .coordinator import IstaCoordinator
from .util import IstaConsumptionType, IstaValueType, get_native_value, get_statistics

_LOGGER = logging.getLogger(__name__)


@dataclass(kw_only=True, frozen=True)
class IstaSensorEntityDescription(SensorEntityDescription):
    """Ista EcoTrend Sensor Description."""

    consumption_type: IstaConsumptionType
    value_type: IstaValueType | None = None


class IstaSensorEntity(StrEnum):
    """Ista EcoTrend Entities."""

    HEATING = "heating"
    HEATING_ENERGY = "heating_energy"
    HEATING_COST = "heating_cost"

    HOT_WATER = "hot_water"
    HOT_WATER_ENERGY = "hot_water_energy"
    HOT_WATER_COST = "hot_water_cost"

    WATER = "water"
    WATER_COST = "water_cost"


SENSOR_DESCRIPTIONS: tuple[IstaSensorEntityDescription, ...] = (
    IstaSensorEntityDescription(
        key=IstaSensorEntity.HEATING,
        translation_key=IstaSensorEntity.HEATING,
        suggested_display_precision=0,
        consumption_type=IstaConsumptionType.HEATING,
        native_unit_of_measurement="units",
        state_class=SensorStateClass.TOTAL,
    ),
    IstaSensorEntityDescription(
        key=IstaSensorEntity.HEATING_ENERGY,
        translation_key=IstaSensorEntity.HEATING_ENERGY,
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=1,
        consumption_type=IstaConsumptionType.HEATING,
        value_type=IstaValueType.ENERGY,
    ),
    IstaSensorEntityDescription(
        key=IstaSensorEntity.HEATING_COST,
        translation_key=IstaSensorEntity.HEATING_COST,
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement="EUR",
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=0,
        entity_registry_enabled_default=False,
        consumption_type=IstaConsumptionType.HEATING,
        value_type=IstaValueType.COSTS,
    ),
    IstaSensorEntityDescription(
        key=IstaSensorEntity.HOT_WATER,
        translation_key=IstaSensorEntity.HOT_WATER,
        device_class=SensorDeviceClass.WATER,
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=1,
        consumption_type=IstaConsumptionType.HOT_WATER,
    ),
    IstaSensorEntityDescription(
        key=IstaSensorEntity.HOT_WATER_ENERGY,
        translation_key=IstaSensorEntity.HOT_WATER_ENERGY,
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=1,
        consumption_type=IstaConsumptionType.HOT_WATER,
        value_type=IstaValueType.ENERGY,
    ),
    IstaSensorEntityDescription(
        key=IstaSensorEntity.HOT_WATER_COST,
        translation_key=IstaSensorEntity.HOT_WATER_COST,
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement="EUR",
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=0,
        entity_registry_enabled_default=False,
        consumption_type=IstaConsumptionType.HOT_WATER,
        value_type=IstaValueType.COSTS,
    ),
    IstaSensorEntityDescription(
        key=IstaSensorEntity.WATER,
        translation_key=IstaSensorEntity.WATER,
        device_class=SensorDeviceClass.WATER,
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=1,
        entity_registry_enabled_default=False,
        consumption_type=IstaConsumptionType.WATER,
    ),
    IstaSensorEntityDescription(
        key=IstaSensorEntity.WATER_COST,
        translation_key=IstaSensorEntity.WATER_COST,
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement="EUR",
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=0,
        entity_registry_enabled_default=False,
        consumption_type=IstaConsumptionType.WATER,
        value_type=IstaValueType.COSTS,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: IstaConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the ista EcoTrend sensors."""

    coordinator = config_entry.runtime_data

    async_add_entities(
        IstaSensor(coordinator, description, consumption_unit)
        for description in SENSOR_DESCRIPTIONS
        for consumption_unit in coordinator.data
    )


class IstaSensor(CoordinatorEntity[IstaCoordinator], SensorEntity):
    """Ista EcoTrend sensor."""

    entity_description: IstaSensorEntityDescription
    _attr_has_entity_name = True
    device_entry: DeviceEntry

    def __init__(
        self,
        coordinator: IstaCoordinator,
        entity_description: IstaSensorEntityDescription,
        consumption_unit: str,
    ) -> None:
        """Initialize the ista EcoTrend sensor."""
        super().__init__(coordinator)
        self.consumption_unit = consumption_unit
        self.entity_description = entity_description
        self._attr_unique_id = f"{consumption_unit}_{entity_description.key}"
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            manufacturer="ista SE",
            model="ista EcoTrend",
            name=f"{coordinator.details[consumption_unit]["address"]["street"]} "
            f"{coordinator.details[consumption_unit]["address"]["houseNumber"]}".strip(),
            configuration_url="https://ecotrend.ista.de/",
            identifiers={(DOMAIN, consumption_unit)},
        )

    @property
    def native_value(self) -> StateType:
        """Return the state of the device."""

        return get_native_value(
            data=self.coordinator.data[self.consumption_unit],
            consumption_type=self.entity_description.consumption_type,
            value_type=self.entity_description.value_type,
        )

    async def async_added_to_hass(self) -> None:
        """When added to hass."""
        # perform initial statistics import when sensor is added, otherwise it would take
        # 1 day when _handle_coordinator_update is triggered for the first time.
        await self.update_statistics()
        await super().async_added_to_hass()

    def _handle_coordinator_update(self) -> None:
        """Handle coordinator update."""
        asyncio.run_coroutine_threadsafe(self.update_statistics(), self.hass.loop)

    async def update_statistics(self) -> None:
        """Import ista EcoTrend historical statistics."""

        # Remember the statistic_id that was initially created
        # in case the entity gets renamed, because we cannot
        # change the statistic_id
        name = self.coordinator.config_entry.options.get(
            f"lts_{self.entity_description.key}_{self.consumption_unit}"
        )
        if not name:
            name = self.entity_id.removeprefix("sensor.")
            self.hass.config_entries.async_update_entry(
                entry=self.coordinator.config_entry,
                options={
                    **self.coordinator.config_entry.options,
                    f"lts_{self.entity_description.key}_{self.consumption_unit}": name,
                },
            )

        statistic_id = f"{DOMAIN}:{name}"
        statistics_sum = 0.0
        statistics_since = None

        last_stats = await get_instance(self.hass).async_add_executor_job(
            get_last_statistics,
            self.hass,
            1,
            statistic_id,
            False,
            {"sum"},
        )

        _LOGGER.debug("Last statistics: %s", last_stats)

        if last_stats:
            statistics_sum = last_stats[statistic_id][0].get("sum") or 0.0
            statistics_since = datetime.datetime.fromtimestamp(
                last_stats[statistic_id][0].get("end") or 0, tz=datetime.UTC
            ) + datetime.timedelta(days=1)

        if monthly_consumptions := get_statistics(
            self.coordinator.data[self.consumption_unit],
            self.entity_description.consumption_type,
            self.entity_description.value_type,
        ):
            statistics: list[StatisticData] = [
                {
                    "start": consumptions["date"],
                    "state": consumptions["value"],
                    "sum": (statistics_sum := statistics_sum + consumptions["value"]),
                }
                for consumptions in monthly_consumptions
                if statistics_since is None or consumptions["date"] > statistics_since
            ]

            metadata: StatisticMetaData = {
                "has_mean": False,
                "has_sum": True,
                "name": f"{self.device_entry.name} {self.name}",
                "source": DOMAIN,
                "statistic_id": statistic_id,
                "unit_of_measurement": self.entity_description.native_unit_of_measurement,
            }
            if statistics:
                _LOGGER.debug("Insert statistics: %s %s", metadata, statistics)
                async_add_external_statistics(self.hass, metadata, statistics)
