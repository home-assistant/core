"""Websocket tests for Voice Assistant integration."""

from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import ANY, patch

from hassil.recognize import Intent, IntentData, RecognizeResult
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components import (
    assist_pipeline,
    conversation,
    media_source,
    stt,
    tts,
)
from homeassistant.components.assist_pipeline.const import DOMAIN
from homeassistant.components.assist_pipeline.pipeline import (
    STORAGE_KEY,
    STORAGE_VERSION,
    STORAGE_VERSION_MINOR,
    Pipeline,
    PipelineData,
    PipelineStorageCollection,
    PipelineStore,
    _async_local_fallback_intent_filter,
    async_create_default_pipeline,
    async_get_pipeline,
    async_get_pipelines,
    async_migrate_engine,
    async_update_pipeline,
)
from homeassistant.const import MATCH_ALL
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import chat_session, intent
from homeassistant.setup import async_setup_component

from . import MANY_LANGUAGES, process_events
from .conftest import (
    MockSTTProvider,
    MockSTTProviderEntity,
    MockTTSProvider,
    MockWakeWordEntity,
    make_10ms_chunk,
)

from tests.common import flush_store
from tests.typing import ClientSessionGenerator, WebSocketGenerator


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
        "prefer_local_intents": False,
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
        "prefer_local_intents": False,
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


def test_fallback_intent_filter() -> None:
    """Test that we filter the right things."""
    assert (
        _async_local_fallback_intent_filter(
            RecognizeResult(
                intent=Intent(intent.INTENT_GET_STATE),
                intent_data=IntentData([]),
                entities={},
                entities_list=[],
            )
        )
        is True
    )
    assert (
        _async_local_fallback_intent_filter(
            RecognizeResult(
                intent=Intent(intent.INTENT_NEVERMIND),
                intent_data=IntentData([]),
                entities={},
                entities_list=[],
            )
        )
        is False
    )
    assert (
        _async_local_fallback_intent_filter(
            RecognizeResult(
                intent=Intent(intent.INTENT_TURN_ON),
                intent_data=IntentData([]),
                entities={},
                entities_list=[],
            )
        )
        is False
    )


async def test_wake_word_detection_aborted(
    hass: HomeAssistant,
    mock_stt_provider: MockSTTProvider,
    mock_wake_word_provider_entity: MockWakeWordEntity,
    init_components,
    pipeline_data: assist_pipeline.pipeline.PipelineData,
    mock_chat_session: chat_session.ChatSession,
    snapshot: SnapshotAssertion,
) -> None:
    """Test wake word stream is first detected, then aborted."""

    events: list[assist_pipeline.PipelineEvent] = []

    async def audio_data():
        yield make_10ms_chunk(b"silence!")
        yield make_10ms_chunk(b"wake word!")
        yield make_10ms_chunk(b"part1")
        yield make_10ms_chunk(b"part2")
        yield b""

    pipeline_store = pipeline_data.pipeline_store
    pipeline_id = pipeline_store.async_get_preferred_item()
    pipeline = assist_pipeline.pipeline.async_get_pipeline(hass, pipeline_id)

    pipeline_input = assist_pipeline.pipeline.PipelineInput(
        session=mock_chat_session,
        device_id=None,
        stt_metadata=stt.SpeechMetadata(
            language="",
            format=stt.AudioFormats.WAV,
            codec=stt.AudioCodecs.PCM,
            bit_rate=stt.AudioBitRates.BITRATE_16,
            sample_rate=stt.AudioSampleRates.SAMPLERATE_16000,
            channel=stt.AudioChannels.CHANNEL_MONO,
        ),
        stt_stream=audio_data(),
        run=assist_pipeline.pipeline.PipelineRun(
            hass,
            context=Context(),
            pipeline=pipeline,
            start_stage=assist_pipeline.PipelineStage.WAKE_WORD,
            end_stage=assist_pipeline.PipelineStage.TTS,
            event_callback=events.append,
            tts_audio_output=None,
            wake_word_settings=assist_pipeline.WakeWordSettings(
                audio_seconds_to_buffer=1.5
            ),
            audio_settings=assist_pipeline.AudioSettings(is_vad_enabled=False),
        ),
    )
    await pipeline_input.validate()

    updates = pipeline.to_json()
    updates.pop("id")
    await pipeline_store.async_update_item(
        pipeline_id,
        updates,
    )
    await pipeline_input.execute()

    assert process_events(events) == snapshot


