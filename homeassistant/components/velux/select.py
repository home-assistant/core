"""Support for Velux cover velocity selection."""

from __future__ import annotations

from pyvlx.const import Velocity
from pyvlx.opening_device import OpeningDevice

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import VeluxDataUpdateCoordinator
from .entity import VeluxCoordinatorEntity

VELOCITY_MAP = {
    velocity.name.lower(): velocity
    for velocity in Velocity
    if velocity != Velocity.NOT_AVAILABLE
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up select entities for Velux platform."""
    coordinator = config_entry.runtime_data  # Get coordinator
    module = hass.data[DOMAIN][config_entry.entry_id]  # Get pyvlx from existing pattern

    # Create select entities for all opening devices
    async_add_entities(
        VeluxCoverVelocitySelect(node, config_entry.entry_id, coordinator)
        for node in module.pyvlx.nodes
        if isinstance(node, OpeningDevice)
    )


class VeluxCoverVelocitySelect(VeluxCoordinatorEntity, SelectEntity):
    """Select entity for controlling Velux cover velocity."""

    _attr_has_entity_name = True
    _attr_translation_key = "cover_velocity"
    _attr_options = list(VELOCITY_MAP.keys())

    def __init__(
        self,
        node: OpeningDevice,
        config_entry_id: str,
        coordinator: VeluxDataUpdateCoordinator,
    ) -> None:
        """Initialize VeluxCoverVelocitySelect."""
        super().__init__(node, config_entry_id, coordinator)
        self._attr_unique_id = f"{self._attr_unique_id}_velocity"

    @property
    def current_option(self) -> str:
        """Return the currently selected velocity."""
        velocity = self.coordinator.get_velocity(str(self._attr_device_info))
        return velocity.name.lower()

    async def async_select_option(self, option: str) -> None:
        """Change the selected velocity option."""
        if option in VELOCITY_MAP:
            self.coordinator.set_velocity(
                str(self._attr_device_info), VELOCITY_MAP[option]
            )
