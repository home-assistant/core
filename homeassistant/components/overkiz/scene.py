"""Support for Overkiz scenes."""

from typing import Any, override

from pyoverkiz.client import OverkizClient
from pyoverkiz.models import PersistedActionGroup

from homeassistant.components.scene import Scene
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import OverkizDataConfigEntry

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OverkizDataConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Overkiz scenes from a config entry."""
    data = entry.runtime_data

    async_add_entities(
        OverkizScene(scene, data.coordinator.client) for scene in data.scenarios
    )


class OverkizScene(Scene):
    """Representation of an Overkiz Scene."""

    _attr_has_entity_name = True

    def __init__(self, scenario: PersistedActionGroup, client: OverkizClient) -> None:
        """Initialize the scene."""
        self.scenario = scenario
        self.client = client
        self._attr_name = self.scenario.label
        self._attr_unique_id = self.scenario.oid

    @override
    async def async_activate(self, **kwargs: Any) -> None:
        """Activate the scene."""
        await self.client.execute_persisted_action_group(self.scenario.oid)