def test_pipeline_run_equality(hass: HomeAssistant, init_components) -> None:
    """Test that pipeline run equality uses unique id."""

    def event_callback(event):
        pass

    pipeline = assist_pipeline.pipeline.async_get_pipeline(hass)
    run_1 = assist_pipeline.pipeline.PipelineRun(
        hass,
        context=Context(),
        pipeline=pipeline,
        start_stage=assist_pipeline.PipelineStage.STT,
        end_stage=assist_pipeline.PipelineStage.TTS,
        event_callback=event_callback,
    )
    run_2 = assist_pipeline.pipeline.PipelineRun(
        hass,
        context=Context(),
        pipeline=pipeline,
        start_stage=assist_pipeline.PipelineStage.STT,
        end_stage=assist_pipeline.PipelineStage.TTS,
        event_callback=event_callback,
    )

    assert run_1 == run_1  # noqa: PLR0124
    assert run_1 != run_2
    assert run_1 != 1234


async def test_tts_audio_output(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_tts_provider: MockTTSProvider,
    init_components,
    pipeline_data: assist_pipeline.pipeline.PipelineData,
    mock_chat_session: chat_session.ChatSession,
    snapshot: SnapshotAssertion,
) -> None:
    """Test using tts_audio_output with wav sets options correctly."""
    client = await hass_client()
    assert await async_setup_component(hass, media_source.DOMAIN, {})

    events: list[assist_pipeline.PipelineEvent] = []

    pipeline_store = pipeline_data.pipeline_store
    pipeline_id = pipeline_store.async_get_preferred_item()
    pipeline = assist_pipeline.pipeline.async_get_pipeline(hass, pipeline_id)

    pipeline_input = assist_pipeline.pipeline.PipelineInput(
        tts_input="This is a test.",
        session=mock_chat_session,
        device_id=None,
        run=assist_pipeline.pipeline.PipelineRun(
            hass,
            context=Context(),
            pipeline=pipeline,
            start_stage=assist_pipeline.PipelineStage.TTS,
            end_stage=assist_pipeline.PipelineStage.TTS,
            event_callback=events.append,
            tts_audio_output="wav",
        ),
    )
    await pipeline_input.validate()

    # Verify TTS audio settings
    assert pipeline_input.run.tts_stream.options is not None
    assert pipeline_input.run.tts_stream.options.get(tts.ATTR_PREFERRED_FORMAT) == "wav"
    assert (
        pipeline_input.run.tts_stream.options.get(tts.ATTR_PREFERRED_SAMPLE_RATE)
        == 16000
    )
    assert (
        pipeline_input.run.tts_stream.options.get(tts.ATTR_PREFERRED_SAMPLE_CHANNELS)
        == 1
    )

    with patch.object(mock_tts_provider, "get_tts_audio") as mock_get_tts_audio:
        await pipeline_input.execute()

        for event in events:
            if event.type == assist_pipeline.PipelineEventType.TTS_END:
                # We must fetch the media URL to trigger the TTS
                assert event.data
                await client.get(event.data["tts_output"]["url"])

        # Ensure that no unsupported options were passed in
        assert mock_get_tts_audio.called
        options = mock_get_tts_audio.call_args_list[0].kwargs["options"]
        extra_options = set(options).difference(mock_tts_provider.supported_options)
        assert len(extra_options) == 0, extra_options


