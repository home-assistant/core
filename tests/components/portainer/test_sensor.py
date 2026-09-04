"""Tests for the Portainer sensor platform."""

from typing import Any, cast
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from pyportainer.exceptions import PortainerTimeoutError
from pyportainer.models.docker import EndpointStatus
from pyportainer.models.portainer import Endpoint
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.portainer.const import DOMAIN
from homeassistant.components.portainer.coordinator import DEFAULT_DF_SCAN_INTERVAL
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


@pytest.mark.usefixtures("mock_portainer_client")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with patch(
        "homeassistant.components.portainer._PLATFORMS",
        [Platform.SENSOR],
    ):
        await setup_integration(hass, mock_config_entry)
        await snapshot_platform(
            hass,
            entity_registry,
            snapshot,
            mock_config_entry.entry_id,
        )


async def test_df_endpoint_timeout_only_marks_that_endpoint_unavailable(
    hass: HomeAssistant,
    mock_portainer_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a timeout fetching one endpoint's disk usage doesn't affect other endpoints."""
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
    assert (
        state := hass.states.get("sensor.my_environment_image_disk_usage_total_size")
    )
    assert state.state != STATE_UNAVAILABLE
    assert (
        state := hass.states.get("sensor.my_edge_offline_image_disk_usage_total_size")
    )
    assert state.state != STATE_UNAVAILABLE

    docker_system_df = mock_portainer_client.docker_system_df.return_value

    async def _docker_system_df(endpoint_id: int) -> Any:
        if endpoint_id == 42:
            raise PortainerTimeoutError("timeout")
        return docker_system_df

    mock_portainer_client.docker_system_df.side_effect = _docker_system_df

    freezer.tick(DEFAULT_DF_SCAN_INTERVAL)
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done(wait_background_tasks=True)

    assert (
        state := hass.states.get("sensor.my_edge_offline_image_disk_usage_total_size")
    )
    assert state.state == STATE_UNAVAILABLE
    assert (
        state := hass.states.get("sensor.my_environment_image_disk_usage_total_size")
    )
    assert state.state != STATE_UNAVAILABLE
