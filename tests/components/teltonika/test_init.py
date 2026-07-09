"""Test the Teltonika integration."""

from unittest.mock import MagicMock

import pytest
from syrupy.assertion import SnapshotAssertion
from teltasync import TeltonikaAuthenticationError, TeltonikaConnectionError

from homeassistant.components.teltonika.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry


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
    snapshot: SnapshotAssertion,
) -> None:
    """Test device registry creation."""
    device = device_registry.async_get_device(identifiers={(DOMAIN, "1234567890")})
    assert device is not None
    assert device == snapshot
