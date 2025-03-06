"""Select platform for Tessie integration."""

from __future__ import annotations

from itertools import chain

from tesla_fleet_api.const import EnergyExportMode, EnergyOperationMode
from tessie_api import set_seat_cool, set_seat_heat

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import TessieConfigEntry
from .const import TessieSeatCoolerOptions, TessieSeatHeaterOptions
from .entity import TessieEnergyEntity, TessieEntity
from .helpers import handle_command
from .models import TessieEnergyData

SEAT_HEATERS = {
    "climate_state_seat_heater_left": "front_left",
    "climate_state_seat_heater_right": "front_right",
    "climate_state_seat_heater_rear_left": "rear_left",
    "climate_state_seat_heater_rear_center": "rear_center",
    "climate_state_seat_heater_rear_right": "rear_right",
    "climate_state_seat_heater_third_row_left": "third_row_left",
    "climate_state_seat_heater_third_row_right": "third_row_right",
}

SEAT_COOLERS = {
    "climate_state_seat_fan_front_left": "front_left",
    "climate_state_seat_fan_front_right": "front_right",
}

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TessieConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Tessie select platform from a config entry."""

    async_add_entities(
        chain(
            (
                TessieSeatHeaterSelectEntity(vehicle, key)
                for vehicle in entry.runtime_data.vehicles
                for key in SEAT_HEATERS
                if key
                in vehicle.data_coordinator.data  # not all vehicles have rear center or third row
            ),
            (
                TessieSeatCoolerSelectEntity(vehicle, key)
                for vehicle in entry.runtime_data.vehicles
                for key in SEAT_COOLERS
                if key
                in vehicle.data_coordinator.data  # not all vehicles have ventilated seats
            ),
            (
                TessieOperationSelectEntity(energysite)
                for energysite in entry.runtime_data.energysites
                if energysite.info_coordinator.data.get("components_battery")
            ),
            (
                TessieExportRuleSelectEntity(energysite)
                for energysite in entry.runtime_data.energysites
                if energysite.info_coordinator.data.get("components_battery")
                and energysite.info_coordinator.data.get("components_solar")
            ),
        )
    )


class TessieSeatHeaterSelectEntity(TessieEntity, SelectEntity):
    """Select entity for current charge."""

    _attr_options = [
        TessieSeatHeaterOptions.OFF,
        TessieSeatHeaterOptions.LOW,
        TessieSeatHeaterOptions.MEDIUM,
        TessieSeatHeaterOptions.HIGH,
    ]

    @property
    def current_option(self) -> str | None:
        """Return the current selected option."""
        return self._attr_options[self._value]

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        level = self._attr_options.index(option)
        await self.run(set_seat_heat, seat=SEAT_HEATERS[self.key], level=level)
        self.set((self.key, level))


class TessieSeatCoolerSelectEntity(TessieEntity, SelectEntity):
    """Select entity for cooled seat."""

    _attr_options = [
        TessieSeatCoolerOptions.OFF,
        TessieSeatCoolerOptions.LOW,
        TessieSeatCoolerOptions.MEDIUM,
        TessieSeatCoolerOptions.HIGH,
    ]

    @property
    def current_option(self) -> str | None:
        """Return the current selected option."""
        return self._attr_options[self._value]

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        level = self._attr_options.index(option)
        await self.run(set_seat_cool, seat=SEAT_COOLERS[self.key], level=level)
        self.set((self.key, level))


class TessieOperationSelectEntity(TessieEnergyEntity, SelectEntity):
    """Select entity for operation mode select entities."""

    _attr_options: list[str] = [
        EnergyOperationMode.AUTONOMOUS,
        EnergyOperationMode.BACKUP,
        EnergyOperationMode.SELF_CONSUMPTION,
    ]

    def __init__(
        self,
        data: TessieEnergyData,
    ) -> None:
        """Initialize the operation mode select entity."""
        super().__init__(data, data.info_coordinator, "default_real_mode")

    def _async_update_attrs(self) -> None:
        """Update the attributes of the entity."""
        self._attr_current_option = self._value

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        await handle_command(self.api.operation(option))
        self._attr_current_option = option
        self.async_write_ha_state()


class TessieExportRuleSelectEntity(TessieEnergyEntity, SelectEntity):
    """Select entity for export rules select entities."""

    _attr_options: list[str] = [
        EnergyExportMode.NEVER,
        EnergyExportMode.BATTERY_OK,
        EnergyExportMode.PV_ONLY,
    ]

    def __init__(
        self,
        data: TessieEnergyData,
    ) -> None:
        """Initialize the export rules select entity."""
        super().__init__(
            data, data.info_coordinator, "components_customer_preferred_export_rule"
        )

    def _async_update_attrs(self) -> None:
        """Update the attributes of the entity."""
        self._attr_current_option = self.get(self.key, EnergyExportMode.NEVER.value)

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        await handle_command(self.api.grid_import_export(option))
        self._attr_current_option = option
        self.async_write_ha_state()
