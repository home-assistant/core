"""Test the Wolf SmartSet Service coordinator."""

from unittest.mock import MagicMock

from httpx import RequestError
from wolf_comm.token_auth import InvalidAuth
from wolf_comm.wolf_client import FetchFailed, ParameterReadError

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_coordinator_device_offline(
    hass: HomeAssistant,
    mock_wolflink: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test coordinator marks update failed and sets refetch flag when device is offline."""
    coordinator = init_integration.runtime_data.coordinators[0]
    mock_wolflink.fetch_system_state_list.return_value = False

    await coordinator.async_refresh()

    assert coordinator.last_update_success is False
    assert coordinator._refetch_parameters is True


async def test_coordinator_refetch_parameters_on_recovery(
    hass: HomeAssistant,
    mock_wolflink: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test coordinator re-fetches parameters when device comes back online."""
    coordinator = init_integration.runtime_data.coordinators[0]

    # Simulate device going offline to set _refetch_parameters
    mock_wolflink.fetch_system_state_list.return_value = False
    await coordinator.async_refresh()
    assert coordinator._refetch_parameters is True

    # Device comes back online — parameters should be re-fetched
    mock_wolflink.fetch_system_state_list.return_value = True
    fetch_parameters_call_count = mock_wolflink.fetch_parameters.call_count
    await coordinator.async_refresh()

    assert coordinator.last_update_success is True
    assert coordinator._refetch_parameters is False
    assert mock_wolflink.fetch_parameters.call_count > fetch_parameters_call_count


async def test_coordinator_request_error(
    hass: HomeAssistant,
    mock_wolflink: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test coordinator raises UpdateFailed on RequestError."""
    coordinator = init_integration.runtime_data.coordinators[0]
    mock_wolflink.fetch_system_state_list.side_effect = RequestError("network error")

    await coordinator.async_refresh()

    assert coordinator.last_update_success is False


async def test_coordinator_fetch_failed(
    hass: HomeAssistant,
    mock_wolflink: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test coordinator raises UpdateFailed on FetchFailed."""
    coordinator = init_integration.runtime_data.coordinators[0]
    mock_wolflink.fetch_value.side_effect = FetchFailed("server error")

    await coordinator.async_refresh()

    assert coordinator.last_update_success is False


async def test_coordinator_parameter_read_error(
    hass: HomeAssistant,
    mock_wolflink: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test coordinator sets refetch flag and raises UpdateFailed on ParameterReadError."""
    coordinator = init_integration.runtime_data.coordinators[0]
    mock_wolflink.fetch_value.side_effect = ParameterReadError("param error")

    await coordinator.async_refresh()

    assert coordinator.last_update_success is False
    assert coordinator._refetch_parameters is True


async def test_coordinator_invalid_auth(
    hass: HomeAssistant,
    mock_wolflink: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test coordinator handles InvalidAuth by triggering config entry re-auth."""
    coordinator = init_integration.runtime_data.coordinators[0]
    mock_wolflink.fetch_system_state_list.side_effect = InvalidAuth

    await coordinator.async_refresh()

    # The coordinator wraps InvalidAuth as ConfigEntryAuthFailed which
    # causes the config entry to enter the setup error state.
    assert coordinator.last_update_success is False
