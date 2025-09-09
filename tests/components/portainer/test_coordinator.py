"""Test the Portainer Coordinator specific behavior."""

from unittest.mock import AsyncMock

from pyportainer.exceptions import (
    PortainerAuthenticationError,
    PortainerConnectionError,
    PortainerTimeoutError,
)
import pytest

from homeassistant.components.portainer.coordinator import PortainerCoordinator
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("exception", "expected_state"),
    [
        (PortainerAuthenticationError("bad creds"), ConfigEntryState.SETUP_ERROR),
        (PortainerConnectionError("cannot connect"), ConfigEntryState.SETUP_RETRY),
        (PortainerTimeoutError("timeout"), ConfigEntryState.SETUP_RETRY),
    ],
)
async def test_setup_exceptions(
    hass: HomeAssistant,
    mock_portainer_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    expected_state: ConfigEntryState,
) -> None:
    """Test the _async_setup."""
    mock_portainer_client.get_endpoints.side_effect = exception
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state == expected_state


@pytest.mark.parametrize(
    ("exception"),
    [
        PortainerAuthenticationError("bad creds"),
        PortainerConnectionError("cannot connect"),
        PortainerTimeoutError("timeout"),
    ],
)
async def test_refresh_exceptions(
    hass: HomeAssistant,
    mock_portainer_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
) -> None:
    """Test entities go unavailable after coordinator refresh failures."""
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    coordinator: PortainerCoordinator = mock_config_entry.runtime_data
    coordinator.portainer.get_endpoints.side_effect = exception

    await coordinator.async_refresh()

    state = hass.states.get("binary_sensor.practical_morse_status")
    assert state.state == STATE_UNAVAILABLE

    # Reset, since we need to check get_containers can also fail
    coordinator.portainer.get_endpoints.side_effect = None
    coordinator.portainer.get_containers.side_effect = exception

    await coordinator.async_refresh()

    state = hass.states.get("binary_sensor.practical_morse_status")
    assert state.state == STATE_UNAVAILABLE
