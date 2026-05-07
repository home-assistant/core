"""Shared fixtures for Cloudflare Workers AI tests."""

from __future__ import annotations

from collections.abc import Generator
import io
from unittest.mock import AsyncMock, patch
import wave

import pytest

from homeassistant.components.cloudflare_ai.const import (
    CONF_ACCOUNT_ID,
    CONF_API_TOKEN,
    CONF_CHAT_MODEL,
    CONF_ENABLE_THINKING,
    CONF_MAX_TOKENS,
    CONF_PROMPT,
    CONF_TEMPERATURE,
    CONF_USE_AI_GATEWAY,
    DEFAULT_CHAT_MODEL,
    DEFAULT_ENABLE_THINKING,
    DOMAIN,
    SUBENTRY_CONVERSATION,
)
from homeassistant.const import CONF_LLM_HASS_API
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

TEST_ACCOUNT_ID = "test_account_id_123"
TEST_API_TOKEN = "test_api_token_456"
TEST_GATEWAY_ID = "test-gateway"
TEST_GATEWAY_TOKEN = "test_gw_token_789"


@pytest.fixture
async def setup_ha_components(hass: HomeAssistant) -> None:
    """Set up core HA components needed by our integration."""
    await async_setup_component(hass, "homeassistant", {})
    await async_setup_component(hass, "conversation", {})
    await hass.async_block_till_done()


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Create a mock config entry with subentries."""
    entry = MockConfigEntry(
        version=1,
        minor_version=1,
        domain=DOMAIN,
        title="Cloudflare Workers AI",
        data={
            CONF_ACCOUNT_ID: TEST_ACCOUNT_ID,
            CONF_API_TOKEN: TEST_API_TOKEN,
            CONF_USE_AI_GATEWAY: False,
        },
        unique_id=TEST_ACCOUNT_ID,
        subentries_data=[
            {
                "subentry_type": SUBENTRY_CONVERSATION,
                "title": "Cloudflare AI Conversation",
                "unique_id": None,
                "data": {
                    CONF_CHAT_MODEL: DEFAULT_CHAT_MODEL,
                    CONF_MAX_TOKENS: 1024,
                    CONF_TEMPERATURE: 0.6,
                    CONF_PROMPT: "You are a helpful assistant.",
                    CONF_ENABLE_THINKING: DEFAULT_ENABLE_THINKING,
                    CONF_LLM_HASS_API: ["assist"],
                },
            },
        ],
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
def mock_validate_credentials() -> Generator[AsyncMock]:
    """Mock the validate_credentials method."""
    with patch(
        "homeassistant.components.cloudflare_ai.client.CloudflareAIClient.validate_credentials",
        new_callable=AsyncMock,
        return_value=True,
    ) as mock:
        yield mock


@pytest.fixture
def mock_run_model() -> Generator[AsyncMock]:
    """Mock the run_model method."""
    with patch(
        "homeassistant.components.cloudflare_ai.client.CloudflareAIClient.run_model",
        new_callable=AsyncMock,
    ) as mock:
        yield mock


@pytest.fixture
def mock_stream_model() -> Generator[AsyncMock]:
    """Mock the stream_model method."""
    with patch(
        "homeassistant.components.cloudflare_ai.client.CloudflareAIClient.stream_model",
    ) as mock:
        yield mock


def make_wav_audio(
    duration_ms: int = 100,
    sample_rate: int = 16000,
    channels: int = 1,
    sample_width: int = 2,
) -> bytes:
    """Generate a small WAV file for testing."""
    num_frames = int(sample_rate * duration_ms / 1000)
    frames = b"\x00" * (num_frames * channels * sample_width)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(sample_width)
        wav.setframerate(sample_rate)
        wav.writeframes(frames)
    return buf.getvalue()


SAMPLE_CHAT_RESPONSE = {
    "response": "Hello! How can I help you?",
    "usage": {
        "prompt_tokens": 20,
        "completion_tokens": 8,
        "total_tokens": 28,
    },
}

SAMPLE_TOOL_CALL_RESPONSE = {
    "response": None,
    "tool_calls": [
        {
            "name": "GetDateTime",
            "arguments": {},
        }
    ],
    "usage": {
        "prompt_tokens": 100,
        "completion_tokens": 19,
        "total_tokens": 119,
    },
}

SAMPLE_TOOL_RESULT_RESPONSE = {
    "response": "The current date is March 18, 2026.",
    "usage": {
        "prompt_tokens": 150,
        "completion_tokens": 12,
        "total_tokens": 162,
    },
}
