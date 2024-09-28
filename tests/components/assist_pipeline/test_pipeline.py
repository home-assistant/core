"""Websocket tests for Voice Assistant integration."""

from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import ANY, patch

import pytest

from homeassistant.components import conversation
from homeassistant.components.assist_pipeline.const import DOMAIN
from homeassistant.components.assist_pipeline.pipeline import (
    STORAGE_KEY,
    STORAGE_VERSION,
    STORAGE_VERSION_MINOR,
    Pipeline,
    PipelineData,
    PipelineStorageCollection,
    PipelineStore,
    async_create_default_pipeline,
    async_get_pipeline,
    async_get_pipelines,
    async_migrate_engine,
    async_update_pipeline,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import MANY_LANGUAGES
from .conftest import MockSTTProviderEntity, MockTTSProvider

from tests.common import flush_store


@pytest.fixture(autouse=True)
async def delay_save_fixture() -> AsyncGenerator[None]:
    """Load the homeassistant integration."""
    with patch("homeassistant.helpers.collection.SAVE_DELAY", new=0):
        yield


@pytest.fixture(autouse=True)
async def load_homeassistant(hass: HomeAssistant) -> None:
    """Load the homeassistant integration."""
    assert await async_setup_component(hass, "homeassistant", {})


@pytest.mark.usefixtures("init_components")
async def test_load_pipelines(hass: HomeAssistant) -> None:
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
            "wake_word_entity": "wakeword_entity_1",
            "wake_word_id": "wakeword_id_1",
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
            "wake_word_entity": "wakeword_entity_2",
            "wake_word_id": "wakeword_id_2",
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
            "wake_word_entity": "wakeword_entity_3",
            "wake_word_id": "wakeword_id_3",
        },
    ]

    pipeline_data: PipelineData = hass.data[DOMAIN]
    store1 = pipeline_data.pipeline_store
    pipeline_ids = [
        (await store1.async_create_item(pipeline)).id for pipeline in pipelines
    ]
    assert len(store1.data) == 4  # 3 manually created plus a default pipeline
    assert store1.async_get_preferred_item() == list(store1.data)[0]

    await store1.async_delete_item(pipeline_ids[1])
    assert len(store1.data) == 3

    store2 = PipelineStorageCollection(
        PipelineStore(
            hass, STORAGE_VERSION, STORAGE_KEY, minor_version=STORAGE_VERSION_MINOR
        )
    )
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
    async_migrate_engine(
        hass,
        "conversation",
        conversation.OLD_HOME_ASSISTANT_AGENT,
        conversation.HOME_ASSISTANT_AGENT,
    )
    id_1 = "01GX8ZWBAQYWNB1XV3EXEZ75DY"
    hass_storage[STORAGE_KEY] = {
        "version": STORAGE_VERSION,
        "minor_version": STORAGE_VERSION_MINOR,
        "key": "assist_pipeline.pipelines",
        "data": {
            "items": [
                {
                    "conversation_engine": conversation.OLD_HOME_ASSISTANT_AGENT,
                    "conversation_language": "language_1",
                    "id": id_1,
                    "language": "language_1",
                    "name": "name_1",
                    "stt_engine": "stt_engine_1",
                    "stt_language": "language_1",
                    "tts_engine": "tts_engine_1",
                    "tts_language": "language_1",
                    "tts_voice": "Arnold Schwarzenegger",
                    "wake_word_entity": "wakeword_entity_1",
                    "wake_word_id": "wakeword_id_1",
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
                    "wake_word_entity": "wakeword_entity_2",
                    "wake_word_id": "wakeword_id_2",
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
                    "wake_word_entity": "wakeword_entity_3",
                    "wake_word_id": "wakeword_id_3",
                },
            ],
            "preferred_item": id_1,
        },
    }

    assert await async_setup_component(hass, "assist_pipeline", {})

    pipeline_data: PipelineData = hass.data[DOMAIN]
    store = pipeline_data.pipeline_store
    assert len(store.data) == 3
    assert store.async_get_preferred_item() == id_1
    assert store.data[id_1].conversation_engine == conversation.HOME_ASSISTANT_AGENT


