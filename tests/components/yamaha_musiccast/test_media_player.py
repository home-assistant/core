"""Tests for the yamaha_musiccast media player."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.media_player import DOMAIN as MP_DOMAIN
from homeassistant.components.yamaha_musiccast.const import (
    CONF_SERIAL,
    CONF_UPNP_DESC,
    DEFAULT_ZONE,
    DOMAIN,
)
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

ENTITY_ID = "media_player.test_musiccast"


@pytest.fixture
def mock_device():
    """Return a mock MusicCastDevice with minimal data populated."""
    from aiomusiccast.musiccast_data import MusicCastData, MusicCastZoneData

    zone = MusicCastZoneData()
    zone.name = "Main Zone"
    zone.sound_program = "movie"

    data = MusicCastData()
    data.device_id = "test_device_id"
    data.model_name = "RX-A4A"
    data.system_version = "2.00"
    data.network_name = "Test MusicCast"
    data.mac_addresses = {"wlan": "00:11:22:33:44:55"}
    data.zones = {DEFAULT_ZONE: zone}
    data.sound_program_names = {
        "movie": "Movie",
        "music": "Music",
        "sports": "Sports",
    }

    device = MagicMock()
    device.data = data
    device.fetch = AsyncMock()
    device.build_capabilities = MagicMock()
    device.register_callback = MagicMock()
    device.remove_callback = MagicMock()
    device.register_group_update_callback = MagicMock()
    device.remove_group_update_callback = MagicMock()
    device.select_sound_mode = AsyncMock()
    device.ip = "192.168.1.100"
    device.media_image_url = None
    device.device = MagicMock()
    device.device.enable_polling = AsyncMock()
    device.device.disable_polling = MagicMock()

    return device


@pytest.fixture
async def setup_integration(
    hass: HomeAssistant, mock_device: MagicMock
) -> MockConfigEntry:
    """Set up the yamaha_musiccast integration with a mocked device."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.100",
            CONF_SERIAL: "1234567890",
            CONF_UPNP_DESC: "http://192.168.1.100:49154/MediaRenderer/desc.xml",
        },
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.yamaha_musiccast.MusicCastDevice",
        return_value=mock_device,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry


def _get_entity(hass: HomeAssistant, entry: MockConfigEntry):
    """Return the media player entity from the coordinator."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    return next(e for e in coordinator.entities if e.entity_id == ENTITY_ID)


async def test_sound_mode(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    """Test that sound_mode resolves the program ID to a human-readable name."""
    entity = _get_entity(hass, setup_integration)
    assert entity.sound_mode == "Movie"


async def test_sound_mode_list(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    """Test that sound_mode_list returns all available sound program names."""
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    sound_mode_list = state.attributes["sound_mode_list"]
    assert "Movie" in sound_mode_list
    assert "Music" in sound_mode_list
    assert "Sports" in sound_mode_list


async def test_async_select_sound_mode(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_device: MagicMock,
) -> None:
    """Test that selecting a sound mode by name resolves to the correct program ID."""
    await hass.services.async_call(
        MP_DOMAIN,
        "select_sound_mode",
        {"entity_id": ENTITY_ID, "sound_mode": "Music"},
        blocking=True,
    )
    mock_device.select_sound_mode.assert_called_once_with(DEFAULT_ZONE, "music")


async def test_async_select_sound_mode_unknown(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_device: MagicMock,
) -> None:
    """Test that selecting an unknown sound mode passes None as program ID."""
    await hass.services.async_call(
        MP_DOMAIN,
        "select_sound_mode",
        {"entity_id": ENTITY_ID, "sound_mode": "Unknown Mode"},
        blocking=True,
    )
    mock_device.select_sound_mode.assert_called_once_with(DEFAULT_ZONE, None)
