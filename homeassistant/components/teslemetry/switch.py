"""Switch platform for Teslemetry integration."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from itertools import chain
from typing import Any

from tesla_fleet_api.const import AutoSeat, Scope
from tesla_fleet_api.teslemetry.vehicles import TeslemetryVehicle
from teslemetry_stream import TeslemetryStreamVehicle

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import StateType

from . import TeslemetryConfigEntry
from .entity import (
    TeslemetryEnergyInfoEntity,
    TeslemetryRootEntity,
    TeslemetryVehicleEntity,
    TeslemetryVehicleStreamEntity,
)
from .helpers import handle_command, handle_vehicle_command
from .models import TeslemetryEnergyData, TeslemetryVehicleData

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class TeslemetrySwitchEntityDescription(SwitchEntityDescription):
    """Describes Teslemetry Switch entity."""

    on_func: Callable[[TeslemetryVehicle], Awaitable[dict[str, Any]]]
    off_func: Callable[[TeslemetryVehicle], Awaitable[dict[str, Any]]]
    scopes: list[Scope]
    value_func: Callable[[StateType], bool] = bool
    streaming_listener: Callable[
        [TeslemetryStreamVehicle, Callable[[bool | None], None]],
        Callable[[], None],
    ]
    streaming_firmware: str = "2024.26"
    unique_id: str | None = None


VEHICLE_DESCRIPTIONS: tuple[TeslemetrySwitchEntityDescription, ...] = (
    TeslemetrySwitchEntityDescription(
        key="vehicle_state_sentry_mode",
        streaming_listener=lambda vehicle, callback: vehicle.listen_SentryMode(
            lambda value: callback(None) if value is None else callback(value != "Off")
        ),
        on_func=lambda api: api.set_sentry_mode(on=True),
        off_func=lambda api: api.set_sentry_mode(on=False),
        scopes=[Scope.VEHICLE_CMDS],
    ),
    TeslemetrySwitchEntityDescription(
        key="climate_state_auto_seat_climate_left",
        streaming_listener=lambda vehicle, callback: vehicle.listen_AutoSeatClimateLeft(
            callback
        ),
        on_func=lambda api: api.remote_auto_seat_climate_request(
            AutoSeat.FRONT_LEFT, True
        ),
        off_func=lambda api: api.remote_auto_seat_climate_request(
            AutoSeat.FRONT_LEFT, False
        ),
        scopes=[Scope.VEHICLE_CMDS],
    ),
    TeslemetrySwitchEntityDescription(
        key="climate_state_auto_seat_climate_right",
        streaming_listener=lambda vehicle,
        callback: vehicle.listen_AutoSeatClimateRight(callback),
        on_func=lambda api: api.remote_auto_seat_climate_request(
            AutoSeat.FRONT_RIGHT, True
        ),
        off_func=lambda api: api.remote_auto_seat_climate_request(
            AutoSeat.FRONT_RIGHT, False
        ),
        scopes=[Scope.VEHICLE_CMDS],
    ),
    TeslemetrySwitchEntityDescription(
        key="climate_state_auto_steering_wheel_heat",
        streaming_listener=lambda vehicle,
        callback: vehicle.listen_HvacSteeringWheelHeatAuto(callback),
        on_func=lambda api: api.remote_auto_steering_wheel_heat_climate_request(
            on=True
        ),
        off_func=lambda api: api.remote_auto_steering_wheel_heat_climate_request(
            on=False
        ),
        scopes=[Scope.VEHICLE_CMDS],
    ),
    TeslemetrySwitchEntityDescription(
        key="climate_state_defrost_mode",
        streaming_listener=lambda vehicle, callback: vehicle.listen_DefrostMode(
            lambda value: callback(value) if value is None else callback(value != "Off")
        ),
        on_func=lambda api: api.set_preconditioning_max(on=True, manual_override=False),
        off_func=lambda api: api.set_preconditioning_max(
            on=False, manual_override=False
        ),
        scopes=[Scope.VEHICLE_CMDS],
    ),
    TeslemetrySwitchEntityDescription(
        key="charge_state_charging_state",
        unique_id="charge_state_user_charge_enable_request",
        value_func=lambda state: state in {"Starting", "Charging"},
        streaming_listener=lambda vehicle, callback: vehicle.listen_DetailedChargeState(
            lambda value: callback(value)
            if value is None
            else callback(value in {"Starting", "Charging"})
        ),
        on_func=lambda api: api.charge_start(),
        off_func=lambda api: api.charge_stop(),
        scopes=[Scope.VEHICLE_CMDS, Scope.VEHICLE_CHARGING_CMDS],
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TeslemetryConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Teslemetry Switch platform from a config entry."""

    async_add_entities(
        chain(
            (
                TeslemetryPollingVehicleSwitchEntity(
                    vehicle, description, entry.runtime_data.scopes
                )
                if vehicle.api.pre2021
                or vehicle.firmware < description.streaming_firmware
                else TeslemetryStreamingVehicleSwitchEntity(
                    vehicle, description, entry.runtime_data.scopes
                )
                for vehicle in entry.runtime_data.vehicles
                for description in VEHICLE_DESCRIPTIONS
            ),
            (
                TeslemetryChargeFromGridSwitchEntity(
                    energysite,
                    entry.runtime_data.scopes,
                )
                for energysite in entry.runtime_data.energysites
                if energysite.info_coordinator.data.get("components_battery")
                and energysite.info_coordinator.data.get("components_solar")
            ),
            (
                TeslemetryStormModeSwitchEntity(energysite, entry.runtime_data.scopes)
                for energysite in entry.runtime_data.energysites
                if energysite.info_coordinator.data.get("components_storm_mode_capable")
            ),
        )
    )


