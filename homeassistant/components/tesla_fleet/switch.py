"""Switch platform for Tesla Fleet integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from itertools import chain
from typing import Any

from tesla_fleet_api.const import Scope, Seat

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import TeslaFleetConfigEntry
from .entity import TeslaFleetEnergyInfoEntity, TeslaFleetVehicleEntity
from .helpers import handle_command, handle_vehicle_command
from .models import TeslaFleetEnergyData, TeslaFleetVehicleData

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class TeslaFleetSwitchEntityDescription(SwitchEntityDescription):
    """Describes TeslaFleet Switch entity."""

    on_func: Callable
    off_func: Callable
    scopes: list[Scope]


VEHICLE_DESCRIPTIONS: tuple[TeslaFleetSwitchEntityDescription, ...] = (
    TeslaFleetSwitchEntityDescription(
        key="vehicle_state_sentry_mode",
        on_func=lambda api: api.set_sentry_mode(on=True),
        off_func=lambda api: api.set_sentry_mode(on=False),
        scopes=[Scope.VEHICLE_CMDS],
    ),
    TeslaFleetSwitchEntityDescription(
        key="climate_state_auto_seat_climate_left",
        on_func=lambda api: api.remote_auto_seat_climate_request(Seat.FRONT_LEFT, True),
        off_func=lambda api: api.remote_auto_seat_climate_request(
            Seat.FRONT_LEFT, False
        ),
        scopes=[Scope.VEHICLE_CMDS],
    ),
    TeslaFleetSwitchEntityDescription(
        key="climate_state_auto_seat_climate_right",
        on_func=lambda api: api.remote_auto_seat_climate_request(
            Seat.FRONT_RIGHT, True
        ),
        off_func=lambda api: api.remote_auto_seat_climate_request(
            Seat.FRONT_RIGHT, False
        ),
        scopes=[Scope.VEHICLE_CMDS],
    ),
    TeslaFleetSwitchEntityDescription(
        key="climate_state_auto_steering_wheel_heat",
        on_func=lambda api: api.remote_auto_steering_wheel_heat_climate_request(
            on=True
        ),
        off_func=lambda api: api.remote_auto_steering_wheel_heat_climate_request(
            on=False
        ),
        scopes=[Scope.VEHICLE_CMDS],
    ),
    TeslaFleetSwitchEntityDescription(
        key="climate_state_defrost_mode",
        on_func=lambda api: api.set_preconditioning_max(on=True, manual_override=False),
        off_func=lambda api: api.set_preconditioning_max(
            on=False, manual_override=False
        ),
        scopes=[Scope.VEHICLE_CMDS],
    ),
)

VEHICLE_CHARGE_DESCRIPTION = TeslaFleetSwitchEntityDescription(
    key="charge_state_user_charge_enable_request",
    on_func=lambda api: api.charge_start(),
    off_func=lambda api: api.charge_stop(),
    scopes=[Scope.VEHICLE_CHARGING_CMDS, Scope.VEHICLE_CMDS],
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TeslaFleetConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the TeslaFleet Switch platform from a config entry."""

    async_add_entities(
        chain(
            (
                TeslaFleetVehicleSwitchEntity(
                    vehicle, description, entry.runtime_data.scopes
                )
                for vehicle in entry.runtime_data.vehicles
                for description in VEHICLE_DESCRIPTIONS
            ),
            (
                TeslaFleetChargeSwitchEntity(
                    vehicle, VEHICLE_CHARGE_DESCRIPTION, entry.runtime_data.scopes
                )
                for vehicle in entry.runtime_data.vehicles
            ),
            (
                TeslaFleetChargeFromGridSwitchEntity(
                    energysite,
                    entry.runtime_data.scopes,
                )
                for energysite in entry.runtime_data.energysites
                if energysite.info_coordinator.data.get("components_battery")
                and energysite.info_coordinator.data.get("components_solar")
            ),
            (
                TeslaFleetStormModeSwitchEntity(energysite, entry.runtime_data.scopes)
                for energysite in entry.runtime_data.energysites
                if energysite.info_coordinator.data.get("components_storm_mode_capable")
            ),
        )
    )


class TeslaFleetSwitchEntity(SwitchEntity):
    """Base class for all TeslaFleet switch entities."""

    _attr_device_class = SwitchDeviceClass.SWITCH
    entity_description: TeslaFleetSwitchEntityDescription


class TeslaFleetVehicleSwitchEntity(TeslaFleetVehicleEntity, TeslaFleetSwitchEntity):
    """Base class for TeslaFleet vehicle switch entities."""

    def __init__(
        self,
        data: TeslaFleetVehicleData,
        description: TeslaFleetSwitchEntityDescription,
        scopes: list[Scope],
    ) -> None:
        """Initialize the Switch."""
        super().__init__(data, description.key)
        self.entity_description = description
        self.scoped = any(scope in scopes for scope in description.scopes)

    def _async_update_attrs(self) -> None:
        """Update the attributes of the sensor."""
        if self._value is None:
            self._attr_is_on = None
        else:
            self._attr_is_on = bool(self._value)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the Switch."""
        self.raise_for_read_only(self.entity_description.scopes[0])
        await self.wake_up_if_asleep()
        await handle_vehicle_command(self.entity_description.on_func(self.api))
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the Switch."""
        self.raise_for_read_only(self.entity_description.scopes[0])
        await self.wake_up_if_asleep()
        await handle_vehicle_command(self.entity_description.off_func(self.api))
        self._attr_is_on = False
        self.async_write_ha_state()


class TeslaFleetChargeSwitchEntity(TeslaFleetVehicleSwitchEntity):
    """Entity class for TeslaFleet charge switch."""

    def _async_update_attrs(self) -> None:
        """Update the attributes of the entity."""
        if self._value is None:
            self._attr_is_on = self.get("charge_state_charge_enable_request")
        else:
            self._attr_is_on = self._value


class TeslaFleetChargeFromGridSwitchEntity(
    TeslaFleetEnergyInfoEntity, TeslaFleetSwitchEntity
):
    """Entity class for Charge From Grid switch."""

    def __init__(
        self,
        data: TeslaFleetEnergyData,
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
        self.raise_for_read_only(Scope.ENERGY_CMDS)
        await handle_command(
            self.api.grid_import_export(
                disallow_charge_from_grid_with_solar_installed=False
            )
        )
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the Switch."""
        self.raise_for_read_only(Scope.ENERGY_CMDS)
        await handle_command(
            self.api.grid_import_export(
                disallow_charge_from_grid_with_solar_installed=True
            )
        )
        self._attr_is_on = False
        self.async_write_ha_state()


class TeslaFleetStormModeSwitchEntity(
    TeslaFleetEnergyInfoEntity, TeslaFleetSwitchEntity
):
    """Entity class for Storm Mode switch."""

    def __init__(
        self,
        data: TeslaFleetEnergyData,
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
        self.raise_for_read_only(Scope.ENERGY_CMDS)
        await handle_command(self.api.storm_mode(enabled=True))
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the Switch."""
        self.raise_for_read_only(Scope.ENERGY_CMDS)
        await handle_command(self.api.storm_mode(enabled=False))
        self._attr_is_on = False
        self.async_write_ha_state()
