"""Websocket tests for Voice Assistant integration."""
from typing import Any

import pytest

from homeassistant.components.assist_pipeline.const import DOMAIN
from homeassistant.components.assist_pipeline.pipeline import (
    STORAGE_KEY,
    STORAGE_VERSION,
    Pipeline,
    PipelineData,
    PipelineStorageCollection,
    async_get_pipeline,
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
            "conversation_language": "language_1",
            "language": "language_1",
            "name": "name_1",
            "stt_engine": "stt_engine_1",
            "stt_language": "language_1",
            "tts_engine": "tts_engine_1",
            "tts_language": "language_1",
            "tts_voice": "Arnold Schwarzenegger",
        },
        {
            "conversation_engine": "conversation_engine_2",
            "conversation_language": "language_2",
            "language": "language_2",
            "name": "name_2",
            "stt_engine": "stt_engine_2",
            "stt_language": "language_1",
            "tts_engine": "tts_engine_2",
            "tts_language": "language_2",
            "tts_voice": "The Voice",
        },
        {
            "conversation_engine": "conversation_engine_3",
            "conversation_language": "language_3",
            "language": "language_3",
            "name": "name_3",
            "stt_engine": None,
            "stt_language": None,
            "tts_engine": None,
            "tts_language": None,
            "tts_voice": None,
        },
    ]
    pipeline_ids = []

    pipeline_data: PipelineData = hass.data[DOMAIN]
    store1 = pipeline_data.pipeline_store
    for pipeline in pipelines:
        pipeline_ids.append((await store1.async_create_item(pipeline)).id)
    assert len(store1.data) == 4  # 3 manually created plus a default pipeline
    assert store1.async_get_preferred_item() == list(store1.data)[0]

    await store1.async_delete_item(pipeline_ids[1])
    assert len(store1.data) == 3

    store2 = PipelineStorageCollection(Store(hass, STORAGE_VERSION, STORAGE_KEY))
    await flush_store(store1.store)
    await store2.async_load()

    assert len(store2.data) == 3

    assert store1.data is not store2.data
    assert store1.data == store2.data
    assert store1.async_get_preferred_item() == store2.async_get_preferred_item()


async def test_loading_datasets_from_storage(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test loading stored datasets on start."""
    hass_storage[STORAGE_KEY] = {
        "version": 1,
        "minor_version": 1,
        "key": "assist_pipeline.pipelines",
        "data": {
            "items": [
                {
                    "conversation_engine": "conversation_engine_1",
                    "conversation_language": "language_1",
                    "id": "01GX8ZWBAQYWNB1XV3EXEZ75DY",
                    "language": "language_1",
                    "name": "name_1",
                    "stt_engine": "stt_engine_1",
                    "stt_language": "language_1",
                    "tts_engine": "tts_engine_1",
                    "tts_language": "language_1",
                    "tts_voice": "Arnold Schwarzenegger",
                },
                {
                    "conversation_engine": "conversation_engine_2",
                    "conversation_language": "language_2",
                    "id": "01GX8ZWBAQTKFQNK4W7Q4CTRCX",
                    "language": "language_2",
                    "name": "name_2",
                    "stt_engine": "stt_engine_2",
                    "stt_language": "language_2",
                    "tts_engine": "tts_engine_2",
                    "tts_language": "language_2",
                    "tts_voice": "The Voice",
                },
                {
                    "conversation_engine": "conversation_engine_3",
                    "conversation_language": "language_3",
                    "id": "01GX8ZWBAQSV1HP3WGJPFWEJ8J",
                    "language": "language_3",
                    "name": "name_3",
                    "stt_engine": None,
                    "stt_language": None,
                    "tts_engine": None,
                    "tts_language": None,
                    "tts_voice": None,
                },
            ],
            "preferred_item": "01GX8ZWBAQYWNB1XV3EXEZ75DY",
        },
    }

    assert await async_setup_component(hass, "assist_pipeline", {})

    pipeline_data: PipelineData = hass.data[DOMAIN]
    store = pipeline_data.pipeline_store
    assert len(store.data) == 3
    assert store.async_get_preferred_item() == "01GX8ZWBAQYWNB1XV3EXEZ75DY"


async def test_get_pipeline(hass: HomeAssistant) -> None:
    """Test async_get_pipeline."""
    assert await async_setup_component(hass, "assist_pipeline", {})

    pipeline_data: PipelineData = hass.data[DOMAIN]
    store = pipeline_data.pipeline_store
    assert len(store.data) == 1

    # Test we get the preferred pipeline if none is speocifed
    pipeline = await async_get_pipeline(hass, None)
    assert pipeline.id == store.async_get_preferred_item()

    # Test getting a specific pipeline
    assert pipeline is await async_get_pipeline(hass, pipeline.id)


@pytest.mark.parametrize(
    ("ha_language", "ha_country", "conv_language", "pipeline_language"),
    [
        ("en", None, "en", "en"),
        ("de", "de", "de", "de"),
        ("de", "ch", "de-CH", "de"),
        ("en", "us", "en", "en"),
        ("en", "uk", "en", "en"),
        ("pt", "pt", "pt", "pt"),
        ("pt", "br", "pt-br", "pt"),
        ("zh-Hans", "cn", "zh-cn", "zh-Hans"),
        ("zh-Hant", "hk", "zh-hk", "zh-Hant"),
        ("zh-Hant", "tw", "zh-hk", "zh-Hant"),
    ],
)
async def test_default_pipeline_no_stt_tts(
    hass: HomeAssistant,
    ha_language: str,
    ha_country: str | None,
    conv_language: str,
    pipeline_language: str,
) -> None:
    """Test async_get_pipeline."""
    hass.config.country = ha_country
    hass.config.language = ha_language
    assert await async_setup_component(hass, "assist_pipeline", {})

    pipeline_data: PipelineData = hass.data[DOMAIN]
    store = pipeline_data.pipeline_store
    assert len(store.data) == 1

    # Check the default pipeline
    pipeline = await async_get_pipeline(hass, None)
    assert pipeline == Pipeline(
        conversation_engine="homeassistant",
        conversation_language=conv_language,
        id=pipeline.id,
        language=pipeline_language,
        name="Home Assistant",
        stt_engine=None,
        stt_language=None,
        tts_engine=None,
        tts_language=None,
        tts_voice=None,
    )


async def test_default_pipeline(hass: HomeAssistant, init_components) -> None:
    """Test async_get_pipeline."""
    assert await async_setup_component(hass, "assist_pipeline", {})

    pipeline_data: PipelineData = hass.data[DOMAIN]
    store = pipeline_data.pipeline_store
    assert len(store.data) == 1

    # Check the default pipeline
    pipeline = await async_get_pipeline(hass, None)
    assert pipeline == Pipeline(
        conversation_engine="homeassistant",
        conversation_language="en",
        id=pipeline.id,
        language="en",
        name="Home Assistant",
        stt_engine="test",
        stt_language="en-US",
        tts_engine="test",
        tts_language="en-US",
        tts_voice=None,
    )
