"""Tests for the DLNA DMS diagnostics."""

from unittest.mock import Mock

from async_upnp_client.exceptions import UpnpConnectionError
import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant


@pytest.fixture
def connected_device(dms_device_mock: Mock) -> Mock:
    """Populate the DMS device mock with realistic values."""
    profile_device = dms_device_mock.profile_device
    profile_device.manufacturer = "device_manufacturer"
    profile_device.model_name = "device_model_name"
    profile_device.model_number = "1.0"
    profile_device.model_description = "Test media server"
    actions = {
        "urn:schemas-upnp-org:service:ContentDirectory:1": [
            "Browse",
            "GetSearchCapabilities",
            "GetSortCapabilities",
            "Search",
        ],
        "urn:schemas-upnp-org:service:ConnectionManager:1": ["GetProtocolInfo"],
    }
    for service_type, service in profile_device.services.items():
        service.actions = dict.fromkeys(actions[service_type])

    dms_device_mock.search_capabilities = ["dc:title", "upnp:class"]
    dms_device_mock.sort_capabilities = ["dc:title", "dc:date"]
    dms_device_mock.source_protocol_info = [
        "http-get:*:audio/mpeg:*",
        "http-get:*:video/mp4:*",
    ]
    dms_device_mock.system_update_id = 42
    return dms_device_mock


@pytest.mark.usefixtures("connected_device")
async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    config_entry_mock: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics for a connected device."""
    config_entry_mock.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry_mock.entry_id)
    await hass.async_block_till_done()

    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, config_entry_mock)
        == snapshot
    )


@pytest.mark.usefixtures("dms_device_mock")
async def test_diagnostics_disconnected(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    upnp_factory_mock: Mock,
    config_entry_mock: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics when the device is not connected."""
    upnp_factory_mock.async_create_device.side_effect = UpnpConnectionError
    config_entry_mock.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry_mock.entry_id)
    await hass.async_block_till_done()

    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, config_entry_mock)
        == snapshot
    )
