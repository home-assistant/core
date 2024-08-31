"""Test WebSocket API."""

import asyncio

from homeassistant.components.assist_pipeline import PipelineStage
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from . import ENTITY_ID
from .conftest import MockAssistSatellite

from tests.common import MockUser
from tests.typing import WebSocketGenerator


async def test_entity_state(
    hass: HomeAssistant,
    init_components: ConfigEntry,
    entity: MockAssistSatellite,
    hass_ws_client: WebSocketGenerator,
    hass_admin_user: MockUser,
) -> None:
    """Test entity state represent events."""
    ws_client = await hass_ws_client(hass)

    await ws_client.send_json_auto_id(
        {
            "type": "assist_satellite/intercept_wake_word",
            "entity_id": ENTITY_ID,
        }
    )

    for _ in range(3):
        await asyncio.sleep(0)

    await entity.async_accept_pipeline_from_satellite(
        object(),
        start_stage=PipelineStage.STT,
        wake_word_phrase="ok, nabu",
    )

    response = await ws_client.receive_json()

    assert response["success"]
    assert response["result"] == {"wake_word_phrase": "ok, nabu"}

    # Ensure we error out for wake word processing in Home Assistant
    await ws_client.send_json_auto_id(
        {
            "type": "assist_satellite/intercept_wake_word",
            "entity_id": ENTITY_ID,
        }
    )

    for _ in range(3):
        await asyncio.sleep(0)

    await entity.async_accept_pipeline_from_satellite(
        object(),
        # Emulate wake word processing in Home Assistant
        start_stage=PipelineStage.WAKE_WORD,
    )

    response = await ws_client.receive_json()
    assert not response["success"]
    assert response["error"] == {
        "code": "home_assistant_error",
        "message": "Only on-device wake words currently supported",
    }

    # Remove admin permission and verify we're not allowed
    hass_admin_user.groups = []

    await ws_client.send_json_auto_id(
        {
            "type": "assist_satellite/intercept_wake_word",
            "entity_id": ENTITY_ID,
        }
    )
    response = await ws_client.receive_json()

    assert not response["success"]
    assert response["error"] == {
        "code": "unauthorized",
        "message": "Unauthorized",
    }
