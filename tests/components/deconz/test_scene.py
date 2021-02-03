"""deCONZ scene platform tests."""

from copy import deepcopy

from homeassistant.components.deconz import DOMAIN as DECONZ_DOMAIN
from homeassistant.components.scene import DOMAIN as SCENE_DOMAIN, SERVICE_TURN_ON
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.setup import async_setup_component

from .test_gateway import (
    DECONZ_WEB_REQUEST,
    mock_deconz_put_request,
    setup_deconz_integration,
)

GROUPS = {
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


async def test_platform_manually_configured(hass):
    """Test that we do not discover anything or try to set up a gateway."""
    assert (
        await async_setup_component(
            hass, SCENE_DOMAIN, {"scene": {"platform": DECONZ_DOMAIN}}
        )
        is True
    )
    assert DECONZ_DOMAIN not in hass.data


async def test_no_scenes(hass, aioclient_mock):
    """Test that scenes can be loaded without scenes being available."""
    await setup_deconz_integration(hass, aioclient_mock)
    assert len(hass.states.async_all()) == 0


async def test_scenes(hass, aioclient_mock):
    """Test that scenes works."""
    data = deepcopy(DECONZ_WEB_REQUEST)
    data["groups"] = deepcopy(GROUPS)
    config_entry = await setup_deconz_integration(
        hass, aioclient_mock, get_state_response=data
    )

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