async def test_tts_wav_preferred_format(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_tts_provider: MockTTSProvider,
    init_components,
    mock_chat_session: chat_session.ChatSession,
    pipeline_data: assist_pipeline.pipeline.PipelineData,
) -> None:
    """Test that preferred format options are given to the TTS system if supported."""
    client = await hass_client()
    assert await async_setup_component(hass, media_source.DOMAIN, {})

    events: list[assist_pipeline.PipelineEvent] = []

    pipeline_store = pipeline_data.pipeline_store
    pipeline_id = pipeline_store.async_get_preferred_item()
    pipeline = assist_pipeline.pipeline.async_get_pipeline(hass, pipeline_id)

    pipeline_input = assist_pipeline.pipeline.PipelineInput(
        tts_input="This is a test.",
        session=mock_chat_session,
        device_id=None,
        run=assist_pipeline.pipeline.PipelineRun(
            hass,
            context=Context(),
            pipeline=pipeline,
            start_stage=assist_pipeline.PipelineStage.TTS,
            end_stage=assist_pipeline.PipelineStage.TTS,
            event_callback=events.append,
            tts_audio_output="wav",
        ),
    )
    await pipeline_input.validate()

    # Make the TTS provider support preferred format options
    supported_options = list(mock_tts_provider.supported_options or [])
    supported_options.extend(
        [
            tts.ATTR_PREFERRED_FORMAT,
            tts.ATTR_PREFERRED_SAMPLE_RATE,
            tts.ATTR_PREFERRED_SAMPLE_CHANNELS,
            tts.ATTR_PREFERRED_SAMPLE_BYTES,
        ]
    )

    with (
        patch.object(mock_tts_provider, "_supported_options", supported_options),
        patch.object(mock_tts_provider, "get_tts_audio") as mock_get_tts_audio,
    ):
        await pipeline_input.execute()

        for event in events:
            if event.type == assist_pipeline.PipelineEventType.TTS_END:
                # We must fetch the media URL to trigger the TTS
                assert event.data
                await client.get(event.data["tts_output"]["url"])

        assert mock_get_tts_audio.called
        options = mock_get_tts_audio.call_args_list[0].kwargs["options"]

        # We should have received preferred format options in get_tts_audio
        assert options.get(tts.ATTR_PREFERRED_FORMAT) == "wav"
        assert int(options.get(tts.ATTR_PREFERRED_SAMPLE_RATE)) == 16000
        assert int(options.get(tts.ATTR_PREFERRED_SAMPLE_CHANNELS)) == 1
        assert int(options.get(tts.ATTR_PREFERRED_SAMPLE_BYTES)) == 2


async def test_tts_dict_preferred_format(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_tts_provider: MockTTSProvider,
    init_components,
    mock_chat_session: chat_session.ChatSession,
    pipeline_data: assist_pipeline.pipeline.PipelineData,
) -> None:
    """Test that preferred format options are given to the TTS system if supported."""
    client = await hass_client()
    assert await async_setup_component(hass, media_source.DOMAIN, {})

    events: list[assist_pipeline.PipelineEvent] = []

    pipeline_store = pipeline_data.pipeline_store
    pipeline_id = pipeline_store.async_get_preferred_item()
    pipeline = assist_pipeline.pipeline.async_get_pipeline(hass, pipeline_id)

    pipeline_input = assist_pipeline.pipeline.PipelineInput(
        tts_input="This is a test.",
        session=mock_chat_session,
        device_id=None,
        run=assist_pipeline.pipeline.PipelineRun(
            hass,
            context=Context(),
            pipeline=pipeline,
            start_stage=assist_pipeline.PipelineStage.TTS,
            end_stage=assist_pipeline.PipelineStage.TTS,
            event_callback=events.append,
            tts_audio_output={
                tts.ATTR_PREFERRED_FORMAT: "flac",
                tts.ATTR_PREFERRED_SAMPLE_RATE: 48000,
                tts.ATTR_PREFERRED_SAMPLE_CHANNELS: 2,
                tts.ATTR_PREFERRED_SAMPLE_BYTES: 2,
            },
        ),
    )
    await pipeline_input.validate()

    # Make the TTS provider support preferred format options
    supported_options = list(mock_tts_provider.supported_options or [])
    supported_options.extend(
        [
            tts.ATTR_PREFERRED_FORMAT,
            tts.ATTR_PREFERRED_SAMPLE_RATE,
            tts.ATTR_PREFERRED_SAMPLE_CHANNELS,
            tts.ATTR_PREFERRED_SAMPLE_BYTES,
        ]
    )

    with (
        patch.object(mock_tts_provider, "_supported_options", supported_options),
        patch.object(mock_tts_provider, "get_tts_audio") as mock_get_tts_audio,
    ):
        await pipeline_input.execute()

        for event in events:
            if event.type == assist_pipeline.PipelineEventType.TTS_END:
                # We must fetch the media URL to trigger the TTS
                assert event.data
                await client.get(event.data["tts_output"]["url"])

        assert mock_get_tts_audio.called
        options = mock_get_tts_audio.call_args_list[0].kwargs["options"]

        # We should have received preferred format options in get_tts_audio
        assert options.get(tts.ATTR_PREFERRED_FORMAT) == "flac"
        assert int(options.get(tts.ATTR_PREFERRED_SAMPLE_RATE)) == 48000
        assert int(options.get(tts.ATTR_PREFERRED_SAMPLE_CHANNELS)) == 2
        assert int(options.get(tts.ATTR_PREFERRED_SAMPLE_BYTES)) == 2


