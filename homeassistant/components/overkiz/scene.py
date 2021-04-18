"""Support for Overkiz scenes."""
import logging
from typing import Any

from pyhoma.client import TahomaClient
from pyhoma.models import Scenario

from homeassistant.components.scene import DOMAIN as SCENE, Scene

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Overkiz scenes from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]

    entities = [
        OverkizScene(scene, coordinator.client) for scene in data["platforms"][SCENE]
    ]
    async_add_entities(entities)


class OverkizScene(Scene):
    """Representation of a Overkiz Scene."""

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
