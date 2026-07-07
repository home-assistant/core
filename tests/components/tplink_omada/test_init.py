"""Tests for TP-Link Omada integration init."""

from unittest.mock import MagicMock

import pytest
from tplink_omada_client.exceptions import (
    ConnectionFailed,
    OmadaClientException,
    UnsupportedControllerVersion,
)

from homeassistant.components.tplink_omada.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry

MOCK_ENTRY_DATA = {
    "host": "https://fake.omada.host",
    "verify_ssl": True,
    "site": "SiteId",
    "username": "test-username",
    "password": "test-password",
}


@pytest.mark.parametrize(
    ("side_effect", "entry_state"),
    [
        (
            UnsupportedControllerVersion("4.0.0"),
            ConfigEntryState.SETUP_ERROR,
        ),
        (
            ConnectionFailed(),
            ConfigEntryState.SETUP_RETRY,
        ),
        (
            OmadaClientException(),
            ConfigEntryState.SETUP_RETRY,
        ),
    ],
)
async def test_setup_entry_login_failed_raises_configentryauthfailed(
    hass: HomeAssistant,
    mock_omada_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    side_effect: OmadaClientException,
    entry_state: ConfigEntryState,
) -> None:
    """Test setup entry with login failed raises ConfigEntryAuthFailed."""
    mock_omada_client.login.side_effect = side_effect

    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is entry_state


async def test_missing_devices_removed_at_startup(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_omada_client: MagicMock,
) -> None:
    """Test missing devices are removed at startup."""
    mock_config_entry = MockConfigEntry(
        title="Test Omada Controller",
        domain=DOMAIN,
        data=dict(MOCK_ENTRY_DATA),
        unique_id="12345_SiteId",
        version=2,
    )
    mock_config_entry.add_to_hass(hass)

    device_entry = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, "AA:BB:CC:DD:EE:FF")},
        manufacturer="TPLink",
        name="Old Device",
        model="Some old model",
    )

    assert device_registry.async_get(device_entry.id) == device_entry

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert device_registry.async_get(device_entry.id) is None


async def test_controller_device_registered_at_startup(
    device_registry: dr.DeviceRegistry,
    init_integration: MockConfigEntry,
) -> None:
    """Test the controller is registered as a device."""
    controller_device = device_registry.async_get_device(
        identifiers={(DOMAIN, "12345")}
    )

    assert controller_device is not None
    assert controller_device.config_entries == {init_integration.entry_id}
    assert controller_device.manufacturer == "TP-Link"
    assert controller_device.model == "OC200"
    assert controller_device.name == "OC200"
    assert controller_device.sw_version == "6.2.10.17"


async def test_omada_devices_link_to_controller_device(
    device_registry: dr.DeviceRegistry,
    init_integration: MockConfigEntry,
) -> None:
    """Test Omada devices are linked to the controller device."""
    controller_device = device_registry.async_get_device(
        identifiers={(DOMAIN, "12345")}
    )
    gateway_device = device_registry.async_get_device(
        identifiers={(DOMAIN, "AA-BB-CC-DD-EE-FF")}
    )
    switch_device = device_registry.async_get_device(
        identifiers={(DOMAIN, "54-AF-97-00-00-01")}
    )

    assert controller_device is not None
    assert gateway_device is not None
    assert switch_device is not None
    assert controller_device.config_entries == {init_integration.entry_id}
    assert gateway_device.via_device_id == controller_device.id
    assert switch_device.via_device_id == controller_device.id


async def test_migrate_entry_v1_to_v2(
    hass: HomeAssistant,
    mock_omada_client: MagicMock,
) -> None:
    """Test migration of a version 1 config entry to version 2."""
    entry = MockConfigEntry(
        title="Test Omada Controller",
        domain=DOMAIN,
        data=dict(MOCK_ENTRY_DATA),
        unique_id="12345",
        version=1,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.version == 2
    assert entry.unique_id == "12345_SiteId"
    assert entry.state is ConfigEntryState.LOADED
