"""Fixtures for the Lyngdorf integration tests."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from lyngdorf.const import LyngdorfModel
import pytest

from homeassistant.components.lyngdorf.const import CONF_SERIAL_NUMBER, DOMAIN
from homeassistant.const import CONF_HOST, CONF_MODEL
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="Mock Lyngdorf",
        domain=DOMAIN,
        data={
            CONF_HOST: "127.0.0.1",
            CONF_MODEL: "MP-60",
            CONF_SERIAL_NUMBER: "123456",
        },
        unique_id="123456",
    )


@pytest.fixture
def mock_setup_entry() -> Generator[None]:
    """Mock setting up a config entry."""
    with (
        patch("homeassistant.components.lyngdorf.async_setup_entry", return_value=True),
        patch(
            "homeassistant.components.lyngdorf.async_unload_entry", return_value=True
        ),
    ):
        yield


@pytest.fixture
def mock_lyngdorf_model() -> LyngdorfModel:
    """Return a mocked Lyngdorf model."""
    return LyngdorfModel.MP_60


@pytest.fixture
def mock_receiver() -> Generator[MagicMock]:
    """Return a mocked Lyngdorf receiver."""
    with patch(
        "homeassistant.components.lyngdorf.async_create_receiver"
    ) as create_mock:
        receiver = MagicMock()
        receiver.async_connect = AsyncMock()
        receiver.async_disconnect = AsyncMock()
        receiver.name = "Mock Lyngdorf"
        receiver.register_notification_callback = MagicMock()
        receiver.un_register_notification_callback = MagicMock()
        receiver.connected = True

        # Main zone properties
        receiver.power_on = False
        receiver.volume = -40.0
        receiver.mute_enabled = False
        receiver.audio_information = None
        receiver.video_information = None
        receiver.source = None
        receiver.available_sources = []
        receiver.sound_mode = None
        receiver.available_sound_modes = []
        receiver.volume_up = MagicMock()
        receiver.volume_down = MagicMock()

        # Zone B properties
        receiver.zone_b_power_on = False
        receiver.zone_b_volume = -40.0
        receiver.zone_b_mute_enabled = False
        receiver.zone_b_source = None
        receiver.zone_b_available_sources = []
        receiver.zone_b_volume_up = MagicMock()
        receiver.zone_b_volume_down = MagicMock()

        create_mock.return_value = receiver
        yield receiver


@pytest.fixture
def mock_find_receiver_model() -> Generator[AsyncMock]:
    """Return a mocked async_find_receiver_model function."""
    with patch(
        "homeassistant.components.lyngdorf.config_flow.async_find_receiver_model"
    ) as find_mock:
        find_mock.return_value = LyngdorfModel.MP_60
        yield find_mock


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_receiver: MagicMock,
) -> MockConfigEntry:
    """Set up the Lyngdorf integration for testing."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.lyngdorf.lookup_receiver_model") as lookup:
        lookup.return_value = LyngdorfModel.MP_60
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    return mock_config_entry
