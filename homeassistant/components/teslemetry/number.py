"""Number platform for Teslemetry integration."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from itertools import chain
from typing import Any

from tesla_fleet_api.const import Scope
from tesla_fleet_api.teslemetry import EnergySite, Vehicle
from teslemetry_stream import TeslemetryStreamVehicle

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
    RestoreNumber,
)
from homeassistant.const import (
    PERCENTAGE,
    PRECISION_WHOLE,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfElectricCurrent,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.icon import icon_for_battery_level

from . import TeslemetryConfigEntry
from .entity import (
    TeslemetryEnergyInfoEntity,
    TeslemetryRootEntity,
    TeslemetryVehiclePollingEntity,
    TeslemetryVehicleStreamEntity,
)
from .helpers import handle_command, handle_vehicle_command
from .models import TeslemetryEnergyData, TeslemetryVehicleData

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class TeslemetryNumberVehicleEntityDescription(NumberEntityDescription):
    """Describes Teslemetry Number entity."""

    func: Callable[[Vehicle, int], Awaitable[Any]]
    min_key: str | None = None
    max_key: str
    native_min_value: float
    native_max_value: float
    scopes: list[Scope]
    value_listener: Callable[
        [TeslemetryStreamVehicle, Callable[[int | None], None]],
        Callable[[], None],
    ]
    max_listener: (
        Callable[
            [TeslemetryStreamVehicle, Callable[[int | None], None]], Callable[[], None]
        ]
        | None
    ) = None


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
        scopes=[Scope.VEHICLE_CHARGING_CMDS, Scope.VEHICLE_CMDS],
        value_listener=lambda x, y: x.listen_ChargeCurrentRequest(y),
        max_listener=lambda x, y: x.listen_ChargeCurrentRequestMax(y),
    ),
    TeslemetryNumberVehicleEntityDescription(
        key="charge_state_charge_limit_soc",
        native_step=PRECISION_WHOLE,
        native_min_value=50,
        native_max_value=100,
        native_unit_of_measurement=PERCENTAGE,
        device_class=NumberDeviceClass.BATTERY,
        mode=NumberMode.AUTO,
        max_key="charge_state_charge_limit_soc_max",
        func=lambda api, value: api.set_charge_limit(value),
        scopes=[Scope.VEHICLE_CHARGING_CMDS, Scope.VEHICLE_CMDS],
        value_listener=lambda x, y: x.listen_ChargeLimitSoc(y),
    ),
)


@dataclass(frozen=True, kw_only=True)
class TeslemetryNumberBatteryEntityDescription(NumberEntityDescription):
    """Describes Teslemetry Number entity."""

    func: Callable[[EnergySite, float], Awaitable[Any]]
    requires: str | None = None
    scopes: list[Scope]


ENERGY_INFO_DESCRIPTIONS: tuple[TeslemetryNumberBatteryEntityDescription, ...] = (
    TeslemetryNumberBatteryEntityDescription(
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
    TeslemetryNumberBatteryEntityDescription(
        key="off_grid_vehicle_charging_reserve_percent",
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
    hass: HomeAssistant,
    entry: TeslemetryConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Teslemetry number platform from a config entry."""

    async_add_entities(
        chain(
            (
                TeslemetryVehiclePollingNumberEntity(
                    vehicle,
                    description,
                    entry.runtime_data.scopes,
                )
                if vehicle.api.pre2021 or vehicle.firmware < "2024.26"
                else TeslemetryStreamingNumberEntity(
                    vehicle,
                    description,
                    entry.runtime_data.scopes,
                )
                for vehicle in entry.runtime_data.vehicles
                for description in VEHICLE_DESCRIPTIONS
            ),
            (
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


class TeslemetryVehicleNumberEntity(TeslemetryRootEntity, NumberEntity):
    """Vehicle number entity base class."""

    api: Vehicle
    entity_description: TeslemetryNumberVehicleEntityDescription

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        value = int(value)
        self.raise_for_scope(self.entity_description.scopes[0])
        await handle_vehicle_command(self.entity_description.func(self.api, value))
        self._attr_native_value = value
        self.async_write_ha_state()


class TeslemetryVehiclePollingNumberEntity(
    TeslemetryVehiclePollingEntity, TeslemetryVehicleNumberEntity
):
    """Vehicle polling number entity."""

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

        self._attr_native_max_value = self.get_number(
            self.entity_description.max_key,
            self.entity_description.native_max_value,
        )


class TeslemetryStreamingNumberEntity(
    TeslemetryVehicleStreamEntity, TeslemetryVehicleNumberEntity, RestoreNumber
):
    """Number entity for current charge."""

    entity_description: TeslemetryNumberVehicleEntityDescription

    def __init__(
        self,
        data: TeslemetryVehicleData,
        description: TeslemetryNumberVehicleEntityDescription,
        scopes: list[Scope],
    ) -> None:
        """Initialize the Number entity."""
        self.scoped = any(scope in scopes for scope in description.scopes)
        self.entity_description = description
        self._attr_native_max_value = self.entity_description.native_max_value
        super().__init__(data, description.key)

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()

        # Restore state
        if (last_state := await self.async_get_last_state()) and (
            last_number_data := await self.async_get_last_number_data()
        ):
            if last_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
                self._attr_native_value = last_number_data.native_value
            if last_number_data.native_max_value:
                self._attr_native_max_value = last_number_data.native_max_value
            self.async_write_ha_state()

        # Add listeners
        self.async_on_remove(
            self.entity_description.value_listener(
                self.vehicle.stream_vehicle, self._value_callback
            )
        )
        if self.entity_description.max_listener:
            self.async_on_remove(
                self.entity_description.max_listener(
                    self.vehicle.stream_vehicle, self._max_callback
                )
            )

    def _value_callback(self, value: int | None) -> None:
        """Update the value of the entity."""
        self._attr_native_value = None if value is None else value
        self.async_write_ha_state()

    def _max_callback(self, value: int | None) -> None:
        """Update the value of the entity."""
        self._attr_native_max_value = (
            self.entity_description.native_max_value if value is None else value
        )
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
