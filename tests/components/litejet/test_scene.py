"""The tests for the litejet component."""

from homeassistant.components import scene
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import async_init_integration

ENTITY_SCENE = "scene.litejet_mock_scene_1"
ENTITY_SCENE_NUMBER = 1
ENTITY_OTHER_SCENE = "scene.litejet_mock_scene_2"
ENTITY_OTHER_SCENE_NUMBER = 2


async def test_disabled_by_default(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, mock_litejet
) -> None:
    """Test the scene is disabled by default."""
    await async_init_integration(hass)

    state = hass.states.get(ENTITY_SCENE)
    assert state is None

    entry = entity_registry.async_get(ENTITY_SCENE)
    assert entry
    assert entry.disabled
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION


async def test_activate(hass: HomeAssistant, mock_litejet) -> None:
    """Test activating the scene."""

    await async_init_integration(hass, use_scene=True)

    state = hass.states.get(ENTITY_SCENE)
    assert state is not None

    await hass.services.async_call(
        scene.DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENTITY_SCENE}, blocking=True
    )

    mock_litejet.activate_scene.assert_called_once_with(ENTITY_SCENE_NUMBER)


async def test_connected_event(hass: HomeAssistant, mock_litejet) -> None:
    """Test handling an event from LiteJet."""

    await async_init_integration(hass, use_scene=True)

    # Initial state is available.
    assert hass.states.get(ENTITY_SCENE).state == STATE_UNKNOWN

    # Event indicates it is disconnected now.
    mock_litejet.connected_changed(False, "test")
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_SCENE).state == STATE_UNAVAILABLE

    # Event indicates it is connected now.
    mock_litejet.connected_changed(True, None)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_SCENE).state == STATE_UNKNOWN
