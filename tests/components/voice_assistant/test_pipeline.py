"""Websocket tests for Voice Assistant integration."""
from typing import Any

from homeassistant.components.voice_assistant.const import DOMAIN
from homeassistant.components.voice_assistant.pipeline import (
    STORAGE_KEY,
    STORAGE_VERSION,
    PipelineStorageCollection,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.setup import async_setup_component

from tests.common import flush_store


async def test_load_datasets(hass: HomeAssistant, init_components) -> None:
    """Make sure that we can load/save data correctly."""

    pipelines = [
        {
            "conversation_engine": "conversation_engine_1",
            "language": "language_1",
            "name": "name_1",
            "stt_engine": "stt_engine_1",
            "tts_engine": "tts_engine_1",
        },
        {
            "conversation_engine": "conversation_engine_2",
            "language": "language_2",
            "name": "name_2",
            "stt_engine": "stt_engine_2",
            "tts_engine": "tts_engine_2",
        },
        {
            "conversation_engine": "conversation_engine_3",
            "language": "language_3",
            "name": "name_3",
            "stt_engine": "stt_engine_3",
            "tts_engine": "tts_engine_3",
        },
    ]
    pipeline_ids = []

    store1: PipelineStorageCollection = hass.data[DOMAIN]
    for pipeline in pipelines:
        pipeline_ids.append((await store1.async_create_item(pipeline)).id)
    assert len(store1.data) == 3

    await store1.async_delete_item(pipeline_ids[1])
    assert len(store1.data) == 2

    store2 = PipelineStorageCollection(Store(hass, STORAGE_VERSION, STORAGE_KEY))
    await flush_store(store1.store)
    await store2.async_load()

    assert len(store2.data) == 2

    assert store1.data is not store2.data
    assert store1.data == store2.data


async def test_loading_datasets_from_storage(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test loading stored datasets on start."""
    hass_storage[STORAGE_KEY] = {
        "version": 1,
        "minor_version": 1,
        "key": "voice_assistant.pipelines",
        "data": {
            "items": [
                {
                    "conversation_engine": "conversation_engine_1",
                    "id": "01GX8ZWBAQYWNB1XV3EXEZ75DY",
                    "language": "language_1",
                    "name": "name_1",
                    "stt_engine": "stt_engine_1",
                    "tts_engine": "tts_engine_1",
                },
                {
                    "conversation_engine": "conversation_engine_2",
                    "id": "01GX8ZWBAQTKFQNK4W7Q4CTRCX",
                    "language": "language_2",
                    "name": "name_2",
                    "stt_engine": "stt_engine_2",
                    "tts_engine": "tts_engine_2",
                },
                {
                    "conversation_engine": "conversation_engine_3",
                    "id": "01GX8ZWBAQSV1HP3WGJPFWEJ8J",
                    "language": "language_3",
                    "name": "name_3",
                    "stt_engine": "stt_engine_3",
                    "tts_engine": "tts_engine_3",
                },
            ]
        },
    }

    assert await async_setup_component(hass, "voice_assistant", {})

    store: PipelineStorageCollection = hass.data[DOMAIN]
    assert len(store.data) == 3
