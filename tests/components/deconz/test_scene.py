"""deCONZ scene platform tests."""

from unittest.mock import patch

import pytest

from homeassistant.components.scene import DOMAIN as SCENE_DOMAIN, SERVICE_TURN_ON
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .test_gateway import (
    DECONZ_WEB_REQUEST,
    mock_deconz_put_request,
    setup_deconz_integration,
)


async def test_no_scenes(hass, aioclient_mock):
    """Test that scenes can be loaded without scenes being available."""
    await setup_deconz_integration(hass, aioclient_mock)
    assert len(hass.states.async_all()) == 0


TEST_DATA = [
    (  # Scene
        {
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
        },
        {
            "entity_count": 2,
            "device_count": 3,
            "entity_id": "scene.light_group_scene",
            "unique_id": "01234E56789A/groups/1/scenes/1",
            "entity_category": None,
            "attributes": {
                "friendly_name": "Light group Scene",
            },
            "request": "/groups/1/scenes/1/recall",
        },
    ),
]


@pytest.mark.parametrize("raw_data, expected", TEST_DATA)
async def test_scenes(hass, aioclient_mock, raw_data, expected):
    """Test successful creation of scene entities."""
    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)

    with patch.dict(DECONZ_WEB_REQUEST, raw_data):
        config_entry = await setup_deconz_integration(hass, aioclient_mock)

    assert len(hass.states.async_all()) == expected["entity_count"]

    # Verify state data

    scene = hass.states.get(expected["entity_id"])
    assert scene.attributes == expected["attributes"]

    # Verify entity registry data

    ent_reg_entry = ent_reg.async_get(expected["entity_id"])
    assert ent_reg_entry.entity_category is expected["entity_category"]
    assert ent_reg_entry.unique_id == expected["unique_id"]

    # Verify device registry data

    assert (
        len(dr.async_entries_for_config_entry(dev_reg, config_entry.entry_id))
        == expected["device_count"]
    )

    # Verify button press

    mock_deconz_put_request(aioclient_mock, config_entry.data, expected["request"])

    await hass.services.async_call(
        SCENE_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: expected["entity_id"]},
        blocking=True,
    )
    assert aioclient_mock.mock_calls[1][2] == {}

    # Unload entry

    await hass.config_entries.async_unload(config_entry.entry_id)
    assert hass.states.get(expected["entity_id"]).state == STATE_UNAVAILABLE

    # Remove entry

    await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 0


async def test_only_new_scenes_are_created(hass, aioclient_mock, mock_deconz_websocket):
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
        await setup_deconz_integration(hass, aioclient_mock)

    assert len(hass.states.async_all()) == 2

    event_changed_group = {
        "t": "event",
        "e": "changed",
        "r": "groups",
        "id": "1",
        "scenes": [{"id": "1", "name": "Scene"}],
    }
    await mock_deconz_websocket(data=event_changed_group)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 2
