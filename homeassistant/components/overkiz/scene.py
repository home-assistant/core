"""Support for Overkiz scenes."""

from __future__ import annotations

from typing import Any

from pyoverkiz.client import OverkizClient
from pyoverkiz.models import Scenario

from homeassistant.components.scene import Scene
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HomeAssistantOverkizData
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Overkiz scenes from a config entry."""
    data: HomeAssistantOverkizData = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        OverkizScene(scene, data.coordinator.client) for scene in data.scenarios
    )


class OverkizScene(Scene):
    """Representation of an Overkiz Scene."""

    def __init__(self, scenario: Scenario, client: OverkizClient) -> None:
        """Initialize the scene."""
        self.scenario = scenario
        self.client = client
        self._attr_name = self.scenario.label
        self._attr_unique_id = self.scenario.oid

    async def async_activate(self, **kwargs: Any) -> None:
        """Activate the scene."""
        await self.client.execute_scenario(self.scenario.oid)
