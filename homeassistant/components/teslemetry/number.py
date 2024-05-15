"""Number platform for Teslemetry integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from itertools import chain
from typing import cast

from tesla_fleet_api.const import Scope

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    PRECISION_WHOLE,
    UnitOfElectricCurrent,
    UnitOfSpeed,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.icon import icon_for_battery_level
from homeassistant.util.unit_conversion import SpeedConverter

from .entity import TeslemetryEnergyInfoEntity, TeslemetryVehicleEntity
from .models import TeslemetryEnergyData, TeslemetryVehicleData


@dataclass(frozen=True, kw_only=True)
class TeslemetryNumberEntityDescription(NumberEntityDescription):
    """Describes Teslemetry Number entity."""

    func: Callable
    native_min_value: float
    native_max_value: float
    min_key: str = ""
    max_key: str = ""
    scopes: list[Scope]
    requires: str | None = None


VEHICLE_DESCRIPTIONS: tuple[TeslemetryNumberEntityDescription, ...] = (
    TeslemetryNumberEntityDescription(
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
    TeslemetryNumberEntityDescription(
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

ENERGY_INFO_DESCRIPTIONS: tuple[TeslemetryNumberEntityDescription, ...] = (
    TeslemetryNumberEntityDescription(
        key="backup_reserve_percent",
        native_step=PRECISION_WHOLE,
        native_min_value=0,
        native_max_value=100,
        device_class=NumberDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        scopes=[Scope.ENERGY_CMDS],
        func=lambda api, value: api.backup(int(value)),
        requires="components_battery",
    ),
    TeslemetryNumberEntityDescription(
        key="off_grid_vehicle_charging_reserve",
        native_step=PRECISION_WHOLE,
        native_min_value=0,
        native_max_value=100,
        device_class=NumberDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        scopes=[Scope.ENERGY_CMDS],
        func=lambda api, value: api.off_grid_vehicle_charging_reserve(int(value)),
        requires="components_off_grid_vehicle_charging_reserve_supported",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Teslemetry sensor platform from a config entry."""

    async_add_entities(
        chain(
            (  # Add imperial speed limit entities
                TeslemetryImperialSpeedNumberEntity(
                    hass,
                    vehicle,
                    entry.runtime_data.scopes,
                )
                for vehicle in entry.runtime_data.vehicles
            ),
            (  # Add metric speed limit entities
                TeslemetryMetricSpeedNumberEntity(
                    hass,
                    vehicle,
                    entry.runtime_data.scopes,
                )
                for vehicle in entry.runtime_data.vehicles
            ),
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
    """Number entity for current charge."""

    entity_description: TeslemetryNumberEntityDescription

    def __init__(
        self,
        data: TeslemetryVehicleData,
        description: TeslemetryNumberEntityDescription,
        scopes: list[Scope],
    ) -> None:
        """Initialize the Number entity."""
        self.scoped = any(scope in scopes for scope in description.scopes)
        self.entity_description = description
        super().__init__(
            data,
            description.key,
        )

    def _async_update_attrs(self) -> None:
        """Update the attributes of the entity."""
        self._attr_native_value = self._value
        self._attr_native_min_value = cast(
            float,
            self.get(
                self.entity_description.min_key,
                self.entity_description.native_min_value,
            ),
        )
        self._attr_native_max_value = cast(
            float,
            self.get(
                self.entity_description.max_key,
                self.entity_description.native_max_value,
            ),
        )

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        value = int(value)
        self.raise_for_scope()
        await self.wake_up_if_asleep()
        await self.handle_command(self.entity_description.func(self.api, value))
        self._attr_native_value = value
        self.async_write_ha_state()


class TeslemetryImperialSpeedNumberEntity(TeslemetryVehicleEntity, NumberEntity):
    """Number entity for speed limit."""

    device_class = NumberDeviceClass.SPEED
    native_unit_of_measurement = UnitOfSpeed.MILES_PER_HOUR
    mode = NumberMode.BOX
    _attr_entity_registry_enabled_default = False

    def __init__(
        self,
        hass: HomeAssistant,
        data: TeslemetryVehicleData,
        scopes: list[Scope],
    ) -> None:
        """Initialize the Number entity."""
        self.hass = hass
        self.scoped = Scope.VEHICLE_CMDS in scopes

        super().__init__(data, "vehicle_state_speed_limit_mode_current_limit_mph")

    def _async_update_attrs(self) -> None:
        """Update the attributes of the entity."""
        if self._value is None:
            self._attr_native_value = None
        else:
            self._attr_native_value = self._value
        self._attr_native_min_value = (
            self.get(
                "vehicle_state_speed_limit_mode_min_limit_mph",
            )
            or 50
        )
        self._attr_native_max_value = (
            self.get(
                "vehicle_state_speed_limit_mode_max_limit_mph",
            )
            or 120
        )

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        self.raise_for_scope()
        await self.wake_up_if_asleep()
        await self.handle_command(self.api.speed_limit_set_limit(value))
        self._attr_native_value = value
        self.async_write_ha_state()


class TeslemetryMetricSpeedNumberEntity(TeslemetryVehicleEntity, NumberEntity):
    """Number entity for speed limit in metric."""

    device_class = NumberDeviceClass.SPEED
    mode = NumberMode.BOX
    native_unit_of_measurement = UnitOfSpeed.KILOMETERS_PER_HOUR
    _attr_entity_registry_enabled_default = False

    def __init__(
        self,
        hass: HomeAssistant,
        data: TeslemetryVehicleData,
        scopes: list[Scope],
    ) -> None:
        """Initialize the Number entity."""
        self.hass = hass
        self.scoped = Scope.VEHICLE_CMDS in scopes

        # Handle Metric
        self.convert_to = SpeedConverter.converter_factory(
            UnitOfSpeed.MILES_PER_HOUR, UnitOfSpeed.KILOMETERS_PER_HOUR
        )
        self.convert_from = SpeedConverter.converter_factory(
            UnitOfSpeed.KILOMETERS_PER_HOUR, UnitOfSpeed.MILES_PER_HOUR
        )

        super().__init__(data, "vehicle_state_speed_limit_mode_current_limit_mph")

    def _async_update_attrs(self) -> None:
        """Update the attributes of the entity."""
        if self._value is None:
            self._attr_native_value = None
        else:
            self._attr_native_value = round(self.convert_to(self._value), 1)
        self._attr_native_min_value = round(
            self.convert_to(
                self.get("vehicle_state_speed_limit_mode_min_limit_mph") or 50
            ),
            1,
        )
        self._attr_native_max_value = round(
            self.convert_to(
                self.get("vehicle_state_speed_limit_mode_max_limit_mph") or 120
            ),
            1,
        )

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        self.raise_for_scope()
        await self.wake_up_if_asleep()
        await self.handle_command(
            self.api.speed_limit_set_limit(round(self.convert_from(value), 4))
        )
        self._attr_native_value = value
        self.async_write_ha_state()


class TeslemetryEnergyInfoNumberSensorEntity(TeslemetryEnergyInfoEntity, NumberEntity):
    """Number entity for energy info number entity."""

    entity_description: TeslemetryNumberEntityDescription

    def __init__(
        self,
        data: TeslemetryEnergyData,
        description: TeslemetryNumberEntityDescription,
        scopes: list[Scope],
    ) -> None:
        """Initialize the Number entity."""
        self.scoped = any(scope in scopes for scope in description.scopes)
        self.entity_description = description
        super().__init__(data, description.key)

    def _async_update_attrs(self) -> None:
        """Update the attributes of the entity."""
        self._attr_native_value = self._value
        self._attr_native_min_value = cast(
            float,
            self.get(
                self.entity_description.min_key,
                self.entity_description.native_min_value,
            ),
        )
        self._attr_native_max_value = cast(
            float,
            self.get(
                self.entity_description.max_key,
                self.entity_description.native_max_value,
            ),
        )
        self._attr_icon = icon_for_battery_level(self.native_value)

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        value = int(value)
        self.raise_for_scope()
        await self.handle_command(self.entity_description.func(self.api, value))
        self._attr_native_value = value
        self.async_write_ha_state()