async def test_migrate_pipeline_store(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test loading stored pipelines from an older version."""
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


@pytest.mark.usefixtures("init_supporting_components")
async def test_create_default_pipeline(hass: HomeAssistant) -> None:
    """Test async_create_default_pipeline."""
    assert await async_setup_component(hass, "assist_pipeline", {})

    pipeline_data: PipelineData = hass.data[DOMAIN]
    store = pipeline_data.pipeline_store
    assert len(store.data) == 1

    assert (
        await async_create_default_pipeline(
            hass,
            stt_engine_id="bla",
            tts_engine_id="bla",
            pipeline_name="Bla pipeline",
        )
        is None
    )
    assert await async_create_default_pipeline(
        hass,
        stt_engine_id="test",
        tts_engine_id="test",
        pipeline_name="Test pipeline",
    ) == Pipeline(
        conversation_engine="conversation.home_assistant",
        conversation_language="en",
        id=ANY,
        language="en",
        name="Test pipeline",
        stt_engine="test",
        stt_language="en-US",
        tts_engine="test",
        tts_language="en-US",
        tts_voice="james_earl_jones",
        wake_word_entity=None,
        wake_word_id=None,
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
            conversation_engine="conversation.home_assistant",
            conversation_language="en",
            id=ANY,
            language="en",
            name="Home Assistant",
            stt_engine=None,
            stt_language=None,
            tts_engine=None,
            tts_language=None,
            tts_voice=None,
            wake_word_entity=None,
            wake_word_id=None,
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
        conversation_engine="conversation.home_assistant",
        conversation_language=conv_language,
        id=pipeline.id,
        language=pipeline_language,
        name="Home Assistant",
        stt_engine=None,
        stt_language=None,
        tts_engine=None,
        tts_language=None,
        tts_voice=None,
        wake_word_entity=None,
        wake_word_id=None,
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
@pytest.mark.usefixtures("init_supporting_components")
async def test_default_pipeline(
    hass: HomeAssistant,
    mock_stt_provider_entity: MockSTTProviderEntity,
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

    with (
        patch.object(mock_stt_provider_entity, "_supported_languages", MANY_LANGUAGES),
        patch.object(mock_tts_provider, "_supported_languages", MANY_LANGUAGES),
    ):
        assert await async_setup_component(hass, "assist_pipeline", {})

    pipeline_data: PipelineData = hass.data[DOMAIN]
    store = pipeline_data.pipeline_store
    assert len(store.data) == 1

    # Check the default pipeline
    pipeline = async_get_pipeline(hass, None)
    assert pipeline == Pipeline(
        conversation_engine="conversation.home_assistant",
        conversation_language=conv_language,
        id=pipeline.id,
        language=pipeline_language,
        name="Home Assistant",
        stt_engine="stt.mock_stt",
        stt_language=stt_language,
        tts_engine="test",
        tts_language=tts_language,
        tts_voice=None,
        wake_word_entity=None,
        wake_word_id=None,
    )


@pytest.mark.usefixtures("init_supporting_components")
async def test_default_pipeline_unsupported_stt_language(
    hass: HomeAssistant, mock_stt_provider_entity: MockSTTProviderEntity
) -> None:
    """Test async_get_pipeline."""
    with patch.object(mock_stt_provider_entity, "_supported_languages", ["smurfish"]):
        assert await async_setup_component(hass, "assist_pipeline", {})

    pipeline_data: PipelineData = hass.data[DOMAIN]
    store = pipeline_data.pipeline_store
    assert len(store.data) == 1

    # Check the default pipeline
    pipeline = async_get_pipeline(hass, None)
    assert pipeline == Pipeline(
        conversation_engine="conversation.home_assistant",
        conversation_language="en",
        id=pipeline.id,
        language="en",
        name="Home Assistant",
        stt_engine=None,
        stt_language=None,
        tts_engine="test",
        tts_language="en-US",
        tts_voice="james_earl_jones",
        wake_word_entity=None,
        wake_word_id=None,
    )


@pytest.mark.usefixtures("init_supporting_components")
async def test_default_pipeline_unsupported_tts_language(
    hass: HomeAssistant, mock_tts_provider: MockTTSProvider
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
        conversation_engine="conversation.home_assistant",
        conversation_language="en",
        id=pipeline.id,
        language="en",
        name="Home Assistant",
        stt_engine="stt.mock_stt",
        stt_language="en-US",
        tts_engine=None,
        tts_language=None,
        tts_voice=None,
        wake_word_entity=None,
        wake_word_id=None,
    )


async def test_update_pipeline(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test async_update_pipeline."""
    assert await async_setup_component(hass, "assist_pipeline", {})

    pipelines = async_get_pipelines(hass)
    pipelines = list(pipelines)
    assert pipelines == [
        Pipeline(
            conversation_engine="conversation.home_assistant",
            conversation_language="en",
            id=ANY,
            language="en",
            name="Home Assistant",
            stt_engine=None,
            stt_language=None,
            tts_engine=None,
            tts_language=None,
            tts_voice=None,
            wake_word_entity=None,
            wake_word_id=None,
        )
    ]

    pipeline = pipelines[0]
    await async_update_pipeline(
        hass,
        pipeline,
        conversation_engine="homeassistant_1",
        conversation_language="de",
        language="de",
        name="Home Assistant 1",
        stt_engine="stt.test_1",
        stt_language="de",
        tts_engine="test_1",
        tts_language="de",
        tts_voice="test_voice",
        wake_word_entity="wake_work.test_1",
        wake_word_id="wake_word_id_1",
    )

    pipelines = async_get_pipelines(hass)
    pipelines = list(pipelines)
    pipeline = pipelines[0]
    assert pipelines == [
        Pipeline(
            conversation_engine="homeassistant_1",
            conversation_language="de",
            id=pipeline.id,
            language="de",
            name="Home Assistant 1",
            stt_engine="stt.test_1",
            stt_language="de",
            tts_engine="test_1",
            tts_language="de",
            tts_voice="test_voice",
            wake_word_entity="wake_work.test_1",
            wake_word_id="wake_word_id_1",
        )
    ]
    assert len(hass_storage[STORAGE_KEY]["data"]["items"]) == 1
    assert hass_storage[STORAGE_KEY]["data"]["items"][0] == {
        "conversation_engine": "homeassistant_1",
        "conversation_language": "de",
        "id": pipeline.id,
        "language": "de",
        "name": "Home Assistant 1",
        "stt_engine": "stt.test_1",
        "stt_language": "de",
        "tts_engine": "test_1",
        "tts_language": "de",
        "tts_voice": "test_voice",
        "wake_word_entity": "wake_work.test_1",
        "wake_word_id": "wake_word_id_1",
    }

    await async_update_pipeline(
        hass,
        pipeline,
        stt_engine="stt.test_2",
        stt_language="en",
        tts_engine="test_2",
        tts_language="en",
    )

    pipelines = async_get_pipelines(hass)
    pipelines = list(pipelines)
    assert pipelines == [
        Pipeline(
            conversation_engine="homeassistant_1",
            conversation_language="de",
            id=pipeline.id,
            language="de",
            name="Home Assistant 1",
            stt_engine="stt.test_2",
            stt_language="en",
            tts_engine="test_2",
            tts_language="en",
            tts_voice="test_voice",
            wake_word_entity="wake_work.test_1",
            wake_word_id="wake_word_id_1",
        )
    ]
    assert len(hass_storage[STORAGE_KEY]["data"]["items"]) == 1
    assert hass_storage[STORAGE_KEY]["data"]["items"][0] == {
        "conversation_engine": "homeassistant_1",
        "conversation_language": "de",
        "id": pipeline.id,
        "language": "de",
        "name": "Home Assistant 1",
        "stt_engine": "stt.test_2",
        "stt_language": "en",
        "tts_engine": "test_2",
        "tts_language": "en",
        "tts_voice": "test_voice",
        "wake_word_entity": "wake_work.test_1",
        "wake_word_id": "wake_word_id_1",
    }


@pytest.mark.usefixtures("init_supporting_components")
async def test_migrate_after_load(hass: HomeAssistant) -> None:
    """Test migrating an engine after done loading."""
    assert await async_setup_component(hass, "assist_pipeline", {})

    pipeline_data: PipelineData = hass.data[DOMAIN]
    store = pipeline_data.pipeline_store
    assert len(store.data) == 1

    assert (
        await async_create_default_pipeline(
            hass,
            stt_engine_id="bla",
            tts_engine_id="bla",
            pipeline_name="Bla pipeline",
        )
        is None
    )
    pipeline = await async_create_default_pipeline(
        hass,
        stt_engine_id="test",
        tts_engine_id="test",
        pipeline_name="Test pipeline",
    )
    assert pipeline is not None

    async_migrate_engine(hass, "stt", "test", "stt.test")
    async_migrate_engine(hass, "tts", "test", "tts.test")

    await hass.async_block_till_done(wait_background_tasks=True)

    pipeline_updated = async_get_pipeline(hass, pipeline.id)

    assert pipeline_updated.stt_engine == "stt.test"
    assert pipeline_updated.tts_engine == "tts.test"