async def test_sentence_trigger_overrides_conversation_agent(
    hass: HomeAssistant,
    init_components,
    mock_chat_session: chat_session.ChatSession,
    pipeline_data: assist_pipeline.pipeline.PipelineData,
) -> None:
    """Test that sentence triggers are checked before a non-default conversation agent."""
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": {
                "trigger": {
                    "platform": "conversation",
                    "command": [
                        "test trigger sentence",
                    ],
                },
                "action": {
                    "set_conversation_response": "test trigger response",
                },
            }
        },
    )

    events: list[assist_pipeline.PipelineEvent] = []

    pipeline_store = pipeline_data.pipeline_store
    pipeline_id = pipeline_store.async_get_preferred_item()
    pipeline = assist_pipeline.pipeline.async_get_pipeline(hass, pipeline_id)

    pipeline_input = assist_pipeline.pipeline.PipelineInput(
        intent_input="test trigger sentence",
        session=mock_chat_session,
        run=assist_pipeline.pipeline.PipelineRun(
            hass,
            context=Context(),
            pipeline=pipeline,
            start_stage=assist_pipeline.PipelineStage.INTENT,
            end_stage=assist_pipeline.PipelineStage.INTENT,
            event_callback=events.append,
            intent_agent="test-agent",  # not the default agent
        ),
    )

    # Ensure prepare succeeds
    with patch(
        "homeassistant.components.assist_pipeline.pipeline.conversation.async_get_agent_info",
        return_value=conversation.AgentInfo(id="test-agent", name="Test Agent"),
    ):
        await pipeline_input.validate()

    with patch(
        "homeassistant.components.assist_pipeline.pipeline.conversation.async_converse"
    ) as mock_async_converse:
        await pipeline_input.execute()

        # Sentence trigger should have been handled
        mock_async_converse.assert_not_called()

        # Verify sentence trigger response
        intent_end_event = next(
            (
                e
                for e in events
                if e.type == assist_pipeline.PipelineEventType.INTENT_END
            ),
            None,
        )
        assert (intent_end_event is not None) and intent_end_event.data
        assert (
            intent_end_event.data["intent_output"]["response"]["speech"]["plain"][
                "speech"
            ]
            == "test trigger response"
        )


async def test_prefer_local_intents(
    hass: HomeAssistant,
    init_components,
    mock_chat_session: chat_session.ChatSession,
    pipeline_data: assist_pipeline.pipeline.PipelineData,
) -> None:
    """Test that the default agent is checked first when local intents are preferred."""
    events: list[assist_pipeline.PipelineEvent] = []

    # Reuse custom sentences in test config
    class OrderBeerIntentHandler(intent.IntentHandler):
        intent_type = "OrderBeer"

        async def async_handle(
            self, intent_obj: intent.Intent
        ) -> intent.IntentResponse:
            response = intent_obj.create_response()
            response.async_set_speech("Order confirmed")
            return response

    handler = OrderBeerIntentHandler()
    intent.async_register(hass, handler)

    # Fake a test agent and prefer local intents
    pipeline_store = pipeline_data.pipeline_store
    pipeline_id = pipeline_store.async_get_preferred_item()
    pipeline = assist_pipeline.pipeline.async_get_pipeline(hass, pipeline_id)
    await assist_pipeline.pipeline.async_update_pipeline(
        hass, pipeline, conversation_engine="test-agent", prefer_local_intents=True
    )
    pipeline = assist_pipeline.pipeline.async_get_pipeline(hass, pipeline_id)

    pipeline_input = assist_pipeline.pipeline.PipelineInput(
        intent_input="I'd like to order a stout please",
        session=mock_chat_session,
        run=assist_pipeline.pipeline.PipelineRun(
            hass,
            context=Context(),
            pipeline=pipeline,
            start_stage=assist_pipeline.PipelineStage.INTENT,
            end_stage=assist_pipeline.PipelineStage.INTENT,
            event_callback=events.append,
        ),
    )

    # Ensure prepare succeeds
    with patch(
        "homeassistant.components.assist_pipeline.pipeline.conversation.async_get_agent_info",
        return_value=conversation.AgentInfo(id="test-agent", name="Test Agent"),
    ):
        await pipeline_input.validate()

    with patch(
        "homeassistant.components.assist_pipeline.pipeline.conversation.async_converse"
    ) as mock_async_converse:
        await pipeline_input.execute()

        # Test agent should not have been called
        mock_async_converse.assert_not_called()

        # Verify local intent response
        intent_end_event = next(
            (
                e
                for e in events
                if e.type == assist_pipeline.PipelineEventType.INTENT_END
            ),
            None,
        )
        assert (intent_end_event is not None) and intent_end_event.data
        assert (
            intent_end_event.data["intent_output"]["response"]["speech"]["plain"][
                "speech"
            ]
            == "Order confirmed"
        )


