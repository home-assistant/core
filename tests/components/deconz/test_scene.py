"""deCONZ scene platform tests."""

from unittest.mock import patch

from homeassistant.components.scene import DOMAIN as SCENE_DOMAIN, SERVICE_TURN_ON
from homeassistant.const import ATTR_ENTITY_ID

from .test_gateway import (
    DECONZ_WEB_REQUEST,
    mock_deconz_put_request,
    setup_deconz_integration,
)


async def test_no_scenes(hass, aioclient_mock):
    """Test that scenes can be loaded without scenes being available."""
    await setup_deconz_integration(hass, aioclient_mock)
    assert len(hass.states.async_all()) == 0


async def test_scenes(hass, aioclient_mock):
    """Test that scenes works."""
    data = {
        "groups": {
            "1": {
                "id": "Light group id",
                "name": "Light group",
                "type": "LightGroup",
                "state": {"all_on": False, "any_on": True},
                "action": {},
                "scenes": [{"id": "1", "name": "Scene"}],
                "lights": [],
            }
        }
    }
    with patch.dict(DECONZ_WEB_REQUEST, data):
        config_entry = await setup_deconz_integration(hass, aioclient_mock)

    assert len(hass.states.async_all()) == 1
    assert hass.states.get("scene.light_group_scene")

    # Verify service calls

    mock_deconz_put_request(
        aioclient_mock, config_entry.data, "/groups/1/scenes/1/recall"
    )

    # Service turn on scene

    await hass.services.async_call(
        SCENE_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "scene.light_group_scene"},
        blocking=True,
    )
    assert aioclient_mock.mock_calls[1][2] == {}

    await hass.config_entries.async_unload(config_entry.entry_id)

    assert len(hass.states.async_all()) == 0
