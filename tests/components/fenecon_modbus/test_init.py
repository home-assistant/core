"""Test the Fenecon Modbus setup and coordinator."""

from unittest.mock import MagicMock

from fenecon_modbus import (
    FeneconConnectionError,
    FeneconInvalidResponseError,
    FeneconTimeoutError,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.fenecon_modbus.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import SERIAL, setup_integration


async def test_load_unload(
    hass: HomeAssistant,
    mock_fenecon_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test loading and unloading the config entry closes the connection."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_fenecon_client.close.assert_not_awaited()

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_fenecon_client.close.assert_awaited_once()


@pytest.mark.parametrize("method", ["read_device_info", "read_data"])
@pytest.mark.parametrize(
    "side_effect",
    [FeneconConnectionError, FeneconTimeoutError, FeneconInvalidResponseError],
)
async def test_setup_retry(
    hass: HomeAssistant,
    mock_fenecon_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    method: str,
    side_effect: type[Exception],
) -> None:
    """Test setup is retried when the FEMS cannot be read."""
    getattr(mock_fenecon_client, method).side_effect = side_effect

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    mock_fenecon_client.close.assert_awaited_once()


@pytest.mark.usefixtures("mock_fenecon_client")
async def test_device_info(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the device is registered with the identification data."""
    await setup_integration(hass, mock_config_entry)

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, SERIAL), mock_config_entry.entry_id
    )
    assert device == snapshot