async def test_intent_continue_conversation(
    hass: HomeAssistant,
    init_components,
    mock_chat_session: chat_session.ChatSession,
    pipeline_data: assist_pipeline.pipeline.PipelineData,
) -> None:
    """Test that a conversation agent flagging continue conversation gets response."""
    events: list[assist_pipeline.PipelineEvent] = []

    # Fake a test agent and prefer local intents
    pipeline_store = pipeline_data.pipeline_store
    pipeline_id = pipeline_store.async_get_preferred_item()
    pipeline = assist_pipeline.pipeline.async_get_pipeline(hass, pipeline_id)
    await assist_pipeline.pipeline.async_update_pipeline(
        hass, pipeline, conversation_engine="test-agent"
    )
    pipeline = assist_pipeline.pipeline.async_get_pipeline(hass, pipeline_id)

    pipeline_input = assist_pipeline.pipeline.PipelineInput(
        intent_input="Set a timer",
        session=mock_chat_session,
        run=assist_pipeline.pipeline.PipelineRun(
            hass,
            context=Context(),
            pipeline=pipeline,
            start_stage=assist_pipeline.PipelineStage.INTENT,
            end_stage=assist_pipeline.PipelineStage.INTENT,
            event_callback=events.append,
        ),
    )

    # Ensure prepare succeeds
    with patch(
        "homeassistant.components.assist_pipeline.pipeline.conversation.async_get_agent_info",
        return_value=conversation.AgentInfo(id="test-agent", name="Test Agent"),
    ):
        await pipeline_input.validate()

    response = intent.IntentResponse("en")
    response.async_set_speech("For how long?")

    with patch(
        "homeassistant.components.assist_pipeline.pipeline.conversation.async_converse",
        return_value=conversation.ConversationResult(
            response=response,
            conversation_id=mock_chat_session.conversation_id,
            continue_conversation=True,
        ),
    ) as mock_async_converse:
        await pipeline_input.execute()

        mock_async_converse.assert_called()

    results = [
        event.data
        for event in events
        if event.type
        in (
            assist_pipeline.PipelineEventType.INTENT_START,
            assist_pipeline.PipelineEventType.INTENT_END,
        )
    ]
    assert results[1]["intent_output"]["continue_conversation"] is True

    # Change conversation agent to default one and register sentence trigger that should not be called
    await assist_pipeline.pipeline.async_update_pipeline(
        hass, pipeline, conversation_engine=None
    )
    pipeline = assist_pipeline.pipeline.async_get_pipeline(hass, pipeline_id)
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": {
                "trigger": {
                    "platform": "conversation",
                    "command": ["Hello"],
                },
                "action": {
                    "set_conversation_response": "test trigger response",
                },
            }
        },
    )

    # Because we did continue conversation, it should respond to the test agent again.
    events.clear()

    pipeline_input = assist_pipeline.pipeline.PipelineInput(
        intent_input="Hello",
        session=mock_chat_session,
        run=assist_pipeline.pipeline.PipelineRun(
            hass,
            context=Context(),
            pipeline=pipeline,
            start_stage=assist_pipeline.PipelineStage.INTENT,
            end_stage=assist_pipeline.PipelineStage.INTENT,
            event_callback=events.append,
        ),
    )

    # Ensure prepare succeeds
    with patch(
        "homeassistant.components.assist_pipeline.pipeline.conversation.async_get_agent_info",
        return_value=conversation.AgentInfo(id="test-agent", name="Test Agent"),
    ) as mock_prepare:
        await pipeline_input.validate()

    # It requested test agent even if that was not default agent.
    assert mock_prepare.mock_calls[0][1][1] == "test-agent"

    response = intent.IntentResponse("en")
    response.async_set_speech("Timer set for 20 minutes")

    with patch(
        "homeassistant.components.assist_pipeline.pipeline.conversation.async_converse",
        return_value=conversation.ConversationResult(
            response=response,
            conversation_id=mock_chat_session.conversation_id,
        ),
    ) as mock_async_converse:
        await pipeline_input.execute()

        mock_async_converse.assert_called()

    # Snapshot will show it was still handled by the test agent and not default agent
    results = [
        event.data
        for event in events
        if event.type
        in (
            assist_pipeline.PipelineEventType.INTENT_START,
            assist_pipeline.PipelineEventType.INTENT_END,
        )
    ]
    assert results[0]["engine"] == "test-agent"
    assert results[1]["intent_output"]["continue_conversation"] is False


