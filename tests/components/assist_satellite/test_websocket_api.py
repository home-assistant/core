"""Test WebSocket API."""

import asyncio
from http import HTTPStatus
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.assist_pipeline import PipelineStage
from homeassistant.components.assist_satellite.websocket_api import (
    CONNECTION_TEST_TIMEOUT,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from . import ENTITY_ID
from .conftest import MockAssistSatellite

from tests.common import MockUser
from tests.typing import ClientSessionGenerator, WebSocketGenerator


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
    msg = await ws_client.receive_json()
    assert msg["success"]
    assert msg["result"] is None
    subscription_id = msg["id"]

    await entity.async_accept_pipeline_from_satellite(
        object(),  # type: ignore[arg-type]
        start_stage=PipelineStage.STT,
        wake_word_phrase="ok, nabu",
    )

    async with asyncio.timeout(1):
        msg = await ws_client.receive_json()

    assert msg["id"] == subscription_id
    assert msg["type"] == "event"
    assert msg["event"] == {"wake_word_phrase": "ok, nabu"}


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

    async with asyncio.timeout(1):
        msg = await ws_client.receive_json()

    assert msg["success"]
    assert msg["result"] is None

    await entity.async_accept_pipeline_from_satellite(
        object(),  # type: ignore[arg-type]
        # Emulate wake word processing in Home Assistant
        start_stage=PipelineStage.WAKE_WORD,
    )

    async with asyncio.timeout(1):
        msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"] == {
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

    async with asyncio.timeout(1):
        msg = await ws_client.receive_json()

    assert msg["success"]
    assert msg["result"] is None

    await entity.async_accept_pipeline_from_satellite(
        object(),  # type: ignore[arg-type]
        start_stage=PipelineStage.STT,
        # We are not passing wake word phrase
    )

    async with asyncio.timeout(1):
        msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"] == {
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

    async with asyncio.timeout(1):
        msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"] == {
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
    async with asyncio.timeout(1):
        msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"] == {
        "code": "not_found",
        "message": "Entity not found",
    }


