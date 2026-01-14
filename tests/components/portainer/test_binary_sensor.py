"""Tests for the Portainer binary sensor platform."""

from unittest.mock import AsyncMock, patch

from pyportainer.exceptions import (
    PortainerAuthenticationError,
    PortainerConnectionError,
    PortainerTimeoutError,
)
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture(autouse=True)
def enable_all_entities(entity_registry_enabled_by_default: None) -> None:
    """Make sure all entities are enabled."""


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_portainer_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with patch(
        "homeassistant.components.portainer._PLATFORMS",
        [Platform.BINARY_SENSOR],
    ):
        await setup_integration(hass, mock_config_entry)
        await snapshot_platform(
            hass, entity_registry, snapshot, mock_config_entry.entry_id
        )


@pytest.mark.parametrize(
    ("exception"),
    [
        PortainerAuthenticationError("bad creds"),
        PortainerConnectionError("cannot connect"),
        PortainerTimeoutError("timeout"),
    ],
)
async def test_refresh_endpoints_exceptions(
    hass: HomeAssistant,
    mock_portainer_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
) -> None:
    """Test entities go unavailable after coordinator refresh failures, for the endpoint fetch."""
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    mock_portainer_client.get_endpoints.side_effect = exception

    await mock_config_entry.runtime_data.async_refresh()

    state = hass.states.get("binary_sensor.practical_morse_status")
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    ("exception"),
    [
        PortainerAuthenticationError("bad creds"),
        PortainerConnectionError("cannot connect"),
        PortainerTimeoutError("timeout"),
    ],
)
async def test_refresh_containers_exceptions(
    hass: HomeAssistant,
    mock_portainer_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
) -> None:
    """Test entities go unavailable after coordinator refresh failures, for the container fetch."""
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    mock_portainer_client.get_containers.side_effect = exception

    await mock_config_entry.runtime_data.async_refresh()

    state = hass.states.get("binary_sensor.practical_morse_status")
    assert state.state == STATE_UNAVAILABLE