class TeslemetryVehicleSwitchEntity(TeslemetryRootEntity, SwitchEntity):
    """Base class for all Teslemetry switch entities."""

    _attr_device_class = SwitchDeviceClass.SWITCH
    entity_description: TeslemetrySwitchEntityDescription

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the Switch."""
        self.raise_for_scope(self.entity_description.scopes[0])
        await handle_vehicle_command(self.entity_description.on_func(self.api))
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the Switch."""
        self.raise_for_scope(self.entity_description.scopes[0])
        await handle_vehicle_command(self.entity_description.off_func(self.api))
        self._attr_is_on = False
        self.async_write_ha_state()


class TeslemetryPollingVehicleSwitchEntity(
    TeslemetryVehicleEntity, TeslemetryVehicleSwitchEntity
):
    """Base class for Teslemetry polling vehicle switch entities."""

    def __init__(
        self,
        data: TeslemetryVehicleData,
        description: TeslemetrySwitchEntityDescription,
        scopes: list[Scope],
    ) -> None:
        """Initialize the Switch."""
        self.entity_description = description
        self.scoped = any(scope in scopes for scope in description.scopes)
        super().__init__(data, description.key)
        if description.unique_id:
            self._attr_unique_id = f"{data.vin}-{description.unique_id}"

    def _async_update_attrs(self) -> None:
        """Update the attributes of the sensor."""
        self._attr_is_on = (
            None
            if self._value is None
            else self.entity_description.value_func(self._value)
        )


class TeslemetryStreamingVehicleSwitchEntity(
    TeslemetryVehicleStreamEntity, TeslemetryVehicleSwitchEntity, RestoreEntity
):
    """Base class for Teslemetry streaming vehicle switch entities."""

    def __init__(
        self,
        data: TeslemetryVehicleData,
        description: TeslemetrySwitchEntityDescription,
        scopes: list[Scope],
    ) -> None:
        """Initialize the Switch."""

        self.entity_description = description
        self.scoped = any(scope in scopes for scope in description.scopes)
        super().__init__(data, description.key)
        if description.unique_id:
            self._attr_unique_id = f"{data.vin}-{description.unique_id}"

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()

        # Restore previous state
        if (state := await self.async_get_last_state()) is not None:
            if state.state == "on":
                self._attr_is_on = True
            elif state.state == "off":
                self._attr_is_on = False

        # Add listener
        self.async_on_remove(
            self.entity_description.streaming_listener(
                self.vehicle.stream_vehicle, self._value_callback
            )
        )

    def _value_callback(self, value: bool | None) -> None:
        """Update the value of the entity."""
        self._attr_is_on = value
        self.async_write_ha_state()


class TeslemetryChargeFromGridSwitchEntity(TeslemetryEnergyInfoEntity, SwitchEntity):
    """Entity class for Charge From Grid switch."""

    _attr_device_class = SwitchDeviceClass.SWITCH

    def __init__(
        self,
        data: TeslemetryEnergyData,
        scopes: list[Scope],
    ) -> None:
        """Initialize the Switch."""
        self.scoped = Scope.ENERGY_CMDS in scopes
        super().__init__(
            data, "components_disallow_charge_from_grid_with_solar_installed"
        )

    def _async_update_attrs(self) -> None:
        """Update the attributes of the entity."""
        # When disallow_charge_from_grid_with_solar_installed is missing, its Off.
        # But this sensor is flipped to match how the Tesla app works.
        self._attr_is_on = not self.get(self.key, False)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the Switch."""
        self.raise_for_scope(Scope.ENERGY_CMDS)
        await handle_command(
            self.api.grid_import_export(
                disallow_charge_from_grid_with_solar_installed=False
            )
        )
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the Switch."""
        self.raise_for_scope(Scope.ENERGY_CMDS)
        await handle_command(
            self.api.grid_import_export(
                disallow_charge_from_grid_with_solar_installed=True
            )
        )
        self._attr_is_on = False
        self.async_write_ha_state()


class TeslemetryStormModeSwitchEntity(TeslemetryEnergyInfoEntity, SwitchEntity):
    """Entity class for Storm Mode switch."""

    _attr_device_class = SwitchDeviceClass.SWITCH

    def __init__(
        self,
        data: TeslemetryEnergyData,
        scopes: list[Scope],
    ) -> None:
        """Initialize the Switch."""
        super().__init__(data, "user_settings_storm_mode_enabled")
        self.scoped = Scope.ENERGY_CMDS in scopes

    def _async_update_attrs(self) -> None:
        """Update the attributes of the sensor."""
        self._attr_available = self._value is not None
        self._attr_is_on = bool(self._value)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the Switch."""
        self.raise_for_scope(Scope.ENERGY_CMDS)
        await handle_command(self.api.storm_mode(enabled=True))
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the Switch."""
        self.raise_for_scope(Scope.ENERGY_CMDS)
        await handle_command(self.api.storm_mode(enabled=False))
        self._attr_is_on = False
        self.async_write_ha_state()
