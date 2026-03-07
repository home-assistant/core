"""Support for Velux select entities."""

from __future__ import annotations

from pyvlx import OpeningDevice
from pyvlx.const import Velocity

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import VeluxConfigEntry
from .entity import VeluxEntity

PARALLEL_UPDATES = 1

VELOCITY_MAP = {
    "default": Velocity.DEFAULT,
    "silent": Velocity.SILENT,
    "fast": Velocity.FAST,
}
INVERSE_VELOCITY_MAP = {v: k for k, v in VELOCITY_MAP.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: VeluxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up select entities for Velux platform."""
    pyvlx = config_entry.runtime_data
    entities = [
        VeluxVelocitySelect(node, config_entry.entry_id)
        for node in pyvlx.nodes
        if isinstance(node, OpeningDevice)
    ]
    async_add_entities(entities)


class VeluxVelocitySelect(VeluxEntity, SelectEntity, RestoreEntity):
    """Representation of a Velux velocity select entity."""

    _attr_translation_key = "velocity"
    _attr_options = list(VELOCITY_MAP)
    _attr_entity_category = EntityCategory.CONFIG
    _attr_entity_registry_enabled_default = False
    node: OpeningDevice

    def __init__(self, node: OpeningDevice, config_entry_id: str) -> None:
        """Initialize the Velux velocity select."""
        super().__init__(node, config_entry_id)
        self._attr_unique_id = f"{self._attr_unique_id}_velocity"

    async def async_added_to_hass(self) -> None:
        """Restore state."""
        state = await self.async_get_last_state()
        if state and state.state in VELOCITY_MAP:
            self._update_velocity(state.state)

    def _update_velocity(self, option: str) -> None:
        """Update node velocity based on string option."""
        velocity = VELOCITY_MAP[option]
        if velocity == Velocity.DEFAULT:
            self.node.use_default_velocity = False
            self.node.default_velocity = Velocity.DEFAULT
        else:
            self.node.use_default_velocity = True
            self.node.default_velocity = velocity

    @property
    def current_option(self) -> str | None:
        """Return the current selected option."""
        if not self.node.use_default_velocity:
            return "default"
        return INVERSE_VELOCITY_MAP.get(self.node.default_velocity, "default")

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        self._update_velocity(option)
        self.async_write_ha_state()
