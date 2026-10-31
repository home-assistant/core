"""Test the Teltonika integration."""

from typing import Any
from unittest.mock import MagicMock

import pytest
from pytest_homeassistant.common import MockConfigEntry
from syrupy.assertion import SnapshotAssertion
from teltasync import TeltonikaAuthenticationError, TeltonikaConnectionError

from homeassistant.components.teltonika.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr


async def test_load_unload_config_entry(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test loading and unloading the integration."""
    assert init_integration.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()

    assert init_integration.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("exception", "expected_state"),
    [
        (
            TeltonikaConnectionError("Connection failed"),
            ConfigEntryState.SETUP_RETRY,
        ),
        (
            TeltonikaAuthenticationError("Invalid credentials"),
            ConfigEntryState.SETUP_ERROR,
        ),
    ],
    ids=[
        "connection_error",
        "auth_error",
    ],
)
async def test_setup_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_teltasync: MagicMock,
    exception: Exception,
    expected_state: ConfigEntryState,
) -> None:
    """Test various setup errors result in appropriate config entry states."""
    mock_teltasync.return_value.get_device_info.side_effect = exception

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is expected_state


@pytest.mark.usefixtures("hass")
@pytest.mark.usefixtures("init_integration")
async def test_device_registry_creation(
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test device registry creation."""
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "1234567890"), mock_config_entry.entry_id
    )
    assert device is not None
    assert device == snapshot


@pytest.mark.parametrize(
    ("host", "expected_data", "expected_base_url"),
    [
        (
            "https://192.168.1.1",
            {CONF_HOST: "192.168.1.1", CONF_PORT: 443, CONF_SSL: True},
            "https://192.168.1.1/api",
        ),
        (
            "https://192.168.1.1:8443",
            {CONF_HOST: "192.168.1.1", CONF_PORT: 8443, CONF_SSL: True},
            "https://192.168.1.1:8443/api",
        ),
        (
            "http://router.lan:8080",
            {CONF_HOST: "router.lan", CONF_PORT: 8080, CONF_SSL: False},
            "http://router.lan:8080/api",
        ),
        (
            "192.168.1.1",
            {CONF_HOST: "192.168.1.1", CONF_PORT: 443, CONF_SSL: True},
            "https://192.168.1.1/api",
        ),
    ],
)
@pytest.mark.usefixtures("mock_modems")
async def test_migrate_entry_v1(
    hass: HomeAssistant,
    mock_teltasync: MagicMock,
    host: str,
    expected_data: dict[str, Any],
    expected_base_url: str,
) -> None:
    """Test a version 1 entry has its URL split into host, port and SSL."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="RUTX50 Test",
        version=1,
        data={CONF_HOST: host, CONF_USERNAME: "admin", CONF_PASSWORD: "password"},
        unique_id="1234567890",
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.version == 2
    assert entry.minor_version == 1
    assert entry.data == {
        **expected_data,
        CONF_USERNAME: "admin",
        CONF_PASSWORD: "password",
    }
    assert mock_teltasync.call_args.kwargs["base_url"] == expected_base_url
