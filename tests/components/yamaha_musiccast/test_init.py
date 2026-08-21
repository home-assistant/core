"""Test the MusicCast integration setup."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from aiomusiccast.capabilities import BinarySetter, EntityType
from aiomusiccast.musiccast_data import MusicCastData, MusicCastZoneData
import pytest

from homeassistant.components.yamaha_musiccast.const import DEFAULT_ZONE, DOMAIN
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry

TEST_DEVICE_ID = "1234567890"
TEST_ZONE = "zone2"


@pytest.fixture(autouse=True)
def silent_ssdp_scanner() -> Generator[None]:
    """Start SSDP component and get Scanner, prevent actual SSDP traffic."""
    with (
        patch("homeassistant.components.ssdp.Scanner._async_start_ssdp_listeners"),
        patch("homeassistant.components.ssdp.Scanner._async_stop_ssdp_listeners"),
        patch("homeassistant.components.ssdp.Scanner.async_scan"),
        patch("homeassistant.components.ssdp.Server._async_start_upnp_servers"),
        patch("homeassistant.components.ssdp.Server._async_stop_upnp_servers"),
    ):
        yield


@pytest.fixture
def mock_musiccast_device() -> Generator[MagicMock]:
    """Mock a MusicCast device with a main zone and a sub-zone."""
    data = MusicCastData()
    data.device_id = TEST_DEVICE_ID
    data.model_name = "MC20"
    data.system_version = "1.0"
    data.mac_addresses = {"main": "001122334455"}
    data.network_name = "MusicCast"

    main_zone = MusicCastZoneData()
    main_zone.name = "Main"
    sub_zone = MusicCastZoneData()
    sub_zone.name = "Zone 2"
    # A capability on the sub-zone makes the switch platform register the
    # sub-zone device, which links back to the main device via via_device_id.
    sub_zone.capabilities = [
        BinarySetter("power", "Power", EntityType.CONFIG, lambda: False, AsyncMock())
    ]
    data.zones = {DEFAULT_ZONE: main_zone, TEST_ZONE: sub_zone}

    device = MagicMock()
    device.data = data
    device.ip = "127.0.0.1"
    device.fetch = AsyncMock()
    device.build_capabilities = MagicMock()
    device.device = MagicMock()
    device.device.enable_polling = AsyncMock()

    with patch(
        "homeassistant.components.yamaha_musiccast.MusicCastDevice",
        return_value=device,
    ):
        yield device


@pytest.mark.usefixtures("mock_musiccast_device")
async def test_device_via_device_links(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test that a zone sub-device links to the main device via via_device_id.

    Only the switch platform is loaded so the main device is registered solely
    by the integration setup, exercising the via_device pre-registration.
    """
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_DEVICE_ID,
        data={
            CONF_HOST: "127.0.0.1",
            "serial": TEST_DEVICE_ID,
            "upnp_description": "http://127.0.0.1:49154/MediaRenderer/desc.xml",
        },
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.yamaha_musiccast.PLATFORMS", [Platform.SWITCH]
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    main_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, TEST_DEVICE_ID), config_entry.entry_id
    )
    assert main_device is not None

    zone_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{TEST_DEVICE_ID}_{TEST_ZONE}"), config_entry.entry_id
    )
    assert zone_device is not None
    assert zone_device.via_device_id == main_device.id
