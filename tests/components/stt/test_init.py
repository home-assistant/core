"""Test STT component setup."""
from collections.abc import AsyncIterable, Generator
from http import HTTPStatus
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from homeassistant.components.stt import (
    DOMAIN,
    AudioBitRates,
    AudioChannels,
    AudioCodecs,
    AudioFormats,
    AudioSampleRates,
    Provider,
    SpeechMetadata,
    SpeechResult,
    SpeechResultState,
    SpeechToTextEntity,
    async_default_engine,
    async_get_provider,
    async_get_speech_to_text_engine,
)
from homeassistant.config_entries import ConfigEntry, ConfigEntryState, ConfigFlow
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.setup import async_setup_component

from .common import mock_stt_entity_platform, mock_stt_platform

from tests.common import (
    MockConfigEntry,
    MockModule,
    mock_config_flow,
    mock_integration,
    mock_platform,
    mock_restore_cache,
)
from tests.typing import ClientSessionGenerator, WebSocketGenerator

TEST_DOMAIN = "test"


class BaseProvider:
    """Mock provider."""

    fail_process_audio = False

    def __init__(self) -> None:
        """Init test provider."""
        self.calls: list[tuple[SpeechMetadata, AsyncIterable[bytes]]] = []

    @property
    def supported_languages(self) -> list[str]:
        """Return a list of supported languages."""
        return ["de", "de-CH", "en"]

    @property
    def supported_formats(self) -> list[AudioFormats]:
        """Return a list of supported formats."""
        return [AudioFormats.WAV, AudioFormats.OGG]

    @property
    def supported_codecs(self) -> list[AudioCodecs]:
        """Return a list of supported codecs."""
        return [AudioCodecs.PCM, AudioCodecs.OPUS]

    @property
    def supported_bit_rates(self) -> list[AudioBitRates]:
        """Return a list of supported bitrates."""
        return [AudioBitRates.BITRATE_16]

    @property
    def supported_sample_rates(self) -> list[AudioSampleRates]:
        """Return a list of supported samplerates."""
        return [AudioSampleRates.SAMPLERATE_16000]

    @property
    def supported_channels(self) -> list[AudioChannels]:
        """Return a list of supported channels."""
        return [AudioChannels.CHANNEL_MONO]

    async def async_process_audio_stream(
        self, metadata: SpeechMetadata, stream: AsyncIterable[bytes]
    ) -> SpeechResult:
        """Process an audio stream."""
        self.calls.append((metadata, stream))
        if self.fail_process_audio:
            return SpeechResult(None, SpeechResultState.ERROR)

        return SpeechResult("test_result", SpeechResultState.SUCCESS)


class MockProvider(BaseProvider, Provider):
    """Mock provider."""

    url_path = TEST_DOMAIN


class MockProviderEntity(BaseProvider, SpeechToTextEntity):
    """Mock provider entity."""

    url_path = "stt.test"
    _attr_name = "test"


@pytest.fixture
def mock_provider() -> MockProvider:
    """Test provider fixture."""
    return MockProvider()


@pytest.fixture
def mock_provider_entity() -> MockProviderEntity:
    """Test provider entity fixture."""
    return MockProviderEntity()


class STTFlow(ConfigFlow):
    """Test flow."""


@pytest.fixture(name="config_flow_test_domain")
def config_flow_test_domain_fixture() -> str:
    """Test domain fixture."""
    return TEST_DOMAIN


@pytest.fixture(autouse=True)
def config_flow_fixture(
    hass: HomeAssistant, config_flow_test_domain: str
) -> Generator[None, None, None]:
    """Mock config flow."""
    mock_platform(hass, f"{config_flow_test_domain}.config_flow")

    with mock_config_flow(config_flow_test_domain, STTFlow):
        yield


@pytest.fixture(name="setup")
async def setup_fixture(
    hass: HomeAssistant,
    tmp_path: Path,
    request: pytest.FixtureRequest,
) -> MockProvider | MockProviderEntity:
    """Set up the test environment."""
    provider: MockProvider | MockProviderEntity
    if request.param == "mock_setup":
        provider = MockProvider()
        await mock_setup(hass, tmp_path, provider)
    elif request.param == "mock_config_entry_setup":
        provider = MockProviderEntity()
        await mock_config_entry_setup(hass, tmp_path, provider)
    else:
        raise RuntimeError("Invalid setup fixture")

    return provider


