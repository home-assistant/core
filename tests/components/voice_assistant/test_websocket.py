"""Websocket tests for Voice Assistant integration."""
import asyncio
from unittest.mock import patch

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.typing import WebSocketGenerator


@pytest.fixture(autouse=True)
async def init_components(hass):
    """Initialize relevant components with empty configs."""
    assert await async_setup_component(hass, "voice_assistant", {})


async def test_text_only_pipeline(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test events from a pipeline run with text input (no STT/TTS)."""
    client = await hass_ws_client(hass)

    await client.send_json(
        {"id": 5, "type": "voice_assistant/run", "intent_input": "Are the lights on?"}
    )

    # result
    msg = await client.receive_json()
    assert msg["success"]

    # run start
    msg = await client.receive_json()
    assert msg["event"]["type"] == "run-start"
    assert msg["event"]["data"] == {
        "pipeline": "default",
        "language": hass.config.language,
    }

    # intent
    msg = await client.receive_json()
    assert msg["event"]["type"] == "intent-start"
    assert msg["event"]["data"] == {
        "engine": "default",
        "intent_input": "Are the lights on?",
    }

    msg = await client.receive_json()
    assert msg["event"]["type"] == "intent-finish"
    assert msg["event"]["data"] == {
        "intent_output": {
            "response": {
                "speech": {
                    "plain": {
                        "speech": "Sorry, I couldn't understand that",
                        "extra_data": None,
                    }
                },
                "card": {},
                "language": "en",
                "response_type": "error",
                "data": {"code": "no_intent_match"},
            },
            "conversation_id": None,
        }
    }

    # run finish
    msg = await client.receive_json()
    assert msg["event"]["type"] == "run-finish"
    assert msg["event"]["data"] == {}


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
                "timeout": 0.00001,
            }
        )

        # result
        msg = await client.receive_json()
        assert msg["success"]

        # run start
        msg = await client.receive_json()
        assert msg["event"]["type"] == "run-start"
        assert msg["event"]["data"] == {
            "pipeline": "default",
            "language": hass.config.language,
        }

        # intent
        msg = await client.receive_json()
        assert msg["event"]["type"] == "intent-start"
        assert msg["event"]["data"] == {
            "engine": "default",
            "intent_input": "Are the lights on?",
        }

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
                "timeout": 0.0001,
            }
        )

        # result
        msg = await client.receive_json()
        assert msg["success"]

        # timeout error
        msg = await client.receive_json()
        assert not msg["success"]
        assert msg["error"]["code"] == "timeout"
