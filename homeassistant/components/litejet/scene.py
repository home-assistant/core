"""Support for LiteJet scenes."""
import logging
from typing import Any

from pylitejet import LiteJet, LiteJetError

from homeassistant.components.scene import Scene
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

ATTR_NUMBER = "number"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up entry."""

    system: LiteJet = hass.data[DOMAIN]

    entities = []
    for i in system.scenes():
        name = await system.get_scene_name(i)
        entities.append(LiteJetScene(config_entry.entry_id, system, i, name))

    async_add_entities(entities, True)


class LiteJetScene(Scene):
    """Representation of a single LiteJet scene."""

    def __init__(self, entry_id, lj: LiteJet, i, name):  # pylint: disable=invalid-name
        """Initialize the scene."""
        self._lj = lj
        self._index = i
        self._attr_unique_id = f"{entry_id}_{i}"
        self._attr_name = name

    async def async_added_to_hass(self) -> None:
        """Run when this Entity has been added to HA."""
        self._lj.on_connected_changed(self._on_connected_changed)

    async def async_will_remove_from_hass(self) -> None:
        """Entity being removed from hass."""
        self._lj.unsubscribe(self._on_connected_changed)

    def _on_connected_changed(self, connected: bool, reason: str) -> None:
        self._attr_available = connected
        self.schedule_update_ha_state()

    @property
    def extra_state_attributes(self):
        """Return the device-specific state attributes."""
        return {ATTR_NUMBER: self._index}

    async def async_activate(self, **kwargs: Any) -> None:
        """Activate the scene."""
        try:
            await self._lj.activate_scene(self._index)
        except LiteJetError as exc:
            raise HomeAssistantError() from exc

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Scenes are only enabled by explicit user choice."""
        return False
