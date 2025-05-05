"""Select platform for Teslemetry integration."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from itertools import chain
from typing import Any

from tesla_fleet_api.const import EnergyExportMode, EnergyOperationMode, Scope, Seat
from tesla_fleet_api.teslemetry import Vehicle
from teslemetry_stream import TeslemetryStreamVehicle

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import TeslemetryConfigEntry
from .entity import (
    TeslemetryEnergyInfoEntity,
    TeslemetryRootEntity,
    TeslemetryVehiclePollingEntity,
    TeslemetryVehicleStreamEntity,
)
from .helpers import handle_command, handle_vehicle_command
from .models import TeslemetryEnergyData, TeslemetryVehicleData

OFF = "off"
LOW = "low"
MEDIUM = "medium"
HIGH = "high"

PARALLEL_UPDATES = 0

LEVEL = {OFF: 0, LOW: 1, MEDIUM: 2, HIGH: 3}


@dataclass(frozen=True, kw_only=True)
class TeslemetrySelectEntityDescription(SelectEntityDescription):
    """Seat Heater entity description."""

    select_fn: Callable[[Vehicle, int], Awaitable[Any]]
    supported_fn: Callable[[dict], bool] = lambda _: True
    streaming_listener: (
        Callable[
            [TeslemetryStreamVehicle, Callable[[int | None], None]],
            Callable[[], None],
        ]
        | None
    ) = None
    options: list[str]


VEHICLE_DESCRIPTIONS: tuple[TeslemetrySelectEntityDescription, ...] = (
    TeslemetrySelectEntityDescription(
        key="climate_state_seat_heater_left",
        select_fn=lambda api, level: api.remote_seat_heater_request(
            Seat.FRONT_LEFT, level
        ),
        streaming_listener=lambda x, y: x.listen_SeatHeaterLeft(y),
        options=[
            OFF,
            LOW,
            MEDIUM,
            HIGH,
        ],
    ),
    TeslemetrySelectEntityDescription(
        key="climate_state_seat_heater_right",
        select_fn=lambda api, level: api.remote_seat_heater_request(
            Seat.FRONT_RIGHT, level
        ),
        streaming_listener=lambda x, y: x.listen_SeatHeaterRight(y),
        options=[
            OFF,
            LOW,
            MEDIUM,
            HIGH,
        ],
    ),
    TeslemetrySelectEntityDescription(
        key="climate_state_seat_heater_rear_left",
        select_fn=lambda api, level: api.remote_seat_heater_request(
            Seat.REAR_LEFT, level
        ),
        supported_fn=lambda data: data.get("vehicle_config_rear_seat_heaters") != 0,
        streaming_listener=lambda x, y: x.listen_SeatHeaterRearLeft(y),
        entity_registry_enabled_default=False,
        options=[
            OFF,
            LOW,
            MEDIUM,
            HIGH,
        ],
    ),
    TeslemetrySelectEntityDescription(
        key="climate_state_seat_heater_rear_center",
        select_fn=lambda api, level: api.remote_seat_heater_request(
            Seat.REAR_CENTER, level
        ),
        supported_fn=lambda data: data.get("vehicle_config_rear_seat_heaters") != 0,
        streaming_listener=lambda x, y: x.listen_SeatHeaterRearCenter(y),
        entity_registry_enabled_default=False,
        options=[
            OFF,
            LOW,
            MEDIUM,
            HIGH,
        ],
    ),
    TeslemetrySelectEntityDescription(
        key="climate_state_seat_heater_rear_right",
        select_fn=lambda api, level: api.remote_seat_heater_request(
            Seat.REAR_RIGHT, level
        ),
        supported_fn=lambda data: data.get("vehicle_config_rear_seat_heaters") != 0,
        streaming_listener=lambda x, y: x.listen_SeatHeaterRearRight(y),
        entity_registry_enabled_default=False,
        options=[
            OFF,
            LOW,
            MEDIUM,
            HIGH,
        ],
    ),
    TeslemetrySelectEntityDescription(
        key="climate_state_seat_heater_third_row_left",
        select_fn=lambda api, level: api.remote_seat_heater_request(
            Seat.THIRD_LEFT, level
        ),
        supported_fn=lambda self: self.get("vehicle_config_third_row_seats") != "None",
        entity_registry_enabled_default=False,
        options=[
            OFF,
            LOW,
            MEDIUM,
            HIGH,
        ],
    ),
    TeslemetrySelectEntityDescription(
        key="climate_state_seat_heater_third_row_right",
        select_fn=lambda api, level: api.remote_seat_heater_request(
            Seat.THIRD_RIGHT, level
        ),
        supported_fn=lambda self: self.get("vehicle_config_third_row_seats") != "None",
        entity_registry_enabled_default=False,
        options=[
            OFF,
            LOW,
            MEDIUM,
            HIGH,
        ],
    ),
    TeslemetrySelectEntityDescription(
        key="climate_state_steering_wheel_heat_level",
        select_fn=lambda api, level: api.remote_steering_wheel_heat_level_request(
            level
        ),
        streaming_listener=lambda x, y: x.listen_HvacSteeringWheelHeatLevel(y),
        options=[
            OFF,
            LOW,
            HIGH,
        ],
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TeslemetryConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Teslemetry select platform from a config entry."""

    async_add_entities(
        chain(
            (
                TeslemetryVehiclePollingSelectEntity(
                    vehicle, description, entry.runtime_data.scopes
                )
                if vehicle.api.pre2021
                or vehicle.firmware < "2024.26"
                or description.streaming_listener is None
                else TeslemetryStreamingSelectEntity(
                    vehicle, description, entry.runtime_data.scopes
                )
                for description in VEHICLE_DESCRIPTIONS
                for vehicle in entry.runtime_data.vehicles
                if description.supported_fn(vehicle.coordinator.data)
            ),
            (
                TeslemetryOperationSelectEntity(energysite, entry.runtime_data.scopes)
                for energysite in entry.runtime_data.energysites
                if energysite.info_coordinator.data.get("components_battery")
            ),
            (
                TeslemetryExportRuleSelectEntity(energysite, entry.runtime_data.scopes)
                for energysite in entry.runtime_data.energysites
                if energysite.info_coordinator.data.get("components_battery")
                and energysite.info_coordinator.data.get("components_solar")
            ),
        )
    )


