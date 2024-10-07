"""Number platform for Teslemetry integration."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from itertools import chain
from typing import Any

from tesla_fleet_api import EnergySpecific, VehicleSpecific
from tesla_fleet_api.const import Scope

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import PERCENTAGE, PRECISION_WHOLE, UnitOfElectricCurrent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.icon import icon_for_battery_level

from . import TeslemetryConfigEntry
from .entity import TeslemetryEnergyInfoEntity, TeslemetryVehicleEntity
from .helpers import handle_command, handle_vehicle_command
from .models import TeslemetryEnergyData, TeslemetryVehicleData

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class TeslemetryNumberVehicleEntityDescription(NumberEntityDescription):
    """Describes Teslemetry Number entity."""

    func: Callable[[VehicleSpecific, float], Awaitable[Any]]
    native_min_value: float
    native_max_value: float
    min_key: str | None = None
    max_key: str
    scopes: list[Scope]


VEHICLE_DESCRIPTIONS: tuple[TeslemetryNumberVehicleEntityDescription, ...] = (
    TeslemetryNumberVehicleEntityDescription(
        key="charge_state_charge_current_request",
        native_step=PRECISION_WHOLE,
        native_min_value=0,
        native_max_value=32,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=NumberDeviceClass.CURRENT,
        mode=NumberMode.AUTO,
        max_key="charge_state_charge_current_request_max",
        func=lambda api, value: api.set_charging_amps(value),
        scopes=[Scope.VEHICLE_CHARGING_CMDS],
    ),
    TeslemetryNumberVehicleEntityDescription(
        key="charge_state_charge_limit_soc",
        native_step=PRECISION_WHOLE,
        native_min_value=50,
        native_max_value=100,
        native_unit_of_measurement=PERCENTAGE,
        device_class=NumberDeviceClass.BATTERY,
        mode=NumberMode.AUTO,
        min_key="charge_state_charge_limit_soc_min",
        max_key="charge_state_charge_limit_soc_max",
        func=lambda api, value: api.set_charge_limit(value),
        scopes=[Scope.VEHICLE_CHARGING_CMDS, Scope.VEHICLE_CMDS],
    ),
)


@dataclass(frozen=True, kw_only=True)
class TeslemetryNumberBatteryEntityDescription(NumberEntityDescription):
    """Describes Teslemetry Number entity."""

    func: Callable[[EnergySpecific, float], Awaitable[Any]]
    requires: str | None = None


ENERGY_INFO_DESCRIPTIONS: tuple[TeslemetryNumberBatteryEntityDescription, ...] = (
    TeslemetryNumberBatteryEntityDescription(
        key="backup_reserve_percent",
        func=lambda api, value: api.backup(int(value)),
        requires="components_battery",
    ),
    TeslemetryNumberBatteryEntityDescription(
        key="off_grid_vehicle_charging_reserve_percent",
        func=lambda api, value: api.off_grid_vehicle_charging_reserve(int(value)),
        requires="components_off_grid_vehicle_charging_reserve_supported",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TeslemetryConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Teslemetry number platform from a config entry."""

    async_add_entities(
        chain(
            (  # Add vehicle entities
                TeslemetryVehicleNumberEntity(
                    vehicle,
                    description,
                    entry.runtime_data.scopes,
                )
                for vehicle in entry.runtime_data.vehicles
                for description in VEHICLE_DESCRIPTIONS
            ),
            (  # Add energy site entities
                TeslemetryEnergyInfoNumberSensorEntity(
                    energysite,
                    description,
                    entry.runtime_data.scopes,
                )
                for energysite in entry.runtime_data.energysites
                for description in ENERGY_INFO_DESCRIPTIONS
                if description.requires is None
                or energysite.info_coordinator.data.get(description.requires)
            ),
        )
    )


class TeslemetryVehicleNumberEntity(TeslemetryVehicleEntity, NumberEntity):
    """Vehicle number entity base class."""

    entity_description: TeslemetryNumberVehicleEntityDescription

    def __init__(
        self,
        data: TeslemetryVehicleData,
        description: TeslemetryNumberVehicleEntityDescription,
        scopes: list[Scope],
    ) -> None:
        """Initialize the number entity."""
        self.scoped = any(scope in scopes for scope in description.scopes)
        self.entity_description = description
        super().__init__(
            data,
            description.key,
        )

    def _async_update_attrs(self) -> None:
        """Update the attributes of the entity."""
        self._attr_native_value = self._value

        if (min_key := self.entity_description.min_key) is not None:
            self._attr_native_min_value = self.get_number(
                min_key,
                self.entity_description.native_min_value,
            )
        else:
            self._attr_native_min_value = self.entity_description.native_min_value

        self._attr_native_max_value = self.get_number(
            self.entity_description.max_key,
            self.entity_description.native_max_value,
        )

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        value = int(value)
        self.raise_for_scope(self.entity_description.scopes[0])
        await self.wake_up_if_asleep()
        await handle_vehicle_command(self.entity_description.func(self.api, value))
        self._attr_native_value = value
        self.async_write_ha_state()


class TeslemetryEnergyInfoNumberSensorEntity(TeslemetryEnergyInfoEntity, NumberEntity):
    """Energy info number entity base class."""

    entity_description: TeslemetryNumberBatteryEntityDescription
    _attr_native_step = PRECISION_WHOLE
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_device_class = NumberDeviceClass.BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(
        self,
        data: TeslemetryEnergyData,
        description: TeslemetryNumberBatteryEntityDescription,
        scopes: list[Scope],
    ) -> None:
        """Initialize the number entity."""
        self.scoped = Scope.ENERGY_CMDS in scopes
        self.entity_description = description
        super().__init__(data, description.key)

    def _async_update_attrs(self) -> None:
        """Update the attributes of the entity."""
        self._attr_native_value = self._value
        self._attr_icon = icon_for_battery_level(self.native_value)

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        value = int(value)
        self.raise_for_scope(Scope.ENERGY_CMDS)
        await handle_command(self.entity_description.func(self.api, value))
        self._attr_native_value = value
        self.async_write_ha_state()
