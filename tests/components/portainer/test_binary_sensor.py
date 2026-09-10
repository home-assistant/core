"""Tests for the Portainer binary sensor platform."""

from typing import Any, cast
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from pyportainer.exceptions import (
    PortainerAuthenticationError,
    PortainerConnectionError,
    PortainerTimeoutError,
)
from pyportainer.models.docker import EndpointStatus
from pyportainer.models.portainer import Endpoint
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.portainer.const import DOMAIN
from homeassistant.components.portainer.coordinator import DEFAULT_SCAN_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from . import setup_integration

from tests.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_load_json_array_fixture,
    snapshot_platform,
)


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
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test entities go unavailable after endpoint refresh failures."""
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    mock_portainer_client.get_endpoints.side_effect = exception

    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done(wait_background_tasks=True)

    assert (state := hass.states.get("binary_sensor.practical_morse_status"))
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
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test entities go unavailable after container refresh failures."""
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    mock_portainer_client.get_containers.side_effect = exception

    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done(wait_background_tasks=True)

    assert (state := hass.states.get("binary_sensor.practical_morse_status"))
    assert state.state == STATE_UNAVAILABLE


async def test_endpoint_timeout_only_marks_that_endpoint_unavailable(
    hass: HomeAssistant,
    mock_portainer_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a timeout fetching one endpoint's data doesn't affect other endpoints."""
    endpoints = cast(
        list[dict[str, Any]],
        await async_load_json_array_fixture(hass, "endpoints.json", DOMAIN),
    )
    for endpoint in endpoints:
        endpoint["Status"] = EndpointStatus.UP
    mock_portainer_client.get_endpoints.return_value = [
        Endpoint.from_dict(endpoint) for endpoint in endpoints
    ]

    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert (state := hass.states.get("binary_sensor.my_edge_offline_status"))
    assert state.state != STATE_UNAVAILABLE

    docker_version = mock_portainer_client.docker_version.return_value

    async def _docker_version(endpoint_id: int) -> Any:
        if endpoint_id == 42:
            raise PortainerTimeoutError("timeout")
        return docker_version

    mock_portainer_client.docker_version.side_effect = _docker_version

    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert (state := hass.states.get("binary_sensor.my_edge_offline_status"))
    assert state.state == STATE_UNAVAILABLE
    assert (state := hass.states.get("binary_sensor.my_environment_status"))
    assert state.state != STATE_UNAVAILABLE