async def test_intercept_wake_word_twice(
    hass: HomeAssistant,
    init_components: ConfigEntry,
    entity: MockAssistSatellite,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test intercepting a wake word twice cancels the previous request."""
    ws_client = await hass_ws_client(hass)

    await ws_client.send_json_auto_id(
        {
            "type": "assist_satellite/intercept_wake_word",
            "entity_id": ENTITY_ID,
        }
    )

    async with asyncio.timeout(1):
        msg = await ws_client.receive_json()

    assert msg["success"]
    assert msg["result"] is None

    task = hass.async_create_task(ws_client.receive_json())

    await ws_client.send_json_auto_id(
        {
            "type": "assist_satellite/intercept_wake_word",
            "entity_id": ENTITY_ID,
        }
    )

    # Should get an error from previous subscription
    async with asyncio.timeout(1):
        msg = await task

    assert not msg["success"]
    assert msg["error"] == {
        "code": "home_assistant_error",
        "message": "Wake word interception already in progress",
    }

    # Response to second subscription
    async with asyncio.timeout(1):
        msg = await ws_client.receive_json()

    assert msg["success"]
    assert msg["result"] is None


async def test_intercept_wake_word_unsubscribe(
    hass: HomeAssistant,
    init_components: ConfigEntry,
    entity: MockAssistSatellite,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test that closing the websocket connection stops interception."""
    ws_client = await hass_ws_client(hass)

    await ws_client.send_json_auto_id(
        {
            "type": "assist_satellite/intercept_wake_word",
            "entity_id": ENTITY_ID,
        }
    )

    # Wait for interception to start
    for _ in range(3):
        await asyncio.sleep(0)

    async def receive_json():
        with pytest.raises(TypeError):
            # Raises TypeError when connection is closed
            await ws_client.receive_json()

    task = hass.async_create_task(receive_json())

    # Close connection
    await ws_client.close()
    await task

    with (
        patch(
            "homeassistant.components.assist_satellite.entity.async_pipeline_from_audio_stream",
        ) as mock_pipeline_from_audio_stream,
    ):
        # Start a pipeline with a wake word
        await entity.async_accept_pipeline_from_satellite(
            object(),
            wake_word_phrase="ok, nabu",  # type: ignore[arg-type]
        )

        # Wake word should not be intercepted
        mock_pipeline_from_audio_stream.assert_called_once()


async def test_get_configuration(
    hass: HomeAssistant,
    init_components: ConfigEntry,
    entity: MockAssistSatellite,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test getting satellite configuration."""
    ws_client = await hass_ws_client(hass)

    with (
        patch.object(entity, "_attr_pipeline_entity_id", "select.test_pipeline"),
        patch.object(entity, "_attr_vad_sensitivity_entity_id", "select.test_vad"),
    ):
        await ws_client.send_json_auto_id(
            {
                "type": "assist_satellite/get_configuration",
                "entity_id": ENTITY_ID,
            }
        )
        msg = await ws_client.receive_json()
        assert msg["success"]
        assert msg["result"] == {
            "active_wake_words": ["1234"],
            "available_wake_words": [
                {"id": "1234", "trained_languages": ["en"], "wake_word": "okay nabu"},
                {"id": "5678", "trained_languages": ["en"], "wake_word": "hey jarvis"},
            ],
            "max_active_wake_words": 1,
            "pipeline_entity_id": "select.test_pipeline",
            "vad_entity_id": "select.test_vad",
        }


async def test_set_wake_words(
    hass: HomeAssistant,
    init_components: ConfigEntry,
    entity: MockAssistSatellite,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test setting active wake words."""
    ws_client = await hass_ws_client(hass)

    await ws_client.send_json_auto_id(
        {
            "type": "assist_satellite/set_wake_words",
            "entity_id": ENTITY_ID,
            "wake_word_ids": ["5678"],
        }
    )
    msg = await ws_client.receive_json()
    assert msg["success"]

    # Verify change
    await ws_client.send_json_auto_id(
        {
            "type": "assist_satellite/get_configuration",
            "entity_id": ENTITY_ID,
        }
    )
    msg = await ws_client.receive_json()
    assert msg["success"]
    assert msg["result"].get("active_wake_words") == ["5678"]


async def test_set_wake_words_exceed_maximum(
    hass: HomeAssistant,
    init_components: ConfigEntry,
    entity: MockAssistSatellite,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test setting too many active wake words."""
    ws_client = await hass_ws_client(hass)

    await ws_client.send_json_auto_id(
        {
            "type": "assist_satellite/set_wake_words",
            "entity_id": ENTITY_ID,
            "wake_word_ids": ["1234", "5678"],  # max of 1
        }
    )
    msg = await ws_client.receive_json()
    assert not msg["success"]
    assert msg["error"] == {
        "code": "not_supported",
        "message": "Maximum number of active wake words is 1",
    }


async def test_set_wake_words_bad_id(
    hass: HomeAssistant,
    init_components: ConfigEntry,
    entity: MockAssistSatellite,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test setting active wake words with a bad id."""
    ws_client = await hass_ws_client(hass)

    await ws_client.send_json_auto_id(
        {
            "type": "assist_satellite/set_wake_words",
            "entity_id": ENTITY_ID,
            "wake_word_ids": ["abcd"],  # not an available id
        }
    )
    msg = await ws_client.receive_json()
    assert not msg["success"]
    assert msg["error"] == {
        "code": "not_supported",
        "message": "Wake word id is not supported: abcd",
    }


async def test_connection_test(
    hass: HomeAssistant,
    init_components: ConfigEntry,
    entity: MockAssistSatellite,
    hass_ws_client: WebSocketGenerator,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test connection test."""
    ws_client = await hass_ws_client(hass)

    await ws_client.send_json_auto_id(
        {
            "type": "assist_satellite/test_connection",
            "entity_id": ENTITY_ID,
        }
    )

    for _ in range(3):
        await asyncio.sleep(0)

    assert len(entity.announcements) == 1
    assert entity.announcements[0].message == ""
    announcement_media_id = entity.announcements[0].media_id
    hass_url = "http://10.10.10.10:8123"
    assert announcement_media_id.startswith(
        f"{hass_url}/api/assist_satellite/connection_test/"
    )

    # Fake satellite fetches the URL
    client = await hass_client()
    resp = await client.get(announcement_media_id[len(hass_url) :])
    assert resp.status == HTTPStatus.OK

    response = await ws_client.receive_json()
    assert response["success"]
    assert response["result"] == {"status": "success"}


async def test_connection_test_timeout(
    hass: HomeAssistant,
    init_components: ConfigEntry,
    entity: MockAssistSatellite,
    hass_ws_client: WebSocketGenerator,
    hass_client: ClientSessionGenerator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test connection test timeout."""
    ws_client = await hass_ws_client(hass)

    await ws_client.send_json_auto_id(
        {
            "type": "assist_satellite/test_connection",
            "entity_id": ENTITY_ID,
        }
    )

    for _ in range(3):
        await asyncio.sleep(0)

    assert len(entity.announcements) == 1
    assert entity.announcements[0].message == ""
    announcement_media_id = entity.announcements[0].media_id
    hass_url = "http://10.10.10.10:8123"
    assert announcement_media_id.startswith(
        f"{hass_url}/api/assist_satellite/connection_test/"
    )

    freezer.tick(CONNECTION_TEST_TIMEOUT + 1)

    # Timeout
    response = await ws_client.receive_json()
    assert response["success"]
    assert response["result"] == {"status": "timeout"}


async def test_connection_test_invalid_satellite(
    hass: HomeAssistant,
    init_components: ConfigEntry,
    entity: MockAssistSatellite,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test connection test with unknown entity id."""
    ws_client = await hass_ws_client(hass)

    await ws_client.send_json_auto_id(
        {
            "type": "assist_satellite/test_connection",
            "entity_id": "assist_satellite.invalid",
        }
    )
    response = await ws_client.receive_json()

    assert not response["success"]
    assert response["error"] == {
        "code": "not_found",
        "message": "Entity not found",
    }


async def test_connection_test_timeout_announcement_unsupported(
    hass: HomeAssistant,
    init_components: ConfigEntry,
    entity: MockAssistSatellite,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test connection test entity which does not support announce."""
    ws_client = await hass_ws_client(hass)

    # Disable announce support
    entity.supported_features = 0

    await ws_client.send_json_auto_id(
        {
            "type": "assist_satellite/test_connection",
            "entity_id": ENTITY_ID,
        }
    )
    response = await ws_client.receive_json()

    assert not response["success"]
    assert response["error"] == {
        "code": "not_supported",
        "message": "Entity does not support announce",
    }
