"""deCONZ scene platform tests."""
from copy import deepcopy

from homeassistant.components import deconz
from homeassistant.components.deconz.gateway import get_gateway_from_config_entry
import homeassistant.components.scene as scene
from homeassistant.setup import async_setup_component

from .test_gateway import DECONZ_WEB_REQUEST, setup_deconz_integration

from tests.async_mock import patch

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
            hass, scene.DOMAIN, {"scene": {"platform": deconz.DOMAIN}}
        )
        is True
    )
    assert deconz.DOMAIN not in hass.data


async def test_no_scenes(hass):
    """Test that scenes can be loaded without scenes being available."""
    await setup_deconz_integration(hass)
    assert len(hass.states.async_all()) == 0


async def test_scenes(hass):
    """Test that scenes works."""
    data = deepcopy(DECONZ_WEB_REQUEST)
    data["groups"] = deepcopy(GROUPS)
    config_entry = await setup_deconz_integration(hass, get_state_response=data)
    gateway = get_gateway_from_config_entry(hass, config_entry)

    assert len(hass.states.async_all()) == 1
    assert hass.states.get("scene.light_group_scene")

    # Verify service calls

    group_scene = gateway.api.groups["1"].scenes["1"]

    # Service turn on scene

    with patch.object(group_scene, "_request", return_value=True) as set_callback:
        await hass.services.async_call(
            "scene", "turn_on", {"entity_id": "scene.light_group_scene"}, blocking=True
        )
        await hass.async_block_till_done()
        set_callback.assert_called_with("put", "/groups/1/scenes/1/recall", json={})

    await hass.config_entries.async_unload(config_entry.entry_id)

    assert len(hass.states.async_all()) == 0
