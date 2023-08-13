"""Test wake_word component setup."""
from collections.abc import AsyncIterable, Generator
from pathlib import Path

import pytest

from homeassistant.components import wake_word
from homeassistant.config_entries import ConfigEntry, ConfigEntryState, ConfigFlow
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

TEST_DOMAIN = "test"

_SAMPLES_PER_CHUNK = 1024
_BYTES_PER_CHUNK = _SAMPLES_PER_CHUNK * 2  # 16-bit
_MS_PER_CHUNK = (_BYTES_PER_CHUNK // 2) // 16  # 16Khz


class MockProviderEntity(wake_word.WakeWordDetectionEntity):
    """Mock provider entity."""

    url_path = "wake_word.test"
    _attr_name = "test"

    @property
    def supported_wake_words(self) -> list[wake_word.WakeWord]:
        """Return a list of supported wake words."""
        return [wake_word.WakeWord(ww_id="test_ww", name="Test Wake Word")]

    async def _async_process_audio_stream(
        self, stream: AsyncIterable[tuple[bytes, int]]
    ) -> wake_word.DetectionResult | None:
        """Try to detect wake word(s) in an audio stream with timestamps."""
        async for _chunk, timestamp in stream:
            if timestamp >= 2000:
                return wake_word.DetectionResult(
                    ww_id=self.supported_wake_words[0].ww_id, timestamp=timestamp
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
    assert config_entry.state == ConfigEntryState.LOADED
    await hass.config_entries.async_unload(config_entry.entry_id)
    assert config_entry.state == ConfigEntryState.NOT_LOADED


async def test_detected_entity(
    hass: HomeAssistant, tmp_path: Path, setup: MockProviderEntity
) -> None:
    """Test successful detection through entity."""

    async def three_second_stream():
        timestamp = 0
        while timestamp < 3000:
            yield bytes(_BYTES_PER_CHUNK), timestamp
            timestamp += _MS_PER_CHUNK

    # Need 2 seconds to trigger
    result = await setup.async_process_audio_stream(three_second_stream())
    assert result == wake_word.DetectionResult("test_ww", 2048)


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
    result = await setup.async_process_audio_stream(one_second_stream())
    assert result is None


async def test_default_engine_none(hass: HomeAssistant, tmp_path: Path) -> None:
    """Test async_default_engine."""
    assert await async_setup_component(hass, wake_word.DOMAIN, {wake_word.DOMAIN: {}})
    await hass.async_block_till_done()

    assert wake_word.async_default_engine(hass) is None


async def test_default_engine_entity(
    hass: HomeAssistant, tmp_path: Path, mock_provider_entity: MockProviderEntity
) -> None:
    """Test async_default_engine."""
    await mock_config_entry_setup(hass, tmp_path, mock_provider_entity)

    assert wake_word.async_default_engine(hass) == f"{wake_word.DOMAIN}.{TEST_DOMAIN}"


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

    assert config_entry.state == ConfigEntryState.LOADED
    state = hass.states.get(entity_id)
    assert state
    assert state.state == timestamp
