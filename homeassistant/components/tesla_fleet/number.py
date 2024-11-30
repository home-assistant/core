"""Number platform for Tesla Fleet integration."""

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

from . import TeslaFleetConfigEntry
from .entity import TeslaFleetEnergyInfoEntity, TeslaFleetVehicleEntity
from .helpers import handle_command, handle_vehicle_command
from .models import TeslaFleetEnergyData, TeslaFleetVehicleData

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class TeslaFleetNumberVehicleEntityDescription(NumberEntityDescription):
    """Describes TeslaFleet Number entity."""

    func: Callable[[VehicleSpecific, float], Awaitable[Any]]
    native_min_value: float
    native_max_value: float
    min_key: str | None = None
    max_key: str
    scopes: list[Scope]


VEHICLE_DESCRIPTIONS: tuple[TeslaFleetNumberVehicleEntityDescription, ...] = (
    TeslaFleetNumberVehicleEntityDescription(
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
    TeslaFleetNumberVehicleEntityDescription(
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
class TeslaFleetNumberBatteryEntityDescription(NumberEntityDescription):
    """Describes TeslaFleet Number entity."""

    func: Callable[[EnergySpecific, float], Awaitable[Any]]
    requires: str | None = None


ENERGY_INFO_DESCRIPTIONS: tuple[TeslaFleetNumberBatteryEntityDescription, ...] = (
    TeslaFleetNumberBatteryEntityDescription(
        key="backup_reserve_percent",
        func=lambda api, value: api.backup(int(value)),
        requires="components_battery",
    ),
    TeslaFleetNumberBatteryEntityDescription(
        key="off_grid_vehicle_charging_reserve_percent",
        func=lambda api, value: api.off_grid_vehicle_charging_reserve(int(value)),
        requires="components_off_grid_vehicle_charging_reserve_supported",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TeslaFleetConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the TeslaFleet number platform from a config entry."""

    async_add_entities(
        chain(
            (  # Add vehicle entities
                TeslaFleetVehicleNumberEntity(
                    vehicle,
                    description,
                    entry.runtime_data.scopes,
                )
                for vehicle in entry.runtime_data.vehicles
                for description in VEHICLE_DESCRIPTIONS
            ),
            (  # Add energy site entities
                TeslaFleetEnergyInfoNumberSensorEntity(
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


class TeslaFleetVehicleNumberEntity(TeslaFleetVehicleEntity, NumberEntity):
    """Vehicle number entity base class."""

    entity_description: TeslaFleetNumberVehicleEntityDescription

    def __init__(
        self,
        data: TeslaFleetVehicleData,
        description: TeslaFleetNumberVehicleEntityDescription,
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
        self.raise_for_read_only(self.entity_description.scopes[0])
        await self.wake_up_if_asleep()
        await handle_vehicle_command(self.entity_description.func(self.api, value))
        self._attr_native_value = value
        self.async_write_ha_state()


class TeslaFleetEnergyInfoNumberSensorEntity(TeslaFleetEnergyInfoEntity, NumberEntity):
    """Energy info number entity base class."""

    entity_description: TeslaFleetNumberBatteryEntityDescription
    _attr_native_step = PRECISION_WHOLE
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_device_class = NumberDeviceClass.BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(
        self,
        data: TeslaFleetEnergyData,
        description: TeslaFleetNumberBatteryEntityDescription,
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
        self.raise_for_read_only(Scope.ENERGY_CMDS)
        await handle_command(self.entity_description.func(self.api, value))
        self._attr_native_value = value
        self.async_write_ha_state()
