"""Select platform for the Tado integration."""

import logging
from typing import override

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import TYPE_HEATING
from .coordinator import TadoConfigEntry, TadoDataUpdateCoordinator
from .entity import TadoZoneEntity

_LOGGER = logging.getLogger(__name__)

NO_HEATING_CIRCUIT_OPTION = "no_heating_circuit"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TadoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Tado select platform."""
    coordinator = entry.runtime_data

    if not coordinator.heating_circuits:
        return

    async_add_entities(
        TadoHeatingCircuitSelectEntity(coordinator, zone["name"], zone["id"])
        for zone in coordinator.zones
        if zone["type"] == TYPE_HEATING
    )


class TadoHeatingCircuitSelectEntity(TadoZoneEntity, SelectEntity):
    """Representation of the heating circuit assigned to a Tado zone."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "heating_circuit"

    def __init__(
        self,
        coordinator: TadoDataUpdateCoordinator,
        zone_name: str,
        zone_id: int,
    ) -> None:
        """Initialize the Tado heating circuit select entity."""
        super().__init__(zone_name, coordinator.home_id, zone_id, coordinator)

        self._attr_unique_id = f"{zone_id} {coordinator.home_id} heating_circuit"
        self._attr_options = [
            NO_HEATING_CIRCUIT_OPTION,
            *coordinator.heating_circuits,
        ]
        self._async_update_callback()

    @override
    async def async_select_option(self, option: str) -> None:
        """Assign the selected heating circuit to this zone."""
        circuit_number = None
        if option != NO_HEATING_CIRCUIT_OPTION:
            circuit_number = self.coordinator.heating_circuits[option]["number"]

        await self.coordinator.set_heating_circuit(self.zone_id, circuit_number)
        self._async_update_callback()
        self.async_write_ha_state()

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._async_update_callback()
        super()._handle_coordinator_update()

    @callback
    def _async_update_callback(self) -> None:
        """Resolve the circuit number currently assigned to this zone."""
        circuit_number = (
            self.coordinator.data["zone_control"]
            .get(self.zone_id, {})
            .get("heatingCircuit")
        )
        if circuit_number is None:
            self._attr_current_option = NO_HEATING_CIRCUIT_OPTION
            return

        for serial, circuit in self.coordinator.heating_circuits.items():
            if circuit["number"] == circuit_number:
                self._attr_current_option = serial
                return

        _LOGGER.debug(
            "Heating circuit %s of zone %s is not in the list of circuits",
            circuit_number,
            self.zone_name,
        )
        self._attr_current_option = None