async def mock_setup(
    hass: HomeAssistant,
    tmp_path: Path,
    mock_provider: MockProvider,
) -> None:
    """Set up a test provider."""
    mock_stt_platform(
        hass,
        tmp_path,
        TEST_DOMAIN,
        async_get_engine=AsyncMock(return_value=mock_provider),
    )
    assert await async_setup_component(hass, "stt", {"stt": {"platform": TEST_DOMAIN}})
    await hass.async_block_till_done()


async def mock_config_entry_setup(
    hass: HomeAssistant,
    tmp_path: Path,
    mock_provider_entity: MockProviderEntity,
    test_domain: str = TEST_DOMAIN,
) -> MockConfigEntry:
    """Set up a test provider via config entry."""

    async def async_setup_entry_init(
        hass: HomeAssistant, config_entry: ConfigEntry
    ) -> bool:
        """Set up test config entry."""
        await hass.config_entries.async_forward_entry_setup(config_entry, DOMAIN)
        return True

    async def async_unload_entry_init(
        hass: HomeAssistant, config_entry: ConfigEntry
    ) -> bool:
        """Unload up test config entry."""
        await hass.config_entries.async_forward_entry_unload(config_entry, DOMAIN)
        return True

    mock_integration(
        hass,
        MockModule(
            test_domain,
            async_setup_entry=async_setup_entry_init,
            async_unload_entry=async_unload_entry_init,
        ),
    )

    async def async_setup_entry_platform(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
    ) -> None:
        """Set up test stt platform via config entry."""
        async_add_entities([mock_provider_entity])

    mock_stt_entity_platform(hass, tmp_path, test_domain, async_setup_entry_platform)

    config_entry = MockConfigEntry(domain=test_domain)
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    return config_entry


@pytest.mark.parametrize(
    "setup", ["mock_setup", "mock_config_entry_setup"], indirect=True
)
async def test_get_provider_info(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    setup: MockProvider | MockProviderEntity,
) -> None:
    """Test engine that doesn't exist."""
    client = await hass_client()
    response = await client.get(f"/api/stt/{setup.url_path}")
    assert response.status == HTTPStatus.OK
    assert await response.json() == {
        "languages": ["de", "de-CH", "en"],
        "formats": ["wav", "ogg"],
        "codecs": ["pcm", "opus"],
        "sample_rates": [16000],
        "bit_rates": [16],
        "channels": [1],
    }


@pytest.mark.parametrize(
    "setup", ["mock_setup", "mock_config_entry_setup"], indirect=True
)
async def test_non_existing_provider(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    setup: MockProvider | MockProviderEntity,
) -> None:
    """Test streaming to engine that doesn't exist."""
    client = await hass_client()

    response = await client.get("/api/stt/not_exist")
    assert response.status == HTTPStatus.NOT_FOUND

    response = await client.post(
        "/api/stt/not_exist",
        headers={
            "X-Speech-Content": (
                "format=wav; codec=pcm; sample_rate=16000; bit_rate=16; channel=1;"
                " language=en"
            )
        },
    )
    assert response.status == HTTPStatus.NOT_FOUND


@pytest.mark.parametrize(
    "setup", ["mock_setup", "mock_config_entry_setup"], indirect=True
)
async def test_stream_audio(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    setup: MockProvider | MockProviderEntity,
) -> None:
    """Test streaming audio and getting response."""
    client = await hass_client()
    response = await client.post(
        f"/api/stt/{setup.url_path}",
        headers={
            "X-Speech-Content": (
                "format=wav; codec=pcm; sample_rate=16000; bit_rate=16; channel=1;"
                " language=en"
            )
        },
    )
    assert response.status == HTTPStatus.OK
    assert await response.json() == {"text": "test_result", "result": "success"}


