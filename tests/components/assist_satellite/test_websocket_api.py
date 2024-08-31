"""Test WebSocket API."""

import asyncio

from homeassistant.components.assist_pipeline import PipelineStage
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from . import ENTITY_ID
from .conftest import MockAssistSatellite

from tests.common import MockUser
from tests.typing import WebSocketGenerator


async def test_intercept_wake_word(
    hass: HomeAssistant,
    init_components: ConfigEntry,
    entity: MockAssistSatellite,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test intercepting a wake word."""
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


async def test_intercept_wake_word_requires_on_device_wake_word(
    hass: HomeAssistant,
    init_components: ConfigEntry,
    entity: MockAssistSatellite,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test intercepting a wake word fails if detection happens in HA."""
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
        # Emulate wake word processing in Home Assistant
        start_stage=PipelineStage.WAKE_WORD,
    )

    response = await ws_client.receive_json()
    assert not response["success"]
    assert response["error"] == {
        "code": "home_assistant_error",
        "message": "Only on-device wake words currently supported",
    }


async def test_intercept_wake_word_requires_wake_word_phrase(
    hass: HomeAssistant,
    init_components: ConfigEntry,
    entity: MockAssistSatellite,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test intercepting a wake word fails if detection happens in HA."""
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
        # We are not passing wake word phrase
    )

    response = await ws_client.receive_json()
    assert not response["success"]
    assert response["error"] == {
        "code": "home_assistant_error",
        "message": "No wake word phrase provided",
    }


async def test_intercept_wake_word_require_admin(
    hass: HomeAssistant,
    init_components: ConfigEntry,
    entity: MockAssistSatellite,
    hass_ws_client: WebSocketGenerator,
    hass_admin_user: MockUser,
) -> None:
    """Test intercepting a wake word requires admin access."""
    # Remove admin permission and verify we're not allowed
    hass_admin_user.groups = []
    ws_client = await hass_ws_client(hass)

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


async def test_intercept_wake_word_invalid_satellite(
    hass: HomeAssistant,
    init_components: ConfigEntry,
    entity: MockAssistSatellite,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test intercepting a wake word requires admin access."""
    ws_client = await hass_ws_client(hass)

    await ws_client.send_json_auto_id(
        {
            "type": "assist_satellite/intercept_wake_word",
            "entity_id": "assist_satellite.invalid",
        }
    )
    response = await ws_client.receive_json()

    assert not response["success"]
    assert response["error"] == {
        "code": "not_found",
        "message": "Entity not found",
    }


async def test_intercept_wake_word_twice(
    hass: HomeAssistant,
    init_components: ConfigEntry,
    entity: MockAssistSatellite,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test intercepting a wake word requires admin access."""
    ws_client = await hass_ws_client(hass)

    await ws_client.send_json_auto_id(
        {
            "type": "assist_satellite/intercept_wake_word",
            "entity_id": ENTITY_ID,
        }
    )

    await ws_client.send_json_auto_id(
        {
            "type": "assist_satellite/intercept_wake_word",
            "entity_id": ENTITY_ID,
        }
    )
    response = await ws_client.receive_json()

    assert not response["success"]
    assert response["error"] == {
        "code": "home_assistant_error",
        "message": "Wake word interception already in progress",
    }
