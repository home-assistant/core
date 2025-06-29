"""Module for Tado select entities."""

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import TadoConfigEntry
from .entity import TadoDataUpdateCoordinator, TadoZoneEntity

_LOGGER = logging.getLogger(__name__)

TRANSLATABLE_NO_HEATING_CIRCUIT = "no_heating_circuit"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TadoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Tado select platform."""

    tado = entry.runtime_data.coordinator
    entities: list[SelectEntity] = [
        # Add heating circuit select
        TadoHeatingCircuitSelectEntity(tado, zone["name"], zone["id"])
        for zone in tado.zones
        if zone["type"] == "HEATING"
    ]

    async_add_entities(entities, True)


class TadoHeatingCircuitSelectEntity(TadoZoneEntity, SelectEntity):
    """Representation of a Tado heating circuit select entity."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_has_entity_name = True
    _attr_icon = "mdi:water-boiler"
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

        self._attr_options = []
        self._attr_current_option = None

    async def async_select_option(self, option: str) -> None:
        """Update the selected heating circuit."""
        heating_circuit_id = (
            None
            if option is TRANSLATABLE_NO_HEATING_CIRCUIT
            else self.coordinator.data["heating_circuits"].get(option, {}).get("number")
        )
        await self.coordinator.set_heating_circuit(self.zone_id, heating_circuit_id)
        await self.coordinator.async_request_refresh()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._async_update_callback()
        super()._handle_coordinator_update()

    @callback
    def _async_update_callback(self) -> None:
        """Handle update callbacks."""
        try:
            # Heating circuits list
            heating_circuits = self.coordinator.data["heating_circuits"].values()
            self._attr_options = [TRANSLATABLE_NO_HEATING_CIRCUIT]
            self._attr_options.extend(
                hc["driverShortSerialNo"] for hc in heating_circuits
            )

            # Current heating circuit
            zone_control = self.coordinator.data["zone_control"].get(self.zone_id)
            if zone_control and "heatingCircuit" in zone_control:
                heating_circuit_number = zone_control["heatingCircuit"]
                if heating_circuit_number is None:
                    self._attr_current_option = TRANSLATABLE_NO_HEATING_CIRCUIT
                else:
                    # Find heating circuit by driverShortSerialNo
                    heating_circuit = next(
                        (
                            hc
                            for hc in heating_circuits
                            if hc.get("number") == heating_circuit_number
                        ),
                        None,
                    )

                    if heating_circuit is None:
                        _LOGGER.error(
                            "Heating circuit with number %s not found for zone %s",
                            heating_circuit_number,
                            self.zone_name,
                        )
                        self._attr_current_option = TRANSLATABLE_NO_HEATING_CIRCUIT
                    else:
                        self._attr_current_option = heating_circuit.get(
                            "driverShortSerialNo"
                        )
        except KeyError:
            _LOGGER.error(
                "Could not update heating circuit info for zone %s",
                self.zone_name,
            )
