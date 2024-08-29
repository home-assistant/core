"""Test the Assist Satellite websocket API."""

import asyncio
from collections.abc import AsyncIterable
from unittest.mock import ANY, patch

from homeassistant.components.assist_pipeline import (
    PipelineEvent,
    PipelineEventType,
    PipelineStage,
)
from homeassistant.components.assist_satellite import AssistSatelliteEntityFeature
from homeassistant.components.media_source import PlayMedia
from homeassistant.components.websocket_api import ERR_NOT_SUPPORTED
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .conftest import MockAssistSatellite

from tests.typing import WebSocketGenerator

ENTITY_ID = "assist_satellite.test_entity"


async def audio_stream() -> AsyncIterable[bytes]:
    """Empty audio stream."""
    yield b""


async def test_intercept_wake_word(
    hass: HomeAssistant,
    init_components: ConfigEntry,
    entity: MockAssistSatellite,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test assist_satellite/intercept_wake_word command."""
    client = await hass_ws_client(hass)

    with (
        patch(
            "homeassistant.components.assist_pipeline.pipeline.PipelineInput.validate",
            return_value=None,
        ),
        patch(
            "homeassistant.components.assist_pipeline.pipeline.PipelineRun.prepare_speech_to_text",
            return_value=None,
        ),
        patch(
            "homeassistant.components.assist_pipeline.pipeline.PipelineRun.prepare_recognize_intent",
            return_value=None,
        ),
        patch(
            "homeassistant.components.assist_pipeline.pipeline.PipelineRun.prepare_text_to_speech",
            return_value=None,
        ),
        patch.object(entity, "on_pipeline_event") as mock_on_pipeline_event,
    ):
        async with asyncio.timeout(1):
            await client.send_json_auto_id(
                {"type": "assist_satellite/intercept_wake_word", "entity_id": ENTITY_ID}
            )

            # Wait for interception to start
            while not entity.is_intercepting_wake_word:
                await asyncio.sleep(0.01)

            # Start a pipeline with a wake word
            await entity._async_accept_pipeline_from_satellite(
                audio_stream=audio_stream(),
                start_stage=PipelineStage.STT,
                end_stage=PipelineStage.TTS,
                wake_word_phrase="test wake word",
            )

            # Verify that wake word was intercepted
            response = await client.receive_json()
            assert response["success"]
            assert response["result"] == {"wake_word_phrase": "test wake word"}

            # Verify that only run end event was sent to pipeline
            mock_on_pipeline_event.assert_called_once_with(
                PipelineEvent(PipelineEventType.RUN_END, data=None, timestamp=ANY)
            )


async def test_announce_not_supported(
    hass: HomeAssistant,
    init_components: ConfigEntry,
    entity: MockAssistSatellite,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test assist_satellite/announce command with an entity that doesn't support announcements."""
    client = await hass_ws_client(hass)

    with patch.object(
        entity, "_attr_supported_features", AssistSatelliteEntityFeature(0)
    ):
        async with asyncio.timeout(1):
            await client.send_json_auto_id(
                {
                    "type": "assist_satellite/announce",
                    "entity_id": ENTITY_ID,
                    "media_id": "test media id",
                }
            )

            response = await client.receive_json()
            assert not response["success"]
            assert response["error"]["code"] == ERR_NOT_SUPPORTED


async def test_announce_media_id(
    hass: HomeAssistant,
    init_components: ConfigEntry,
    entity: MockAssistSatellite,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test assist_satellite/announce command with media id."""
    client = await hass_ws_client(hass)

    with (
        patch.object(
            entity, "_internal_async_announce"
        ) as mock_internal_async_announce,
    ):
        async with asyncio.timeout(1):
            await client.send_json_auto_id(
                {
                    "type": "assist_satellite/announce",
                    "entity_id": ENTITY_ID,
                    "media_id": "test media id",
                }
            )

            response = await client.receive_json()
            assert response["success"]

            # Verify media id was passed through
            mock_internal_async_announce.assert_called_once_with("test media id")


async def test_announce_text(
    hass: HomeAssistant,
    init_components: ConfigEntry,
    entity: MockAssistSatellite,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test assist_satellite/announce command with text."""
    client = await hass_ws_client(hass)

    with (
        patch(
            "homeassistant.components.assist_satellite.entity.tts_generate_media_source_id",
            return_value="",
        ),
        patch(
            "homeassistant.components.assist_satellite.entity.media_source.async_resolve_media",
            return_value=PlayMedia(url="test media id", mime_type=""),
        ),
        patch(
            "homeassistant.components.assist_satellite.entity.async_process_play_media_url",
            return_value="test media id",
        ),
        patch.object(
            entity, "_internal_async_announce"
        ) as mock_internal_async_announce,
    ):
        async with asyncio.timeout(1):
            await client.send_json_auto_id(
                {
                    "type": "assist_satellite/announce",
                    "entity_id": ENTITY_ID,
                    "text": "test text",
                }
            )

            response = await client.receive_json()
            assert response["success"]

            # Verify media id was passed through
            mock_internal_async_announce.assert_called_once_with("test media id")
