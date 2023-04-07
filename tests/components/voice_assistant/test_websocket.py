"""Websocket tests for Voice Assistant integration."""
import asyncio
from unittest.mock import ANY, MagicMock, patch

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.voice_assistant.const import DOMAIN
from homeassistant.components.voice_assistant.pipeline import (
    Pipeline,
    PipelineStorageCollection,
)
from homeassistant.core import HomeAssistant

from tests.typing import WebSocketGenerator


async def test_text_only_pipeline(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    init_components,
    snapshot: SnapshotAssertion,
) -> None:
    """Test events from a pipeline run with text input (no STT/TTS)."""
    client = await hass_ws_client(hass)

    await client.send_json_auto_id(
        {
            "type": "voice_assistant/run",
            "start_stage": "intent",
            "end_stage": "intent",
            "input": {"text": "Are the lights on?"},
        }
    )

    # result
    msg = await client.receive_json()
    assert msg["success"]

    # run start
    msg = await client.receive_json()
    assert msg["event"]["type"] == "run-start"
    assert msg["event"]["data"] == snapshot

    # intent
    msg = await client.receive_json()
    assert msg["event"]["type"] == "intent-start"
    assert msg["event"]["data"] == snapshot

    msg = await client.receive_json()
    assert msg["event"]["type"] == "intent-end"
    assert msg["event"]["data"] == snapshot

    # run end
    msg = await client.receive_json()
    assert msg["event"]["type"] == "run-end"
    assert msg["event"]["data"] == {}


async def test_audio_pipeline(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    init_components,
    snapshot: SnapshotAssertion,
) -> None:
    """Test events from a pipeline run with audio input/output."""
    client = await hass_ws_client(hass)

    await client.send_json_auto_id(
        {
            "type": "voice_assistant/run",
            "start_stage": "stt",
            "end_stage": "tts",
        }
    )

    # result
    msg = await client.receive_json()
    assert msg["success"]

    # run start
    msg = await client.receive_json()
    assert msg["event"]["type"] == "run-start"
    assert msg["event"]["data"] == snapshot

    # stt
    msg = await client.receive_json()
    assert msg["event"]["type"] == "stt-start"
    assert msg["event"]["data"] == snapshot

    # End of audio stream (handler id + empty payload)
    await client.send_bytes(bytes([1]))

    msg = await client.receive_json()
    assert msg["event"]["type"] == "stt-end"
    assert msg["event"]["data"] == snapshot

    # intent
    msg = await client.receive_json()
    assert msg["event"]["type"] == "intent-start"
    assert msg["event"]["data"] == snapshot

    msg = await client.receive_json()
    assert msg["event"]["type"] == "intent-end"
    assert msg["event"]["data"] == snapshot

    # text to speech
    msg = await client.receive_json()
    assert msg["event"]["type"] == "tts-start"
    assert msg["event"]["data"] == snapshot

    msg = await client.receive_json()
    assert msg["event"]["type"] == "tts-end"
    assert msg["event"]["data"] == snapshot

    # run end
    msg = await client.receive_json()
    assert msg["event"]["type"] == "run-end"
    assert msg["event"]["data"] == {}


async def test_intent_timeout(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    init_components,
    snapshot: SnapshotAssertion,
) -> None:
    """Test partial pipeline run with conversation agent timeout."""
    client = await hass_ws_client(hass)

    async def sleepy_converse(*args, **kwargs):
        await asyncio.sleep(3600)

    with patch(
        "homeassistant.components.conversation.async_converse",
        new=sleepy_converse,
    ):
        await client.send_json_auto_id(
            {
                "type": "voice_assistant/run",
                "start_stage": "intent",
                "end_stage": "intent",
                "input": {"text": "Are the lights on?"},
                "timeout": 0.1,
            }
        )

        # result
        msg = await client.receive_json()
        assert msg["success"]

        # run start
        msg = await client.receive_json()
        assert msg["event"]["type"] == "run-start"
        assert msg["event"]["data"] == snapshot

        # intent
        msg = await client.receive_json()
        assert msg["event"]["type"] == "intent-start"
        assert msg["event"]["data"] == snapshot

        # timeout error
        msg = await client.receive_json()
        assert msg["event"]["type"] == "error"
        assert msg["event"]["data"] == snapshot


