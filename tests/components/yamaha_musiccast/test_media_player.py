"""Tests for the yamaha_musiccast media player."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from aiomusiccast.musiccast_data import MusicCastData, MusicCastZoneData
import pytest

from homeassistant.components.yamaha_musiccast.const import (
    CONF_SERIAL,
    CONF_UPNP_DESC,
    DEFAULT_ZONE,
    DOMAIN,
)
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def silent_ssdp_scanner() -> Generator[None]:
    """Prevent actual SSDP traffic during tests."""
    with (
        patch("homeassistant.components.ssdp.Scanner._async_start_ssdp_listeners"),
        patch("homeassistant.components.ssdp.Scanner._async_stop_ssdp_listeners"),
        patch("homeassistant.components.ssdp.Scanner.async_scan"),
        patch("homeassistant.components.ssdp.Server._async_start_upnp_servers"),
        patch("homeassistant.components.ssdp.Server._async_stop_upnp_servers"),
    ):
        yield


@pytest.fixture
def mock_device() -> MagicMock:
    """Return a mock MusicCastDevice with minimal data populated."""
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
    data.sound_program_names = {}

    device = MagicMock()
    device.data = data
    device.fetch = AsyncMock()
    device.build_capabilities = MagicMock()
    device.register_callback = MagicMock()
    device.remove_callback = MagicMock()
    device.register_group_update_callback = MagicMock()
    device.remove_group_update_callback = MagicMock()
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


async def test_translation_key(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    """Test that the media player entity uses the zone translation key."""
    entity_registry = er.async_get(hass)
    entries = er.async_entries_for_config_entry(entity_registry, setup_integration.entry_id)
    mp_entries = [e for e in entries if e.domain == "media_player"]
    assert len(mp_entries) > 0
    assert all(e.translation_key == "zone" for e in mp_entries)
