"""Switch platform for Tessie integration."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from itertools import chain
from typing import Any

from tesla_fleet_api.tessie import Vehicle

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import TessieConfigEntry
from .entity import TessieEnergyEntity, TessieEntity
from .helpers import handle_command
from .models import TessieEnergyData, TessieVehicleData


@dataclass(frozen=True, kw_only=True)
class TessieSwitchEntityDescription(SwitchEntityDescription):
    """Describes Tessie Switch entity."""

    on_func: Callable[[Vehicle], Awaitable[dict]]
    off_func: Callable[[Vehicle], Awaitable[dict]]
    value_func: Callable[[StateType], bool] = bool
    unique_id: str | None = None


DESCRIPTIONS: tuple[TessieSwitchEntityDescription, ...] = (
    TessieSwitchEntityDescription(
        key="climate_state_defrost_mode",
        on_func=lambda api: api.start_max_defrost(),
        off_func=lambda api: api.stop_max_defrost(),
    ),
    TessieSwitchEntityDescription(
        key="vehicle_state_sentry_mode",
        on_func=lambda api: api.enable_sentry(),
        off_func=lambda api: api.disable_sentry(),
    ),
    TessieSwitchEntityDescription(
        key="vehicle_state_valet_mode",
        on_func=lambda api: api.enable_valet(),
        off_func=lambda api: api.disable_valet(),
    ),
    TessieSwitchEntityDescription(
        key="climate_state_steering_wheel_heater",
        on_func=lambda api: api.start_steering_wheel_heater(),
        off_func=lambda api: api.stop_steering_wheel_heater(),
    ),
    TessieSwitchEntityDescription(
        key="charge_state_charging_state",
        unique_id="charge_state_charge_enable_request",
        on_func=lambda api: api.start_charging(),
        off_func=lambda api: api.stop_charging(),
        value_func=lambda state: state in {"Starting", "Charging"},
    ),
)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TessieConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Tessie Switch platform from a config entry."""

    async_add_entities(
        chain(
            (
                TessieSwitchEntity(vehicle, description)
                for vehicle in entry.runtime_data.vehicles
                for description in DESCRIPTIONS
                if description.key in vehicle.data_coordinator.data
            ),
            (
                TessieChargeFromGridSwitchEntity(energysite)
                for energysite in entry.runtime_data.energysites
                if energysite.info_coordinator.data.get("components_battery")
                and energysite.info_coordinator.data.get("components_solar")
            ),
            (
                TessieStormModeSwitchEntity(energysite)
                for energysite in entry.runtime_data.energysites
                if energysite.info_coordinator.data.get("components_storm_mode_capable")
            ),
        )
    )


class TessieSwitchEntity(TessieEntity, SwitchEntity):
    """Base class for Tessie Switch."""

    _attr_device_class = SwitchDeviceClass.SWITCH
    entity_description: TessieSwitchEntityDescription

    def __init__(
        self,
        vehicle: TessieVehicleData,
        description: TessieSwitchEntityDescription,
    ) -> None:
        """Initialize the Switch."""
        self.entity_description = description
        super().__init__(vehicle, description.key)
        if description.unique_id:
            self._attr_unique_id = f"{vehicle.vin}-{description.unique_id}"

    @property
    def is_on(self) -> bool:
        """Return the state of the Switch."""
        return self.entity_description.value_func(self._value)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the Switch."""
        await self.run(self.entity_description.on_func(self.api))
        self.set((self.entity_description.key, True))

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the Switch."""
        await self.run(self.entity_description.off_func(self.api))
        self.set((self.entity_description.key, False))


class TessieChargeFromGridSwitchEntity(TessieEnergyEntity, SwitchEntity):
    """Entity class for Charge From Grid switch."""

    def __init__(
        self,
        data: TessieEnergyData,
    ) -> None:
        """Initialize the switch."""
        super().__init__(
            data,
            data.info_coordinator,
            "components_disallow_charge_from_grid_with_solar_installed",
        )

    def _async_update_attrs(self) -> None:
        """Update the attributes of the entity."""
        # When disallow_charge_from_grid_with_solar_installed is missing, its Off.
        # But this sensor is flipped to match how the Tesla app works.
        self._attr_is_on = not self.get(self.key, False)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the Switch."""
        await handle_command(
            self.api.grid_import_export(
                disallow_charge_from_grid_with_solar_installed=False
            )
        )
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the Switch."""
        await handle_command(
            self.api.grid_import_export(
                disallow_charge_from_grid_with_solar_installed=True
            )
        )
        self._attr_is_on = False
        self.async_write_ha_state()


class TessieStormModeSwitchEntity(TessieEnergyEntity, SwitchEntity):
    """Entity class for Storm Mode switch."""

    def __init__(
        self,
        data: TessieEnergyData,
    ) -> None:
        """Initialize the switch."""
        super().__init__(
            data, data.info_coordinator, "user_settings_storm_mode_enabled"
        )

    def _async_update_attrs(self) -> None:
        """Update the attributes of the sensor."""
        self._attr_available = self._value is not None
        self._attr_is_on = bool(self._value)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the Switch."""
        await handle_command(self.api.storm_mode(enabled=True))
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the Switch."""
        await handle_command(self.api.storm_mode(enabled=False))
        self._attr_is_on = False
        self.async_write_ha_state()
