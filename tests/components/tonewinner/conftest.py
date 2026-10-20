"""Common fixtures for the Tonewinner tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest

from homeassistant.components.tonewinner.const import CONF_SERIAL_PORT, DOMAIN
from homeassistant.const import CONF_MODEL

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_SERIAL_PORT: "/dev/ttyUSB0",
            CONF_MODEL: "AT-500",
        },
        entry_id="test_entry_id",
        title="AT-500",
    )


@pytest.fixture
def mock_receiver() -> MagicMock:
    """Return a mock TonewinnerReceiver."""
    receiver = MagicMock()
    receiver.connected = True
    receiver.state.power = False
    receiver.state.volume = 50.0
    receiver.state.mute = False
    receiver.state.source_name = None
    receiver.state.audio_source = None
    receiver.state.sound_mode_label = None
    type(receiver).state = PropertyMock(return_value=receiver.state)
    receiver.connect = AsyncMock()
    receiver.disconnect = AsyncMock()
    receiver.query_state = AsyncMock()
    receiver.query_source = AsyncMock()
    receiver.query_info = AsyncMock(return_value=None)
    receiver.power_on = AsyncMock()
    receiver.power_off = AsyncMock()
    receiver.set_volume = AsyncMock()
    receiver.volume_up = AsyncMock()
    receiver.volume_down = AsyncMock()
    receiver.mute_on = AsyncMock()
    receiver.mute_off = AsyncMock()
    receiver.select_source = AsyncMock()
    receiver.select_sound_mode = AsyncMock()
    receiver.subscribe = MagicMock(return_value=lambda: None)
    return receiver


@pytest.fixture
def platforms() -> list[str]:
    """Fixture to specify platforms to test."""
    return ["media_player"]


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.tonewinner.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry
