"""Websocket tests for Voice Assistant integration."""
import asyncio
from unittest.mock import patch

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.typing import WebSocketGenerator


@pytest.fixture
async def init_components(hass):
    """Initialize relevant components with empty configs."""
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, "voice_assistant", {})


async def test_text_only_pipeline(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, init_components
) -> None:
    """Test events from a pipeline run with text input (no STT/TTS)."""
    client = await hass_ws_client(hass)

    await client.send_json(
        {"id": 5, "type": "voice_assistant/run", "intent_input": "Are the lights on?"}
    )

    # run start
    msg = await client.receive_json()
    assert msg["event"]["type"] == "run-start"

    # intent
    msg = await client.receive_json()
    assert msg["event"]["type"] == "intent-start"

    msg = await client.receive_json()
    assert msg["event"]["type"] == "intent-finish"

    # run finish
    msg = await client.receive_json()
    assert msg["event"]["type"] == "run-finish"

    # result
    msg = await client.receive_json()
    assert msg["success"]


async def test_conversation_timeout(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, init_components
) -> None:
    """Test partial pipeline run with conversation agent timeout."""
    client = await hass_ws_client(hass)

    async def sleepy_converse(*args, **kwargs):
        await asyncio.sleep(3600)

    with patch(
        "homeassistant.components.conversation.async_converse", new=sleepy_converse
    ):
        await client.send_json(
            {
                "id": 5,
                "type": "voice_assistant/run",
                "intent_input": "Are the lights on?",
                "timeout": 0.5,
            }
        )

        # run start
        msg = await client.receive_json()
        assert msg["event"]["type"] == "run-start"

        # intent
        msg = await client.receive_json()
        assert msg["event"]["type"] == "intent-start"

        # timeout error
        msg = await client.receive_json()
        assert not msg["success"]
        assert msg["error"]["code"] == "timeout"


async def test_pipeline_timeout(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, init_components
) -> None:
    """Test pipeline run with immediate timeout."""
    client = await hass_ws_client(hass)

    async def sleepy_run(*args, **kwargs):
        await asyncio.sleep(3600)

    with patch(
        "homeassistant.components.voice_assistant.pipeline.Pipeline._run",
        new=sleepy_run,
    ):
        await client.send_json(
            {
                "id": 5,
                "type": "voice_assistant/run",
                "intent_input": "Are the lights on?",
                "timeout": 0.5,
            }
        )

        # timeout error
        msg = await client.receive_json()
        assert not msg["success"]
        assert msg["error"]["code"] == "timeout"
