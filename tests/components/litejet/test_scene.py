"""The tests for the litejet component."""
from homeassistant.components import scene
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_ON
from homeassistant.helpers import entity_registry as er

from . import async_init_integration

ENTITY_SCENE = "scene.mock_scene_1"
ENTITY_SCENE_NUMBER = 1
ENTITY_OTHER_SCENE = "scene.mock_scene_2"
ENTITY_OTHER_SCENE_NUMBER = 2


async def test_disabled_by_default(hass, mock_litejet):
    """Test the scene is disabled by default."""
    await async_init_integration(hass)

    registry = er.async_get(hass)

    state = hass.states.get(ENTITY_SCENE)
    assert state is None

    entry = registry.async_get(ENTITY_SCENE)
    assert entry
    assert entry.disabled
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION


async def test_activate(hass, mock_litejet):
    """Test activating the scene."""

    await async_init_integration(hass, use_scene=True)

    state = hass.states.get(ENTITY_SCENE)
    assert state is not None

    await hass.services.async_call(
        scene.DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENTITY_SCENE}, blocking=True
    )

    mock_litejet.activate_scene.assert_called_once_with(ENTITY_SCENE_NUMBER)
