"""deCONZ button platform tests."""

from collections.abc import Callable
from typing import Any
from unittest.mock import patch

import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import ConfigEntryFactoryType

from tests.common import snapshot_platform
from tests.test_util.aiohttp import AiohttpClientMocker

TEST_DATA = [
    (  # Store scene button
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
            "entity_id": "button.light_group_scene_store_current_scene",
            "request": "/groups/1/scenes/1/store",
            "request_data": {},
        },
    ),
    (  # Presence reset button
        {
            "sensors": {
                "1": {
                    "config": {
                        "devicemode": "undirected",
                        "on": True,
                        "reachable": True,
                        "sensitivity": 3,
                        "triggerdistance": "medium",
                    },
                    "etag": "13ff209f9401b317987d42506dd4cd79",
                    "lastannounced": None,
                    "lastseen": "2022-06-28T23:13Z",
                    "manufacturername": "aqara",
                    "modelid": "lumi.motion.ac01",
                    "name": "Aqara FP1",
                    "state": {
                        "lastupdated": "2022-06-28T23:13:38.577",
                        "presence": True,
                        "presenceevent": "leave",
                    },
                    "swversion": "20210121",
                    "type": "ZHAPresence",
                    "uniqueid": "xx:xx:xx:xx:xx:xx:xx:xx-01-0406",
                }
            }
        },
        {
            "entity_id": "button.aqara_fp1_reset_presence",
            "request": "/sensors/1/config",
            "request_data": {"resetpresence": True},
        },
    ),
]


@pytest.mark.parametrize(("deconz_payload", "expected"), TEST_DATA)
async def test_button(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    aioclient_mock: AiohttpClientMocker,
    config_entry_factory: ConfigEntryFactoryType,
    mock_put_request: Callable[[str, str], AiohttpClientMocker],
    expected: dict[str, Any],
    snapshot: SnapshotAssertion,
) -> None:
    """Test successful creation of button entities."""
    with patch("homeassistant.components.deconz.PLATFORMS", [Platform.BUTTON]):
        config_entry = await config_entry_factory()
    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)

    # Verify button press

    aioclient_mock = mock_put_request(expected["request"])

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: expected["entity_id"]},
        blocking=True,
    )
    assert aioclient_mock.mock_calls[1][2] == expected["request_data"]