class TeslemetrySelectEntity(TeslemetryRootEntity, SelectEntity):
    """Parent vehicle select entity class."""

    api: Vehicle
    entity_description: TeslemetrySelectEntityDescription
    _climate: bool = False

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        self.raise_for_scope(Scope.VEHICLE_CMDS)
        level = LEVEL[option]
        # AC must be on to turn on heaters
        if level and not self._climate:
            await handle_vehicle_command(self.api.auto_conditioning_start())
        await handle_vehicle_command(self.entity_description.select_fn(self.api, level))
        self._attr_current_option = option
        self.async_write_ha_state()


class TeslemetryVehiclePollingSelectEntity(
    TeslemetryVehiclePollingEntity, TeslemetrySelectEntity
):
    """Base polling vehicle select entity class."""

    def __init__(
        self,
        data: TeslemetryVehicleData,
        description: TeslemetrySelectEntityDescription,
        scopes: list[Scope],
    ) -> None:
        """Initialize the vehicle seat select entity."""
        self.entity_description = description
        self.scoped = Scope.VEHICLE_CMDS in scopes
        super().__init__(data, description.key)

    def _async_update_attrs(self) -> None:
        """Handle updated data from the coordinator."""
        self._climate = bool(self.get("climate_state_is_climate_on"))
        if not isinstance(self._value, int):
            self._attr_current_option = None
        else:
            self._attr_current_option = self.entity_description.options[self._value]


class TeslemetryStreamingSelectEntity(
    TeslemetryVehicleStreamEntity, TeslemetrySelectEntity, RestoreEntity
):
    """Base streaming vehicle select entity class."""

    def __init__(
        self,
        data: TeslemetryVehicleData,
        description: TeslemetrySelectEntityDescription,
        scopes: list[Scope],
    ) -> None:
        """Initialize the vehicle seat select entity."""
        self.entity_description = description
        self.scoped = Scope.VEHICLE_CMDS in scopes
        self._attr_current_option = None
        super().__init__(data, description.key)

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()

        # Restore state
        if (state := await self.async_get_last_state()) is not None:
            if state.state in self.entity_description.options:
                self._attr_current_option = state.state

        # Listen for streaming data
        assert self.entity_description.streaming_listener is not None
        self.async_on_remove(
            self.entity_description.streaming_listener(
                self.vehicle.stream_vehicle, self._value_callback
            )
        )

        self.async_on_remove(
            self.vehicle.stream_vehicle.listen_HvacACEnabled(self._climate_callback)
        )

    def _value_callback(self, value: int | None) -> None:
        """Update the value of the entity."""
        if value is None:
            self._attr_current_option = None
        else:
            self._attr_current_option = self.entity_description.options[value]
        self.async_write_ha_state()

    def _climate_callback(self, value: bool | None) -> None:
        """Update the value of the entity."""
        self._climate = bool(value)


class TeslemetryOperationSelectEntity(TeslemetryEnergyInfoEntity, SelectEntity):
    """Select entity for operation mode select entities."""

    _attr_options: list[str] = [
        EnergyOperationMode.AUTONOMOUS,
        EnergyOperationMode.BACKUP,
        EnergyOperationMode.SELF_CONSUMPTION,
    ]

    def __init__(
        self,
        data: TeslemetryEnergyData,
        scopes: list[Scope],
    ) -> None:
        """Initialize the operation mode select entity."""
        self.scoped = Scope.ENERGY_CMDS in scopes
        super().__init__(data, "default_real_mode")

    def _async_update_attrs(self) -> None:
        """Update the attributes of the entity."""
        self._attr_current_option = self._value

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        self.raise_for_scope(Scope.ENERGY_CMDS)
        await handle_command(self.api.operation(option))
        self._attr_current_option = option
        self.async_write_ha_state()


class TeslemetryExportRuleSelectEntity(TeslemetryEnergyInfoEntity, SelectEntity):
    """Select entity for export rules select entities."""

    _attr_options: list[str] = [
        EnergyExportMode.NEVER,
        EnergyExportMode.BATTERY_OK,
        EnergyExportMode.PV_ONLY,
    ]

    def __init__(
        self,
        data: TeslemetryEnergyData,
        scopes: list[Scope],
    ) -> None:
        """Initialize the export rules select entity."""
        self.scoped = Scope.ENERGY_CMDS in scopes
        super().__init__(data, "components_customer_preferred_export_rule")

    def _async_update_attrs(self) -> None:
        """Update the attributes of the entity."""
        self._attr_current_option = self.get(self.key, EnergyExportMode.NEVER.value)

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        self.raise_for_scope(Scope.ENERGY_CMDS)
        await handle_command(
            self.api.grid_import_export(customer_preferred_export_rule=option)
        )
        self._attr_current_option = option
        self.async_write_ha_state()