async def test_stt_language_used_instead_of_conversation_language(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    init_components,
    mock_chat_session: chat_session.ChatSession,
    snapshot: SnapshotAssertion,
) -> None:
    """Test that the STT language is used first when the conversation language is '*' (all languages)."""
    client = await hass_ws_client(hass)

    events: list[assist_pipeline.PipelineEvent] = []

    await client.send_json_auto_id(
        {
            "type": "assist_pipeline/pipeline/create",
            "conversation_engine": "homeassistant",
            "conversation_language": MATCH_ALL,
            "language": "en",
            "name": "test_name",
            "stt_engine": "test",
            "stt_language": "en-US",
            "tts_engine": "test",
            "tts_language": "en-US",
            "tts_voice": "Arnold Schwarzenegger",
            "wake_word_entity": None,
            "wake_word_id": None,
        }
    )
    msg = await client.receive_json()
    assert msg["success"]
    pipeline_id = msg["result"]["id"]
    pipeline = assist_pipeline.async_get_pipeline(hass, pipeline_id)

    pipeline_input = assist_pipeline.pipeline.PipelineInput(
        intent_input="test input",
        session=mock_chat_session,
        run=assist_pipeline.pipeline.PipelineRun(
            hass,
            context=Context(),
            pipeline=pipeline,
            start_stage=assist_pipeline.PipelineStage.INTENT,
            end_stage=assist_pipeline.PipelineStage.INTENT,
            event_callback=events.append,
        ),
    )
    await pipeline_input.validate()

    with patch(
        "homeassistant.components.assist_pipeline.pipeline.conversation.async_converse",
        return_value=conversation.ConversationResult(
            intent.IntentResponse(pipeline.language)
        ),
    ) as mock_async_converse:
        await pipeline_input.execute()

        # Check intent start event
        assert process_events(events) == snapshot
        intent_start: assist_pipeline.PipelineEvent | None = None
        for event in events:
            if event.type == assist_pipeline.PipelineEventType.INTENT_START:
                intent_start = event
                break

        assert intent_start is not None

        # STT language (en-US) should be used instead of '*'
        assert intent_start.data.get("language") == pipeline.stt_language

        # Check input to async_converse
        mock_async_converse.assert_called_once()
        assert (
            mock_async_converse.call_args_list[0].kwargs.get("language")
            == pipeline.stt_language
        )


