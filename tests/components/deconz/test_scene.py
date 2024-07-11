"""deCONZ scene platform tests."""

from collections.abc import Callable
from typing import Any

import pytest

from homeassistant.components.scene import DOMAIN as SCENE_DOMAIN, SERVICE_TURN_ON
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import WebsocketDataType

from tests.test_util.aiohttp import AiohttpClientMocker

TEST_DATA = [
    (  # Scene
        {
            "1": {
                "id": "Light group id",
                "name": "Light group",
                "type": "LightGroup",
                "state": {"all_on": False, "any_on": True},
                "action": {},
                "scenes": [{"id": "1", "name": "Scene"}],
                "lights": [],
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


@pytest.mark.parametrize(("group_payload", "expected"), TEST_DATA)
async def test_scenes(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    config_entry_setup: ConfigEntry,
    mock_put_request: Callable[[str, str], AiohttpClientMocker],
    expected: dict[str, Any],
) -> None:
    """Test successful creation of scene entities."""
    assert len(hass.states.async_all()) == expected["entity_count"]

    # Verify state data

    scene = hass.states.get(expected["entity_id"])
    assert scene.attributes == expected["attributes"]

    # Verify entity registry data

    ent_reg_entry = entity_registry.async_get(expected["entity_id"])
    assert ent_reg_entry.entity_category is expected["entity_category"]
    assert ent_reg_entry.unique_id == expected["unique_id"]

    # Verify device registry data

    assert (
        len(
            dr.async_entries_for_config_entry(
                device_registry, config_entry_setup.entry_id
            )
        )
        == expected["device_count"]
    )

    # Verify button press

    aioclient_mock = mock_put_request(expected["request"])

    await hass.services.async_call(
        SCENE_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: expected["entity_id"]},
        blocking=True,
    )
    assert aioclient_mock.mock_calls[1][2] == {}

    # Unload entry

    await hass.config_entries.async_unload(config_entry_setup.entry_id)
    assert hass.states.get(expected["entity_id"]).state == STATE_UNAVAILABLE

    # Remove entry

    await hass.config_entries.async_remove(config_entry_setup.entry_id)
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 0


@pytest.mark.parametrize(
    "group_payload",
    [
        {
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
    ],
)
@pytest.mark.usefixtures("config_entry_setup")
async def test_only_new_scenes_are_created(
    hass: HomeAssistant,
    mock_websocket_data: WebsocketDataType,
) -> None:
    """Test that scenes works."""
    assert len(hass.states.async_all()) == 2

    event_changed_group = {
        "r": "groups",
        "id": "1",
        "scenes": [{"id": "1", "name": "Scene"}],
    }
    await mock_websocket_data(event_changed_group)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 2
