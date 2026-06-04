"""Test the Aqvify init."""

from collections.abc import Generator
from unittest.mock import MagicMock

from pyaqvify import AqvifyAuthException
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
import homeassistant.helpers.device_registry as dr

from . import setup_integration

from tests.common import MockConfigEntry


async def test_load_unload_entry(
    hass: HomeAssistant,
    mock_aqvify_client: Generator[MagicMock],
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test load and unload entry."""
    await setup_integration(hass, mock_config_entry)
    entry = mock_config_entry

    assert entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("error", "expected_state"),
    [
        (None, ConfigEntryState.LOADED),
        (AqvifyAuthException, ConfigEntryState.SETUP_ERROR),
        (TimeoutError, ConfigEntryState.SETUP_RETRY),
    ],
    ids=["no_error", "auth_error", "timeout_error"],
)
async def test_setup_entry_with_error(
    hass: HomeAssistant,
    mock_aqvify_client: Generator[MagicMock],
    mock_config_entry: MockConfigEntry,
    error: Exception | None,
    expected_state: ConfigEntryState,
) -> None:
    """Test setup entry with error."""
    mock_aqvify_client.async_get_account_id.side_effect = error

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is expected_state


async def test_device_registry_integration(
    hass: HomeAssistant,
    mock_aqvify_client: Generator[MagicMock],
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test device registry integration creates correct devices."""
    await setup_integration(hass, mock_config_entry)
    await hass.async_block_till_done()

    # Get all devices created for this config entry
    device_entries = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )

    # Snapshot the devices to ensure they have the correct structure
    assert device_entries == snapshot
