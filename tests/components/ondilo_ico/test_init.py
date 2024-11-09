"""Test Ondilo ICO initialization."""

from typing import Any
from unittest.mock import MagicMock

from ondilo import OndiloError
import pytest
from syrupy import SnapshotAssertion

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_integration

from tests.common import MockConfigEntry


async def test_devices(
    hass: HomeAssistant,
    mock_ondilo_client: MagicMock,
    device_registry: dr.DeviceRegistry,
    config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test devices are registered."""
    await setup_integration(hass, config_entry, mock_ondilo_client)

    device_entries = dr.async_entries_for_config_entry(
        device_registry, config_entry.entry_id
    )

    assert len(device_entries) == 2

    for device_entry in device_entries:
        identifier = list(device_entry.identifiers)[0]
        assert device_entry == snapshot(name=f"{identifier[0]}-{identifier[1]}")


async def test_get_pools_error(
    hass: HomeAssistant,
    mock_ondilo_client: MagicMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test get pools errors."""
    mock_ondilo_client.get_pools.side_effect = OndiloError(
        502,
        (
            "<html> <head><title>502 Bad Gateway</title></head> "
            "<body> <center><h1>502 Bad Gateway</h1></center> </body> </html>"
        ),
    )
    await setup_integration(hass, config_entry, mock_ondilo_client)

    # No sensor should be created
    assert not hass.states.async_all()
    # We should not have tried to retrieve pool measures
    assert mock_ondilo_client.get_ICO_details.call_count == 0
    assert mock_ondilo_client.get_last_pool_measures.call_count == 0
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_init_with_no_ico_attached(
    hass: HomeAssistant,
    mock_ondilo_client: MagicMock,
    config_entry: MockConfigEntry,
    pool1: dict[str, Any],
) -> None:
    """Test if an ICO is not attached to a pool, then no sensor is created."""
    # Only one pool, but no ICO attached
    mock_ondilo_client.get_pools.return_value = pool1
    mock_ondilo_client.get_ICO_details.side_effect = None
    mock_ondilo_client.get_ICO_details.return_value = None
    await setup_integration(hass, config_entry, mock_ondilo_client)

    # No sensor should be created
    assert len(hass.states.async_all()) == 0
    # We should not have tried to retrieve pool measures
    mock_ondilo_client.get_last_pool_measures.assert_not_called()
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize("api", ["get_ICO_details", "get_last_pool_measures"])
async def test_details_error_all_pools(
    hass: HomeAssistant,
    mock_ondilo_client: MagicMock,
    device_registry: dr.DeviceRegistry,
    config_entry: MockConfigEntry,
    pool1: dict[str, Any],
    api: str,
) -> None:
    """Test details and measures error for all pools."""
    mock_ondilo_client.get_pools.return_value = pool1
    client_api = getattr(mock_ondilo_client, api)
    client_api.side_effect = OndiloError(400, "error")

    await setup_integration(hass, config_entry, mock_ondilo_client)

    device_entries = dr.async_entries_for_config_entry(
        device_registry, config_entry.entry_id
    )

    assert not device_entries
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_details_error_one_pool(
    hass: HomeAssistant,
    mock_ondilo_client: MagicMock,
    device_registry: dr.DeviceRegistry,
    config_entry: MockConfigEntry,
    ico_details2: dict[str, Any],
) -> None:
    """Test details error for one pool and success for the other."""
    mock_ondilo_client.get_ICO_details.side_effect = [
        OndiloError(
            404,
            "Not Found",
        ),
        ico_details2,
    ]

    await setup_integration(hass, config_entry, mock_ondilo_client)

    device_entries = dr.async_entries_for_config_entry(
        device_registry, config_entry.entry_id
    )

    assert len(device_entries) == 1


async def test_measures_error_one_pool(
    hass: HomeAssistant,
    mock_ondilo_client: MagicMock,
    device_registry: dr.DeviceRegistry,
    config_entry: MockConfigEntry,
    last_measures: list[dict[str, Any]],
) -> None:
    """Test measures error for one pool and success for the other."""
    mock_ondilo_client.get_last_pool_measures.side_effect = [
        OndiloError(
            404,
            "Not Found",
        ),
        last_measures,
    ]

    await setup_integration(hass, config_entry, mock_ondilo_client)

    device_entries = dr.async_entries_for_config_entry(
        device_registry, config_entry.entry_id
    )

    assert len(device_entries) == 1
