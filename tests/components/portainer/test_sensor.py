"""Tests for the Portainer sensor platform."""

from typing import Any, cast
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from pyportainer.exceptions import PortainerTimeoutError
from pyportainer.models.docker import DockerContainerStats, EndpointStatus
from pyportainer.models.docker_inspect import DockerInspect
from pyportainer.models.portainer import Endpoint
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_load_json_array_fixture,
    load_json_value_fixture,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant import config_entries
from homeassistant.components.portainer.const import DOMAIN
from homeassistant.components.portainer.coordinator import (
    DEFAULT_DF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
)
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from . import setup_integration

CPU_USAGE_ENTITY_ID = "sensor.focused_einstein_cpu_usage_total"
DISK_USAGE_ENTITY_ID = "sensor.my_environment_image_disk_usage_total_size"
VOLUME_SIZE_ENTITY_ID = "sensor.myvolume_volume_size"


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

    async def _docker_system_df(endpoint_id: int, **kwargs: Any) -> Any:
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


# Overrides the autouse fixture, so entities get their default enabled state
@pytest.mark.parametrize("enable_all_entities", [None])
@pytest.mark.parametrize(
    "entity_id",
    [
        pytest.param(DISK_USAGE_ENTITY_ID, id="endpoint"),
        pytest.param(VOLUME_SIZE_ENTITY_ID, id="volume"),
    ],
)
async def test_disk_space_only_fetched_for_enabled_entities(
    hass: HomeAssistant,
    mock_portainer_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    entity_id: str,
) -> None:
    """Test disk space is disabled by default and only fetched while enabled."""
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

    for disk_space_entity_id in (
        DISK_USAGE_ENTITY_ID,
        "sensor.my_edge_offline_image_disk_usage_total_size",
        VOLUME_SIZE_ENTITY_ID,
    ):
        assert (entry := entity_registry.async_get(disk_space_entity_id))
        assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    mock_portainer_client.docker_system_df.assert_not_called()

    # Enabling the entity reloads the config entry after a delay. Waiting for that
    # reload keeps it from firing during the disk space poll below.
    entity_registry.async_update_entity(entity_id, disabled_by=None)
    freezer.tick(config_entries.RELOAD_AFTER_UPDATE_DELAY)
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done(wait_background_tasks=True)

    mock_portainer_client.docker_system_df.assert_called_once_with(1, verbose=True)
    assert (state := hass.states.get(entity_id))
    assert state.state != STATE_UNAVAILABLE

    freezer.tick(DEFAULT_DF_SCAN_INTERVAL)
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_portainer_client.docker_system_df.call_count == 2
    mock_portainer_client.docker_system_df.assert_called_with(1, verbose=True)

    entity_registry.async_update_entity(
        entity_id, disabled_by=er.RegistryEntryDisabler.USER
    )
    await hass.async_block_till_done()
    freezer.tick(DEFAULT_DF_SCAN_INTERVAL)
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_portainer_client.docker_system_df.call_count == 2


async def test_volume_size_from_disk_space(
    hass: HomeAssistant,
    mock_portainer_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test volume size comes from the disk space poll, not the regular poll."""
    await setup_integration(hass, mock_config_entry)
    assert (state := hass.states.get(VOLUME_SIZE_ENTITY_ID))
    assert state.state == "0.09765625"

    mock_portainer_client.docker_system_df.reset_mock()
    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done(wait_background_tasks=True)

    mock_portainer_client.docker_system_df.assert_not_called()

    mock_portainer_client.docker_system_df.side_effect = PortainerTimeoutError(
        "timeout"
    )
    freezer.tick(DEFAULT_DF_SCAN_INTERVAL)
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done(wait_background_tasks=True)

    assert (state := hass.states.get(VOLUME_SIZE_ENTITY_ID))
    assert state.state == STATE_UNAVAILABLE
    assert (state := hass.states.get("sensor.myvolume_volume_driver"))
    assert state.state != STATE_UNAVAILABLE


async def test_volume_size_unknown_when_not_measured(
    hass: HomeAssistant,
    mock_portainer_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test volume size is unknown when Docker does not measure the volume."""
    await setup_integration(hass, mock_config_entry)

    mock_portainer_client.docker_system_df.return_value.volume_disk_usage.items = []
    freezer.tick(DEFAULT_DF_SCAN_INTERVAL)
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done(wait_background_tasks=True)

    assert (state := hass.states.get(VOLUME_SIZE_ENTITY_ID))
    assert state.state == STATE_UNKNOWN


async def test_volume_size_unavailable_when_volume_deleted(
    hass: HomeAssistant,
    mock_portainer_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test volume size follows the regular poll when the volume is deleted."""
    await setup_integration(hass, mock_config_entry)

    mock_portainer_client.get_volumes.return_value = []
    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done(wait_background_tasks=True)

    assert (state := hass.states.get(VOLUME_SIZE_ENTITY_ID))
    assert state.state == STATE_UNAVAILABLE


async def test_endpoint_timeout_keeps_known_entities(
    hass: HomeAssistant,
    mock_portainer_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a timed-out poll doesn't re-add entities or reset CPU usage."""
    await setup_integration(hass, mock_config_entry)

    mock_portainer_client.docker_version.side_effect = PortainerTimeoutError("timeout")
    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done(wait_background_tasks=True)

    assert (state := hass.states.get(CPU_USAGE_ENTITY_ID))
    assert state.state == STATE_UNAVAILABLE

    stats = cast(
        dict[str, Any], load_json_value_fixture("container_stats.json", DOMAIN)
    )
    stats["cpu_stats"]["system_cpu_usage"] += 1_000_000_000
    stats["cpu_stats"]["cpu_usage"]["total_usage"] += 125_000_000
    mock_portainer_client.container_stats.return_value = DockerContainerStats.from_dict(
        stats
    )
    mock_portainer_client.docker_version.side_effect = None
    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done(wait_background_tasks=True)

    # Usage is averaged since the last successful poll
    assert (state := hass.states.get(CPU_USAGE_ENTITY_ID))
    assert state.state == "50.0"
    assert "does not generate unique IDs" not in caplog.text


async def test_container_never_started(
    hass: HomeAssistant,
    mock_portainer_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the started sensor is unknown for a container that never started."""
    inspect = cast(
        dict[str, Any], load_json_value_fixture("container_inspect.json", DOMAIN)
    )
    inspect["State"]["StartedAt"] = "0001-01-01T00:00:00Z"
    mock_portainer_client.inspect_container.return_value = DockerInspect.from_dict(
        inspect
    )

    await setup_integration(hass, mock_config_entry)

    assert (state := hass.states.get("sensor.focused_einstein_started"))
    assert state.state == STATE_UNKNOWN