@pytest.mark.parametrize(
    "setup", ["mock_setup", "mock_config_entry_setup"], indirect=True
)
@pytest.mark.parametrize(
    ("header", "status", "error"),
    (
        (None, 400, "Missing X-Speech-Content header"),
        (
            (
                "format=wav; codec=pcm; sample_rate=16000; bit_rate=16; channel=100;"
                " language=en; unknown=1"
            ),
            400,
            "Invalid field: unknown",
        ),
        (
            (
                "format=wav; codec=pcm; sample_rate=16000; bit_rate=16; channel=100;"
                " language=en"
            ),
            400,
            "Wrong format of X-Speech-Content: 100 is not a valid AudioChannels",
        ),
        (
            (
                "format=wav; codec=pcm; sample_rate=16000; bit_rate=16; channel=bad channel;"
                " language=en"
            ),
            400,
            "Wrong format of X-Speech-Content: invalid literal for int() with base 10: 'bad channel'",
        ),
        (
            "format=wav; codec=pcm; sample_rate=16000",
            400,
            "Missing language in X-Speech-Content header",
        ),
    ),
)
async def test_metadata_errors(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    header: str | None,
    status: int,
    error: str,
    setup: MockProvider | MockProviderEntity,
) -> None:
    """Test metadata errors."""
    client = await hass_client()
    headers: dict[str, str] = {}
    if header:
        headers["X-Speech-Content"] = header

    response = await client.post(f"/api/stt/{setup.url_path}", headers=headers)
    assert response.status == status
    assert await response.text() == error


async def test_get_provider(
    hass: HomeAssistant,
    tmp_path: Path,
    mock_provider: MockProvider,
) -> None:
    """Test we can get STT providers."""
    await mock_setup(hass, tmp_path, mock_provider)
    assert mock_provider == async_get_provider(hass, TEST_DOMAIN)

    # Test getting the default provider
    assert mock_provider == async_get_provider(hass)


async def test_config_entry_unload(
    hass: HomeAssistant, tmp_path: Path, mock_provider_entity: MockProviderEntity
) -> None:
    """Test we can unload config entry."""
    config_entry = await mock_config_entry_setup(hass, tmp_path, mock_provider_entity)
    assert config_entry.state == ConfigEntryState.LOADED
    await hass.config_entries.async_unload(config_entry.entry_id)
    assert config_entry.state == ConfigEntryState.NOT_LOADED


async def test_restore_state(
    hass: HomeAssistant,
    tmp_path: Path,
    mock_provider_entity: MockProviderEntity,
) -> None:
    """Test we restore state in the integration."""
    entity_id = f"{DOMAIN}.{TEST_DOMAIN}"
    timestamp = "2023-01-01T23:59:59+00:00"
    mock_restore_cache(hass, (State(entity_id, timestamp),))

    config_entry = await mock_config_entry_setup(hass, tmp_path, mock_provider_entity)
    await hass.async_block_till_done()

    assert config_entry.state == ConfigEntryState.LOADED
    state = hass.states.get(entity_id)
    assert state
    assert state.state == timestamp


@pytest.mark.parametrize(
    ("setup", "engine_id"),
    [("mock_setup", "test"), ("mock_config_entry_setup", "stt.test")],
    indirect=["setup"],
)
async def test_ws_list_engines(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    setup: MockProvider | MockProviderEntity,
    engine_id: str,
) -> None:
    """Test listing speech-to-text engines."""
    client = await hass_ws_client()

    await client.send_json_auto_id({"type": "stt/engine/list"})

    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] == {
        "providers": [
            {"engine_id": engine_id, "supported_languages": ["de", "de-CH", "en"]}
        ]
    }

    await client.send_json_auto_id({"type": "stt/engine/list", "language": "smurfish"})

    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] == {
        "providers": [{"engine_id": engine_id, "supported_languages": []}]
    }

    await client.send_json_auto_id({"type": "stt/engine/list", "language": "en"})

    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] == {
        "providers": [{"engine_id": engine_id, "supported_languages": ["en"]}]
    }

    await client.send_json_auto_id({"type": "stt/engine/list", "language": "en-UK"})

    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] == {
        "providers": [{"engine_id": engine_id, "supported_languages": ["en"]}]
    }

    await client.send_json_auto_id({"type": "stt/engine/list", "language": "de"})
    msg = await client.receive_json()
    assert msg["type"] == "result"
    assert msg["success"]
    assert msg["result"] == {
        "providers": [{"engine_id": engine_id, "supported_languages": ["de", "de-CH"]}]
    }

    await client.send_json_auto_id(
        {"type": "stt/engine/list", "language": "de", "country": "ch"}
    )
    msg = await client.receive_json()
    assert msg["type"] == "result"
    assert msg["success"]
    assert msg["result"] == {
        "providers": [{"engine_id": engine_id, "supported_languages": ["de-CH", "de"]}]
    }