async def test_text_pipeline_timeout(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    init_components,
    snapshot: SnapshotAssertion,
) -> None:
    """Test text-only pipeline run with immediate timeout."""
    client = await hass_ws_client(hass)

    async def sleepy_run(*args, **kwargs):
        await asyncio.sleep(3600)

    with patch(
        "homeassistant.components.voice_assistant.pipeline.PipelineInput.execute",
        new=sleepy_run,
    ):
        await client.send_json_auto_id(
            {
                "type": "voice_assistant/run",
                "start_stage": "intent",
                "end_stage": "intent",
                "input": {"text": "Are the lights on?"},
                "timeout": 0.0001,
            }
        )

        # result
        msg = await client.receive_json()
        assert msg["success"]

        # timeout error
        msg = await client.receive_json()
        assert msg["event"]["type"] == "error"
        assert msg["event"]["data"] == snapshot


async def test_intent_failed(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    init_components,
    snapshot: SnapshotAssertion,
) -> None:
    """Test text-only pipeline run with conversation agent error."""
    client = await hass_ws_client(hass)

    with patch(
        "homeassistant.components.conversation.async_converse",
        new=MagicMock(return_value=RuntimeError),
    ):
        await client.send_json_auto_id(
            {
                "type": "voice_assistant/run",
                "start_stage": "intent",
                "end_stage": "intent",
                "input": {"text": "Are the lights on?"},
            }
        )

        # result
        msg = await client.receive_json()
        assert msg["success"]

        # run start
        msg = await client.receive_json()
        assert msg["event"]["type"] == "run-start"
        assert msg["event"]["data"] == snapshot

        # intent start
        msg = await client.receive_json()
        assert msg["event"]["type"] == "intent-start"
        assert msg["event"]["data"] == snapshot

        # intent error
        msg = await client.receive_json()
        assert msg["event"]["type"] == "error"
        assert msg["event"]["data"]["code"] == "intent-failed"


async def test_audio_pipeline_timeout(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    init_components,
    snapshot: SnapshotAssertion,
) -> None:
    """Test audio pipeline run with immediate timeout."""
    client = await hass_ws_client(hass)

    async def sleepy_run(*args, **kwargs):
        await asyncio.sleep(3600)

    with patch(
        "homeassistant.components.voice_assistant.pipeline.PipelineInput.execute",
        new=sleepy_run,
    ):
        await client.send_json_auto_id(
            {
                "type": "voice_assistant/run",
                "start_stage": "stt",
                "end_stage": "tts",
                "timeout": 0.0001,
            }
        )

        # result
        msg = await client.receive_json()
        assert msg["success"]

        # timeout error
        msg = await client.receive_json()
        assert msg["event"]["type"] == "error"
        assert msg["event"]["data"]["code"] == "timeout"


async def test_stt_provider_missing(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    init_components,
    snapshot: SnapshotAssertion,
) -> None:
    """Test events from a pipeline run with a non-existent STT provider."""
    with patch(
        "homeassistant.components.stt.async_get_provider",
        new=MagicMock(return_value=None),
    ):
        client = await hass_ws_client(hass)

        await client.send_json_auto_id(
            {
                "type": "voice_assistant/run",
                "start_stage": "stt",
                "end_stage": "tts",
            }
        )

        # result
        msg = await client.receive_json()
        assert not msg["success"]
        assert msg["error"]["code"] == "stt-provider-missing"


