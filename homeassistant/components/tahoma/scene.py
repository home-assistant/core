"""Support for Tahoma scenes."""
from typing import Any

from pyhoma.client import TahomaClient
from pyhoma.models import Scenario

from homeassistant.components.scene import DOMAIN as SCENE, Scene

from .const import DOMAIN


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the TaHoma scenes from a config entry."""
    data = hass.data[DOMAIN]
    coordinator = data["coordinator"]

    entities = [
        TahomaScene(scene, coordinator.client) for scene in data["entities"].get(SCENE)
    ]
    async_add_entities(entities)


class TahomaScene(Scene):
    """Representation of a TaHoma scene entity."""

    def __init__(self, scenario: Scenario, client: TahomaClient):
        """Initialize the scene."""
        self.scenario = scenario
        self.client = client

    async def async_activate(self, **_: Any) -> None:
        """Activate the scene."""
        await self.client.execute_scenario(self.scenario.oid)

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self.scenario.oid

    @property
    def name(self):
        """Return the name of the scene."""
        return self.scenario.label