async def test_tts_language_used_instead_of_conversation_language(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    init_components,
    mock_chat_session: chat_session.ChatSession,
    snapshot: SnapshotAssertion,
) -> None:
    """Test that the TTS language is used after STT when the conversation language is '*' (all languages)."""
    client = await hass_ws_client(hass)

    events: list[assist_pipeline.PipelineEvent] = []

    await client.send_json_auto_id(
        {
            "type": "assist_pipeline/pipeline/create",
            "conversation_engine": "homeassistant",
            "conversation_language": MATCH_ALL,
            "language": "en",
            "name": "test_name",
            "stt_engine": None,
            "stt_language": None,
            "tts_engine": None,
            "tts_language": "en-us",
            "tts_voice": "Arnold Schwarzenegger",
            "wake_word_entity": None,
            "wake_word_id": None,
        }
    )
    msg = await client.receive_json()
    assert msg["success"]
    pipeline_id = msg["result"]["id"]
    pipeline = assist_pipeline.async_get_pipeline(hass, pipeline_id)

    pipeline_input = assist_pipeline.pipeline.PipelineInput(
        intent_input="test input",
        session=mock_chat_session,
        run=assist_pipeline.pipeline.PipelineRun(
            hass,
            context=Context(),
            pipeline=pipeline,
            start_stage=assist_pipeline.PipelineStage.INTENT,
            end_stage=assist_pipeline.PipelineStage.INTENT,
            event_callback=events.append,
        ),
    )
    await pipeline_input.validate()

    with patch(
        "homeassistant.components.assist_pipeline.pipeline.conversation.async_converse",
        return_value=conversation.ConversationResult(
            intent.IntentResponse(pipeline.language)
        ),
    ) as mock_async_converse:
        await pipeline_input.execute()

        # Check intent start event
        assert process_events(events) == snapshot
        intent_start: assist_pipeline.PipelineEvent | None = None
        for event in events:
            if event.type == assist_pipeline.PipelineEventType.INTENT_START:
                intent_start = event
                break

        assert intent_start is not None

        # STT language (en-US) should be used instead of '*'
        assert intent_start.data.get("language") == pipeline.tts_language

        # Check input to async_converse
        mock_async_converse.assert_called_once()
        assert (
            mock_async_converse.call_args_list[0].kwargs.get("language")
            == pipeline.tts_language
        )


async def test_pipeline_language_used_instead_of_conversation_language(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    init_components,
    mock_chat_session: chat_session.ChatSession,
    snapshot: SnapshotAssertion,
) -> None:
    """Test that the pipeline language is used last when the conversation language is '*' (all languages)."""
    client = await hass_ws_client(hass)

    events: list[assist_pipeline.PipelineEvent] = []

    await client.send_json_auto_id(
        {
            "type": "assist_pipeline/pipeline/create",
            "conversation_engine": "homeassistant",
            "conversation_language": MATCH_ALL,
            "language": "en",
            "name": "test_name",
            "stt_engine": None,
            "stt_language": None,
            "tts_engine": None,
            "tts_language": None,
            "tts_voice": None,
            "wake_word_entity": None,
            "wake_word_id": None,
        }
    )
    msg = await client.receive_json()
    assert msg["success"]
    pipeline_id = msg["result"]["id"]
    pipeline = assist_pipeline.async_get_pipeline(hass, pipeline_id)

    pipeline_input = assist_pipeline.pipeline.PipelineInput(
        intent_input="test input",
        session=mock_chat_session,
        run=assist_pipeline.pipeline.PipelineRun(
            hass,
            context=Context(),
            pipeline=pipeline,
            start_stage=assist_pipeline.PipelineStage.INTENT,
            end_stage=assist_pipeline.PipelineStage.INTENT,
            event_callback=events.append,
        ),
    )
    await pipeline_input.validate()

    with patch(
        "homeassistant.components.assist_pipeline.pipeline.conversation.async_converse",
        return_value=conversation.ConversationResult(
            intent.IntentResponse(pipeline.language)
        ),
    ) as mock_async_converse:
        await pipeline_input.execute()

        # Check intent start event
        assert process_events(events) == snapshot
        intent_start: assist_pipeline.PipelineEvent | None = None
        for event in events:
            if event.type == assist_pipeline.PipelineEventType.INTENT_START:
                intent_start = event
                break

        assert intent_start is not None

        # STT language (en-US) should be used instead of '*'
        assert intent_start.data.get("language") == pipeline.language

        # Check input to async_converse
        mock_async_converse.assert_called_once()
        assert (
            mock_async_converse.call_args_list[0].kwargs.get("language")
            == pipeline.language
        )