async def test_stt_stream_failed(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    init_components,
    snapshot: SnapshotAssertion,
) -> None:
    """Test events from a pipeline run with a non-existent STT provider."""
    with patch(
        "tests.components.voice_assistant.conftest.MockSttProvider.async_process_audio_stream",
        new=MagicMock(side_effect=RuntimeError),
    ):
        client = await hass_ws_client(hass)

        await client.send_json_auto_id(
            {
                "type": "voice_assistant/run",
                "start_stage": "stt",
                "end_stage": "tts",
            }
        )

        # result
        msg = await client.receive_json()
        assert msg["success"]

        # run start
        msg = await client.receive_json()
        assert msg["event"]["type"] == "run-start"
        assert msg["event"]["data"] == snapshot

        # stt
        msg = await client.receive_json()
        assert msg["event"]["type"] == "stt-start"
        assert msg["event"]["data"] == snapshot

        # End of audio stream (handler id + empty payload)
        await client.send_bytes(b"1")

        # stt error
        msg = await client.receive_json()
        assert msg["event"]["type"] == "error"
        assert msg["event"]["data"]["code"] == "stt-stream-failed"


async def test_tts_failed(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    init_components,
    snapshot: SnapshotAssertion,
) -> None:
    """Test pipeline run with text to speech error."""
    client = await hass_ws_client(hass)

    with patch(
        "homeassistant.components.media_source.async_resolve_media",
        new=MagicMock(return_value=RuntimeError),
    ):
        await client.send_json(
            {
                "id": 5,
                "type": "voice_assistant/run",
                "start_stage": "tts",
                "end_stage": "tts",
                "input": {"text": "Lights are on."},
            }
        )

        # result
        msg = await client.receive_json()
        assert msg["success"]

        # run start
        msg = await client.receive_json()
        assert msg["event"]["type"] == "run-start"
        assert msg["event"]["data"] == snapshot

        # tts start
        msg = await client.receive_json()
        assert msg["event"]["type"] == "tts-start"
        assert msg["event"]["data"] == snapshot

        # tts error
        msg = await client.receive_json()
        assert msg["event"]["type"] == "error"
        assert msg["event"]["data"]["code"] == "tts-failed"


async def test_invalid_stage_order(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, init_components
) -> None:
    """Test pipeline run with invalid stage order."""
    client = await hass_ws_client(hass)

    await client.send_json_auto_id(
        {
            "type": "voice_assistant/run",
            "start_stage": "tts",
            "end_stage": "stt",
            "input": {"text": "Lights are on."},
        }
    )

    # result
    msg = await client.receive_json()
    assert not msg["success"]


async def test_add_pipeline(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, init_components
) -> None:
    """Test we can add a pipeline."""
    client = await hass_ws_client(hass)
    pipeline_store: PipelineStorageCollection = hass.data[DOMAIN]

    await client.send_json_auto_id(
        {
            "type": "voice_assistant/pipeline/create",
            "conversation_engine": "test_conversation_engine",
            "language": "test_language",
            "name": "test_name",
            "stt_engine": "test_stt_engine",
            "tts_engine": "test_tts_engine",
        }
    )
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] == {
        "conversation_engine": "test_conversation_engine",
        "id": ANY,
        "language": "test_language",
        "name": "test_name",
        "stt_engine": "test_stt_engine",
        "tts_engine": "test_tts_engine",
    }

    assert len(pipeline_store.data) == 1
    pipeline = pipeline_store.data[msg["result"]["id"]]
    assert pipeline == Pipeline(
        conversation_engine="test_conversation_engine",
        id=msg["result"]["id"],
        language="test_language",
        name="test_name",
        stt_engine="test_stt_engine",
        tts_engine="test_tts_engine",
    )