async def test_default_engine_none(hass: HomeAssistant, tmp_path: Path) -> None:
    """Test async_default_engine."""
    assert await async_setup_component(hass, "stt", {"stt": {}})
    await hass.async_block_till_done()

    assert async_default_engine(hass) is None


async def test_default_engine(
    hass: HomeAssistant,
    tmp_path: Path,
    mock_provider: MockProvider,
) -> None:
    """Test async_default_engine."""
    mock_stt_platform(
        hass,
        tmp_path,
        TEST_DOMAIN,
        async_get_engine=AsyncMock(return_value=mock_provider),
    )
    assert await async_setup_component(hass, "stt", {"stt": {"platform": TEST_DOMAIN}})
    await hass.async_block_till_done()

    assert async_default_engine(hass) == TEST_DOMAIN


async def test_default_engine_entity(
    hass: HomeAssistant, tmp_path: Path, mock_provider_entity: MockProviderEntity
) -> None:
    """Test async_default_engine."""
    await mock_config_entry_setup(hass, tmp_path, mock_provider_entity)

    assert async_default_engine(hass) == f"{DOMAIN}.{TEST_DOMAIN}"


@pytest.mark.parametrize("config_flow_test_domain", ["new_test"])
async def test_default_engine_prefer_provider(
    hass: HomeAssistant,
    tmp_path: Path,
    mock_provider_entity: MockProviderEntity,
    mock_provider: MockProvider,
    config_flow_test_domain: str,
) -> None:
    """Test async_default_engine."""
    mock_provider_entity.url_path = "stt.new_test"
    mock_provider_entity._attr_name = "New test"

    await mock_setup(hass, tmp_path, mock_provider)
    await mock_config_entry_setup(
        hass, tmp_path, mock_provider_entity, test_domain=config_flow_test_domain
    )
    await hass.async_block_till_done()

    entity_engine = async_get_speech_to_text_engine(hass, "stt.new_test")
    assert entity_engine is not None
    assert entity_engine.name == "New test"
    provider_engine = async_get_speech_to_text_engine(hass, "test")
    assert provider_engine is not None
    assert provider_engine.name == "test"
    assert async_default_engine(hass) == "test"


async def test_get_engine_legacy(
    hass: HomeAssistant, tmp_path: Path, mock_provider: MockProvider
) -> None:
    """Test async_get_speech_to_text_engine."""
    mock_stt_platform(
        hass,
        tmp_path,
        TEST_DOMAIN,
        async_get_engine=AsyncMock(return_value=mock_provider),
    )
    mock_stt_platform(
        hass,
        tmp_path,
        "cloud",
        async_get_engine=AsyncMock(return_value=mock_provider),
    )
    assert await async_setup_component(
        hass, "stt", {"stt": [{"platform": TEST_DOMAIN}, {"platform": "cloud"}]}
    )
    await hass.async_block_till_done()

    assert async_get_speech_to_text_engine(hass, "no_such_provider") is None
    assert async_get_speech_to_text_engine(hass, "test") is mock_provider


async def test_get_engine_entity(
    hass: HomeAssistant, tmp_path: Path, mock_provider_entity: MockProviderEntity
) -> None:
    """Test async_get_speech_to_text_engine."""
    await mock_config_entry_setup(hass, tmp_path, mock_provider_entity)

    assert async_get_speech_to_text_engine(hass, "stt.test") is mock_provider_entity
