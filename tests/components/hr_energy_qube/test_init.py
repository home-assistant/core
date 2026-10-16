"""Test the Qube Heat Pump integration init."""

from unittest.mock import MagicMock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.hr_energy_qube.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_integration

from tests.common import MockConfigEntry


async def test_setup_and_unload_entry(
    hass: HomeAssistant,
    mock_qube_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test successful setup and unload."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_qube_client.close.assert_called_once()


@pytest.mark.usefixtures("mock_qube_client")
async def test_device_info(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the device registry entry."""
    await setup_integration(hass, mock_config_entry)

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, mock_config_entry.entry_id), mock_config_entry.entry_id
    )
    assert device == snapshot


@pytest.mark.parametrize(
    ("connect_result", "connect_error"),
    [
        (False, None),
        (None, OSError("Connection refused")),
    ],
)
async def test_setup_entry_connection_failure(
    hass: HomeAssistant,
    mock_qube_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    connect_result: bool | None,
    connect_error: Exception | None,
) -> None:
    """Test setup failure when the device cannot be reached."""
    if connect_error is not None:
        mock_qube_client.connect.side_effect = connect_error
    else:
        mock_qube_client.connect.return_value = connect_result

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert (
        mock_config_entry.reason == "Unable to connect to the Qube heat pump at 1.2.3.4"
    )
    mock_qube_client.close.assert_called_once()
