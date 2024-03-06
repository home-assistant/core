"""Conftest for TTS tests."""
import pytest

from homeassistant.core import HomeAssistant

from .common import MockMediaPlayer, mock_setup


@pytest.fixture
def mock_media_player() -> MockMediaPlayer:
    """Test TTS entity."""
    return MockMediaPlayer("test", "very_unique")


@pytest.fixture(name="setup")
async def setup_fixture(
    hass: HomeAssistant,
    mock_media_player: MockMediaPlayer,
) -> None:
    """Set up the test environment."""
    await mock_setup(hass, mock_media_player)
