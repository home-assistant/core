"""Vera tests."""
from unittest.mock import MagicMock

from pyvera import VeraScene

from homeassistant.core import HomeAssistant

from .common import ComponentFactory


async def test_scene(
    hass: HomeAssistant, vera_component_factory: ComponentFactory
) -> None:
    """Test function."""
    vera_scene = MagicMock(spec=VeraScene)  # type: VeraScene
    vera_scene.scene_id = 1
    vera_scene.name = "dev1"
    entity_id = "scene.dev1_1"

    await vera_component_factory.configure_component(
        hass=hass, scenes=(vera_scene,),
    )

    await hass.services.async_call(
        "scene", "turn_on", {"entity_id": entity_id},
    )
    await hass.async_block_till_done()
