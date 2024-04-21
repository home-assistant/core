"""Test wake_word component setup."""

import asyncio
from collections.abc import AsyncIterable, Generator
from functools import partial
from pathlib import Path
from unittest.mock import patch

from freezegun import freeze_time
import pytest

from homeassistant.components import wake_word
from homeassistant.config_entries import ConfigEntry, ConfigEntryState, ConfigFlow
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.setup import async_setup_component

from .common import mock_wake_word_entity_platform

from tests.common import (
    MockConfigEntry,
    MockModule,
    mock_config_flow,
    mock_integration,
    mock_platform,
    mock_restore_cache,
)
from tests.typing import WebSocketGenerator

TEST_DOMAIN = "test"

_SAMPLES_PER_CHUNK = 1024
_BYTES_PER_CHUNK = _SAMPLES_PER_CHUNK * 2  # 16-bit
_MS_PER_CHUNK = (_BYTES_PER_CHUNK // 2) // 16  # 16Khz


class MockProviderEntity(wake_word.WakeWordDetectionEntity):
    """Mock provider entity."""

    url_path = "wake_word.test"
    _attr_name = "test"

    async def get_supported_wake_words(self) -> list[wake_word.WakeWord]:
        """Return a list of supported wake words."""
        return [
            wake_word.WakeWord(
                id="test_ww", name="Test Wake Word", phrase="Test Phrase"
            ),
            wake_word.WakeWord(
                id="test_ww_2", name="Test Wake Word 2", phrase="Test Phrase 2"
            ),
        ]

    async def _async_process_audio_stream(
        self, stream: AsyncIterable[tuple[bytes, int]], wake_word_id: str | None
    ) -> wake_word.DetectionResult | None:
        """Try to detect wake word(s) in an audio stream with timestamps."""
        if wake_word_id is None:
            wake_word_id = (await self.get_supported_wake_words())[0].id

        wake_word_phrase = wake_word_id
        for ww in await self.get_supported_wake_words():
            if ww.id == wake_word_id:
                wake_word_phrase = ww.phrase or ww.name
                break

        async for _chunk, timestamp in stream:
            if timestamp >= 2000:
                return wake_word.DetectionResult(
                    wake_word_id=wake_word_id,
                    wake_word_phrase=wake_word_phrase,
                    timestamp=timestamp,
                )

        # Not detected
        return None


@pytest.fixture
def mock_provider_entity() -> MockProviderEntity:
    """Test provider entity fixture."""
    return MockProviderEntity()


class WakeWordFlow(ConfigFlow):
    """Test flow."""


@pytest.fixture(autouse=True)
def config_flow_fixture(hass: HomeAssistant) -> Generator[None, None, None]:
    """Mock config flow."""
    mock_platform(hass, f"{TEST_DOMAIN}.config_flow")

    with mock_config_flow(TEST_DOMAIN, WakeWordFlow):
        yield


@pytest.fixture(name="setup")
async def setup_fixture(
    hass: HomeAssistant,
    tmp_path: Path,
) -> MockProviderEntity:
    """Set up the test environment."""
    provider = MockProviderEntity()
    await mock_config_entry_setup(hass, tmp_path, provider)

    return provider


async def mock_config_entry_setup(
    hass: HomeAssistant, tmp_path: Path, mock_provider_entity: MockProviderEntity
) -> MockConfigEntry:
    """Set up a test provider via config entry."""

    async def async_setup_entry_init(
        hass: HomeAssistant, config_entry: ConfigEntry
    ) -> bool:
        """Set up test config entry."""
        await hass.config_entries.async_forward_entry_setup(
            config_entry, wake_word.DOMAIN
        )
        return True

    async def async_unload_entry_init(
        hass: HomeAssistant, config_entry: ConfigEntry
    ) -> bool:
        """Unload up test config entry."""
        await hass.config_entries.async_forward_entry_unload(
            config_entry, wake_word.DOMAIN
        )
        return True

    mock_integration(
        hass,
        MockModule(
            TEST_DOMAIN,
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

    mock_wake_word_entity_platform(
        hass, tmp_path, TEST_DOMAIN, async_setup_entry_platform
    )

    config_entry = MockConfigEntry(domain=TEST_DOMAIN)
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    return config_entry


async def test_config_entry_unload(
    hass: HomeAssistant, tmp_path: Path, mock_provider_entity: MockProviderEntity
) -> None:
    """Test we can unload config entry."""
    config_entry = await mock_config_entry_setup(hass, tmp_path, mock_provider_entity)
    assert config_entry.state is ConfigEntryState.LOADED
    await hass.config_entries.async_unload(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.NOT_LOADED


@freeze_time("2023-06-22 10:30:00+00:00")
@pytest.mark.parametrize(
    ("wake_word_id", "expected_ww", "expected_phrase"),
    [
        (None, "test_ww", "Test Phrase"),
        ("test_ww_2", "test_ww_2", "Test Phrase 2"),
    ],
)
async def test_detected_entity(
    hass: HomeAssistant,
    tmp_path: Path,
    setup: MockProviderEntity,
    wake_word_id: str | None,
    expected_ww: str,
    expected_phrase: str,
) -> None:
    """Test successful detection through entity."""

    async def three_second_stream():
        timestamp = 0
        while timestamp < 3000:
            yield bytes(_BYTES_PER_CHUNK), timestamp
            timestamp += _MS_PER_CHUNK

    # Need 2 seconds to trigger
    state = setup.state
    assert state is None
    result = await setup.async_process_audio_stream(three_second_stream(), wake_word_id)
    assert result == wake_word.DetectionResult(
        wake_word_id=expected_ww, wake_word_phrase=expected_phrase, timestamp=2048
    )

    assert state != setup.state
    assert setup.state == "2023-06-22T10:30:00+00:00"


async def test_not_detected_entity(
    hass: HomeAssistant, setup: MockProviderEntity
) -> None:
    """Test unsuccessful detection through entity."""

    async def one_second_stream():
        timestamp = 0
        while timestamp < 1000:
            yield bytes(_BYTES_PER_CHUNK), timestamp
            timestamp += _MS_PER_CHUNK

    # Need 2 seconds to trigger
    state = setup.state
    result = await setup.async_process_audio_stream(one_second_stream(), None)
    assert result is None

    # State should only change when there's a detection
    assert state == setup.state


async def test_default_engine_none(hass: HomeAssistant, tmp_path: Path) -> None:
    """Test async_default_entity."""
    assert await async_setup_component(hass, wake_word.DOMAIN, {wake_word.DOMAIN: {}})
    await hass.async_block_till_done()

    assert wake_word.async_default_entity(hass) is None


async def test_default_engine_entity(
    hass: HomeAssistant, tmp_path: Path, mock_provider_entity: MockProviderEntity
) -> None:
    """Test async_default_entity."""
    await mock_config_entry_setup(hass, tmp_path, mock_provider_entity)

    assert wake_word.async_default_entity(hass) == f"{wake_word.DOMAIN}.{TEST_DOMAIN}"


async def test_get_engine_entity(
    hass: HomeAssistant, tmp_path: Path, mock_provider_entity: MockProviderEntity
) -> None:
    """Test async_get_speech_to_text_engine."""
    await mock_config_entry_setup(hass, tmp_path, mock_provider_entity)

    assert (
        wake_word.async_get_wake_word_detection_entity(hass, f"{wake_word.DOMAIN}.test")
        is mock_provider_entity
    )


async def test_restore_state(
    hass: HomeAssistant,
    tmp_path: Path,
    mock_provider_entity: MockProviderEntity,
) -> None:
    """Test we restore state in the integration."""
    entity_id = f"{wake_word.DOMAIN}.{TEST_DOMAIN}"
    timestamp = "2023-01-01T23:59:59+00:00"
    mock_restore_cache(hass, (State(entity_id, timestamp),))

    config_entry = await mock_config_entry_setup(hass, tmp_path, mock_provider_entity)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    state = hass.states.get(entity_id)
    assert state
    assert state.state == timestamp


async def test_entity_attributes(
    hass: HomeAssistant, mock_provider_entity: MockProviderEntity
) -> None:
    """Test that the provider entity attributes match expectations."""
    assert mock_provider_entity.entity_category == EntityCategory.DIAGNOSTIC


async def test_list_wake_words(
    hass: HomeAssistant,
    setup: MockProviderEntity,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test that the list_wake_words websocket command works."""
    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 5,
            "type": "wake_word/info",
            "entity_id": setup.entity_id,
        }
    )

    msg = await client.receive_json()

    assert msg["success"]
    assert msg["result"] == {
        "wake_words": [
            {"id": "test_ww", "name": "Test Wake Word", "phrase": "Test Phrase"},
            {"id": "test_ww_2", "name": "Test Wake Word 2", "phrase": "Test Phrase 2"},
        ]
    }


async def test_list_wake_words_unknown_entity(
    hass: HomeAssistant,
    setup: MockProviderEntity,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test that the list_wake_words websocket command handles unknown entity."""
    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 5,
            "type": "wake_word/info",
            "entity_id": "wake_word.blah",
        }
    )

    msg = await client.receive_json()

    assert not msg["success"]
    assert msg["error"] == {"code": "not_found", "message": "Entity not found"}


async def test_list_wake_words_timeout(
    hass: HomeAssistant,
    setup: MockProviderEntity,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test that the list_wake_words websocket command handles unknown entity."""
    client = await hass_ws_client(hass)

    with (
        patch.object(setup, "get_supported_wake_words", partial(asyncio.sleep, 1)),
        patch("homeassistant.components.wake_word.TIMEOUT_FETCH_WAKE_WORDS", 0),
    ):
        await client.send_json(
            {
                "id": 5,
                "type": "wake_word/info",
                "entity_id": setup.entity_id,
            }
        )

        msg = await client.receive_json()

    assert not msg["success"]
    assert msg["error"] == {"code": "timeout", "message": "Timeout fetching wake words"}
