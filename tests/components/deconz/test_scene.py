"""deCONZ scene platform tests."""

from collections.abc import Callable
from typing import Any
from unittest.mock import patch

import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.scene import DOMAIN as SCENE_DOMAIN, SERVICE_TURN_ON
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import ConfigEntryFactoryType, WebsocketDataType

from tests.common import snapshot_platform
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
            "entity_id": "scene.light_group_scene",
            "request": "/groups/1/scenes/1/recall",
        },
    ),
]


@pytest.mark.parametrize(("group_payload", "expected"), TEST_DATA)
async def test_scenes(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    config_entry_factory: ConfigEntryFactoryType,
    mock_put_request: Callable[[str, str], AiohttpClientMocker],
    expected: dict[str, Any],
    snapshot: SnapshotAssertion,
) -> None:
    """Test successful creation of scene entities."""
    with patch("homeassistant.components.deconz.PLATFORMS", [Platform.SCENE]):
        config_entry = await config_entry_factory()
    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)

    # Verify button press

    aioclient_mock = mock_put_request(expected["request"])

    await hass.services.async_call(
        SCENE_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: expected["entity_id"]},
        blocking=True,
    )
    assert aioclient_mock.mock_calls[1][2] == {}


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
    assert len(hass.states.async_all()) == 2
