"""Vera tests."""
from unittest.mock import MagicMock

import pyvera as pv

from homeassistant.core import HomeAssistant

from .common import ComponentFactory, new_simple_controller_config


async def test_scene(
    hass: HomeAssistant, vera_component_factory: ComponentFactory
) -> None:
    """Test function."""
    vera_scene: pv.VeraScene = MagicMock(spec=pv.VeraScene)
    vera_scene.scene_id = 1
    vera_scene.vera_scene_id = vera_scene.scene_id
    vera_scene.name = "dev1"
    entity_id = "scene.dev1_1"

    await vera_component_factory.configure_component(
        hass=hass,
        controller_config=new_simple_controller_config(scenes=(vera_scene,)),
    )

    await hass.services.async_call(
        "scene",
        "turn_on",
        {"entity_id": entity_id},
    )
    await hass.async_block_till_done()
