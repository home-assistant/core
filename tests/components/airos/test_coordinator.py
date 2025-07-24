"""Coordinator Ubiquiti airOS tests."""

from asyncio import TimeoutError
from typing import Any
from unittest.mock import AsyncMock

from airos.exceptions import (
    ConnectionAuthenticationError,
    DataMissingError,
    DeviceConnectionError,
)
import pytest

from homeassistant.components.airos.coordinator import AirOSDataUpdateCoordinator
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import ConfigEntryError, UpdateFailed


@pytest.fixture
def mock_hass():
    """Mock HomeAssistant instance."""
    return AsyncMock(spec=HomeAssistant)


@pytest.mark.parametrize(
    ("mock_airos_client", "expectation_error", "expected_key"),
    [
        (ConnectionAuthenticationError, ConfigEntryError, "invalid_auth"),
        (TimeoutError, UpdateFailed, "cannot_connect"),
        (DeviceConnectionError, UpdateFailed, "cannot_connect"),
        (DataMissingError, UpdateFailed, "error_data_missing"),
    ],
    indirect=["mock_airos_client"],
)
async def test_coordinator_async_update_data_exceptions(
    mock_hass: HomeAssistant,
    mock_config_entry: ConfigEntry,
    mock_airos_client: AsyncMock,
    ap_fixture: dict[str, Any],
    expected_key: str,
    expectation_error: Any,
) -> None:
    """Test async_update_data handles ConnectionAuthenticationError."""
    coordinator = AirOSDataUpdateCoordinator(
        mock_hass, mock_config_entry, mock_airos_client
    )

    with pytest.raises(expectation_error) as excinfo:
        await coordinator._async_update_data()
    assert excinfo.value.translation_key == expected_key
    mock_airos_client.login.assert_called_once()
    mock_airos_client.status.assert_not_called()
