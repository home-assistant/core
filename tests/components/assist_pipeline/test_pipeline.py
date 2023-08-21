"""Websocket tests for Voice Assistant integration."""
from typing import Any
from unittest.mock import ANY, AsyncMock, patch

import pytest

from homeassistant.components.assist_pipeline.const import DOMAIN
from homeassistant.components.assist_pipeline.pipeline import (
    STORAGE_KEY,
    STORAGE_VERSION,
    Pipeline,
    PipelineData,
    PipelineStorageCollection,
    async_create_default_pipeline,
    async_get_pipeline,
    async_get_pipelines,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.setup import async_setup_component

from . import MANY_LANGUAGES
from .conftest import MockSttPlatform, MockSttProvider, MockTTSPlatform, MockTTSProvider

from tests.common import MockModule, flush_store, mock_integration, mock_platform


@pytest.fixture(autouse=True)
async def load_homeassistant(hass: HomeAssistant) -> None:
    """Load the homeassistant integration."""
    assert await async_setup_component(hass, "homeassistant", {})


async def test_load_pipelines(hass: HomeAssistant, init_components) -> None:
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


async def test_loading_pipelines_from_storage(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test loading stored pipelines on start."""
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


async def test_create_default_pipeline(
    hass: HomeAssistant, init_supporting_components
) -> None:
    """Test async_create_default_pipeline."""
    assert await async_setup_component(hass, "assist_pipeline", {})

    pipeline_data: PipelineData = hass.data[DOMAIN]
    store = pipeline_data.pipeline_store
    assert len(store.data) == 1

    assert await async_create_default_pipeline(hass, "bla", "bla") is None
    assert await async_create_default_pipeline(hass, "test", "test") == Pipeline(
        conversation_engine="homeassistant",
        conversation_language="en",
        id=ANY,
        language="en",
        name="Home Assistant",
        stt_engine="test",
        stt_language="en-US",
        tts_engine="test",
        tts_language="en-US",
        tts_voice="james_earl_jones",
    )


async def test_get_pipeline(hass: HomeAssistant) -> None:
    """Test async_get_pipeline."""
    assert await async_setup_component(hass, "assist_pipeline", {})

    pipeline_data: PipelineData = hass.data[DOMAIN]
    store = pipeline_data.pipeline_store
    assert len(store.data) == 1

    # Test we get the preferred pipeline if none is specified
    pipeline = async_get_pipeline(hass, None)
    assert pipeline.id == store.async_get_preferred_item()

    # Test getting a specific pipeline
    assert pipeline is async_get_pipeline(hass, pipeline.id)


async def test_get_pipelines(hass: HomeAssistant) -> None:
    """Test async_get_pipelines."""
    assert await async_setup_component(hass, "assist_pipeline", {})

    pipeline_data: PipelineData = hass.data[DOMAIN]
    store = pipeline_data.pipeline_store
    assert len(store.data) == 1

    pipelines = async_get_pipelines(hass)
    assert list(pipelines) == [
        Pipeline(
            conversation_engine="homeassistant",
            conversation_language="en",
            id=ANY,
            language="en",
            name="Home Assistant",
            stt_engine=None,
            stt_language=None,
            tts_engine=None,
            tts_language=None,
            tts_voice=None,
        )
    ]


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
    pipeline = async_get_pipeline(hass, None)
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


@pytest.mark.parametrize(
    (
        "ha_language",
        "ha_country",
        "conv_language",
        "pipeline_language",
        "stt_language",
        "tts_language",
    ),
    [
        ("en", None, "en", "en", "en", "en"),
        ("de", "de", "de", "de", "de", "de"),
        ("de", "ch", "de-CH", "de", "de-CH", "de-CH"),
        ("en", "us", "en", "en", "en", "en"),
        ("en", "uk", "en", "en", "en", "en"),
        ("pt", "pt", "pt", "pt", "pt", "pt"),
        ("pt", "br", "pt-br", "pt", "pt-br", "pt-br"),
    ],
)
async def test_default_pipeline(
    hass: HomeAssistant,
    init_supporting_components,
    mock_stt_provider: MockSttProvider,
    mock_tts_provider: MockTTSProvider,
    ha_language: str,
    ha_country: str | None,
    conv_language: str,
    pipeline_language: str,
    stt_language: str,
    tts_language: str,
) -> None:
    """Test async_get_pipeline."""
    hass.config.country = ha_country
    hass.config.language = ha_language

    with patch.object(
        mock_stt_provider, "_supported_languages", MANY_LANGUAGES
    ), patch.object(mock_tts_provider, "_supported_languages", MANY_LANGUAGES):
        assert await async_setup_component(hass, "assist_pipeline", {})

    pipeline_data: PipelineData = hass.data[DOMAIN]
    store = pipeline_data.pipeline_store
    assert len(store.data) == 1

    # Check the default pipeline
    pipeline = async_get_pipeline(hass, None)
    assert pipeline == Pipeline(
        conversation_engine="homeassistant",
        conversation_language=conv_language,
        id=pipeline.id,
        language=pipeline_language,
        name="Home Assistant",
        stt_engine="test",
        stt_language=stt_language,
        tts_engine="test",
        tts_language=tts_language,
        tts_voice=None,
    )


async def test_default_pipeline_unsupported_stt_language(
    hass: HomeAssistant,
    init_supporting_components,
    mock_stt_provider: MockSttProvider,
) -> None:
    """Test async_get_pipeline."""
    with patch.object(mock_stt_provider, "_supported_languages", ["smurfish"]):
        assert await async_setup_component(hass, "assist_pipeline", {})

    pipeline_data: PipelineData = hass.data[DOMAIN]
    store = pipeline_data.pipeline_store
    assert len(store.data) == 1

    # Check the default pipeline
    pipeline = async_get_pipeline(hass, None)
    assert pipeline == Pipeline(
        conversation_engine="homeassistant",
        conversation_language="en",
        id=pipeline.id,
        language="en",
        name="Home Assistant",
        stt_engine=None,
        stt_language=None,
        tts_engine="test",
        tts_language="en-US",
        tts_voice="james_earl_jones",
    )


async def test_default_pipeline_unsupported_tts_language(
    hass: HomeAssistant,
    init_supporting_components,
    mock_tts_provider: MockTTSProvider,
) -> None:
    """Test async_get_pipeline."""
    with patch.object(mock_tts_provider, "_supported_languages", ["smurfish"]):
        assert await async_setup_component(hass, "assist_pipeline", {})

    pipeline_data: PipelineData = hass.data[DOMAIN]
    store = pipeline_data.pipeline_store
    assert len(store.data) == 1

    # Check the default pipeline
    pipeline = async_get_pipeline(hass, None)
    assert pipeline == Pipeline(
        conversation_engine="homeassistant",
        conversation_language="en",
        id=pipeline.id,
        language="en",
        name="Home Assistant",
        stt_engine="test",
        stt_language="en-US",
        tts_engine=None,
        tts_language=None,
        tts_voice=None,
    )


async def test_default_pipeline_cloud(
    hass: HomeAssistant,
    mock_stt_provider: MockSttProvider,
    mock_tts_provider: MockTTSProvider,
) -> None:
    """Test async_get_pipeline."""

    mock_integration(hass, MockModule("cloud"))
    mock_platform(
        hass,
        "cloud.tts",
        MockTTSPlatform(
            async_get_engine=AsyncMock(return_value=mock_tts_provider),
        ),
    )
    mock_platform(
        hass,
        "cloud.stt",
        MockSttPlatform(
            async_get_engine=AsyncMock(return_value=mock_stt_provider),
        ),
    )
    mock_platform(hass, "test.config_flow")

    assert await async_setup_component(hass, "tts", {"tts": {"platform": "cloud"}})
    assert await async_setup_component(hass, "stt", {"stt": {"platform": "cloud"}})
    assert await async_setup_component(hass, "assist_pipeline", {})

    pipeline_data: PipelineData = hass.data[DOMAIN]
    store = pipeline_data.pipeline_store
    assert len(store.data) == 1

    # Check the default pipeline
    pipeline = async_get_pipeline(hass, None)
    assert pipeline == Pipeline(
        conversation_engine="homeassistant",
        conversation_language="en",
        id=pipeline.id,
        language="en",
        name="Home Assistant Cloud",
        stt_engine="cloud",
        stt_language="en-US",
        tts_engine="cloud",
        tts_language="en-US",
        tts_voice="james_earl_jones",
    )
