"""Number platform for the Tewke integration.

Exposes the energy override as a settable number entity (watts).
Setting a value activates the override; setting it to 0 clears it.
"""

from typing import TYPE_CHECKING

from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
from homeassistant.const import UnitOfPower

from .entity import TewkeEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import TewkeCoordinator
    from .data import TewkeConfigEntry


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: TewkeConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Tewke number entities from a config entry."""
    coordinator = entry.runtime_data.coordinator

    if coordinator.data.get("energy_override") is not None:
        async_add_entities([TewkeEnergyOverrideNumber(coordinator=coordinator)])


class TewkeEnergyOverrideNumber(TewkeEntity, NumberEntity):
    """Number entity to get/set the Tewke energy override.

    A positive value (watts) activates the override; setting 0 clears it.
    """

    _attr_name = "Energy Override"
    _attr_device_class = NumberDeviceClass.POWER
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_mode = NumberMode.BOX
    _attr_entity_registry_enabled_default = False
    _attr_native_min_value = 0
    _attr_native_max_value = 1_000_000
    _attr_native_step = 0.1

    def __init__(self, coordinator: TewkeCoordinator) -> None:
        """Initialise the energy override number entity."""
        super().__init__(coordinator)
        hardware_id = coordinator.data["config"].hardware_id
        self._attr_unique_id = f"{hardware_id}_energy_override"

    @property
    def native_value(self) -> float | None:
        """Return the current override value in watts, or None when inactive."""
        energy_override = self.coordinator.data.get("energy_override")
        if energy_override is None or not energy_override.active:
            return None
        return energy_override.override

    async def async_set_native_value(self, value: float) -> None:
        """Set or clear the energy override.

        Pass 0 to clear the override; any positive value activates it.
        """
        tap = self.coordinator.config_entry.runtime_data.tap
        override_value: float | None = value if value > 0 else None
        updated = await tap.set_energy_override(override_value)

        current = self.coordinator.data
        self.coordinator.async_set_updated_data({**current, "energy_override": updated})