async def test_delete_pipeline(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, init_components
) -> None:
    """Test we can delete a pipeline."""
    client = await hass_ws_client(hass)
    pipeline_store: PipelineStorageCollection = hass.data[DOMAIN]

    await client.send_json_auto_id(
        {
            "type": "voice_assistant/pipeline/create",
            "conversation_engine": "test_conversation_engine",
            "language": "test_language",
            "name": "test_name",
            "stt_engine": "test_stt_engine",
            "tts_engine": "test_tts_engine",
        }
    )
    msg = await client.receive_json()
    assert msg["success"]
    assert len(pipeline_store.data) == 1

    pipeline_id = msg["result"]["id"]

    await client.send_json_auto_id(
        {
            "type": "voice_assistant/pipeline/delete",
            "pipeline_id": pipeline_id,
        }
    )
    msg = await client.receive_json()
    assert msg["success"]
    assert len(pipeline_store.data) == 0

    await client.send_json_auto_id(
        {
            "type": "voice_assistant/pipeline/delete",
            "pipeline_id": pipeline_id,
        }
    )
    msg = await client.receive_json()
    assert not msg["success"]
    assert msg["error"] == {
        "code": "not_found",
        "message": f"Unable to find pipeline_id {pipeline_id}",
    }


async def test_list_pipelines(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, init_components
) -> None:
    """Test we can list pipelines."""
    client = await hass_ws_client(hass)
    pipeline_store: PipelineStorageCollection = hass.data[DOMAIN]

    await client.send_json_auto_id({"type": "voice_assistant/pipeline/list"})
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] == []

    await client.send_json_auto_id(
        {
            "type": "voice_assistant/pipeline/create",
            "conversation_engine": "test_conversation_engine",
            "language": "test_language",
            "name": "test_name",
            "stt_engine": "test_stt_engine",
            "tts_engine": "test_tts_engine",
        }
    )
    msg = await client.receive_json()
    assert msg["success"]
    assert len(pipeline_store.data) == 1

    await client.send_json_auto_id({"type": "voice_assistant/pipeline/list"})
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] == [
        {
            "conversation_engine": "test_conversation_engine",
            "id": ANY,
            "language": "test_language",
            "name": "test_name",
            "stt_engine": "test_stt_engine",
            "tts_engine": "test_tts_engine",
        }
    ]


async def test_update_pipeline(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, init_components
) -> None:
    """Test we can list pipelines."""
    client = await hass_ws_client(hass)
    pipeline_store: PipelineStorageCollection = hass.data[DOMAIN]

    await client.send_json_auto_id(
        {
            "type": "voice_assistant/pipeline/update",
            "conversation_engine": "new_conversation_engine",
            "language": "new_language",
            "name": "new_name",
            "pipeline_id": "no_such_pipeline",
            "stt_engine": "new_stt_engine",
            "tts_engine": "new_tts_engine",
        }
    )
    msg = await client.receive_json()
    assert not msg["success"]
    assert msg["error"] == {
        "code": "not_found",
        "message": "Unable to find pipeline_id no_such_pipeline",
    }

    await client.send_json_auto_id(
        {
            "type": "voice_assistant/pipeline/create",
            "conversation_engine": "test_conversation_engine",
            "language": "test_language",
            "name": "test_name",
            "stt_engine": "test_stt_engine",
            "tts_engine": "test_tts_engine",
        }
    )
    msg = await client.receive_json()
    assert msg["success"]
    pipeline_id = msg["result"]["id"]
    assert len(pipeline_store.data) == 1

    await client.send_json_auto_id(
        {
            "type": "voice_assistant/pipeline/update",
            "conversation_engine": "new_conversation_engine",
            "language": "new_language",
            "name": "new_name",
            "pipeline_id": pipeline_id,
            "stt_engine": "new_stt_engine",
            "tts_engine": "new_tts_engine",
        }
    )
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] == {
        "conversation_engine": "new_conversation_engine",
        "language": "new_language",
        "name": "new_name",
        "id": pipeline_id,
        "stt_engine": "new_stt_engine",
        "tts_engine": "new_tts_engine",
    }

    assert len(pipeline_store.data) == 1
    pipeline = pipeline_store.data[pipeline_id]
    assert pipeline == Pipeline(
        conversation_engine="new_conversation_engine",
        id=pipeline_id,
        language="new_language",
        name="new_name",
        stt_engine="new_stt_engine",
        tts_engine="new_tts_engine",
    )
