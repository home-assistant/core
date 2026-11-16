"""Tests for the Proxmox VE sensor platform."""

from datetime import timedelta
from typing import Any
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_load_json_array_fixture,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.proxmoxve.coordinator import DEFAULT_UPDATE_INTERVAL
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import PVEVMUSER_PERMISSIONS, setup_integration


@pytest.fixture(autouse=True)
def enable_all_entities(entity_registry_enabled_by_default: None) -> None:
    """Make sure all entities are enabled."""


@pytest.mark.freeze_time("2026-05-03T12:00:00+00:00")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_proxmox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with patch(
        "homeassistant.components.proxmoxve.PLATFORMS",
        [Platform.SENSOR],
    ):
        await setup_integration(hass, mock_config_entry)
        await snapshot_platform(
            hass,
            entity_registry,
            snapshot,
            mock_config_entry.entry_id,
        )


async def test_storage_missing_used_fraction(
    hass: HomeAssistant,
    mock_proxmox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test storage usage percentage sensor when used_fraction is missing."""
    storage_data = await async_load_json_array_fixture(
        hass, "nodes/storage.json", "proxmoxve"
    )
    # Remove used_fraction from all storage entries
    storage_without_fraction = [
        {key: value for key, value in storage.items() if key != "used_fraction"}
        for storage in storage_data
    ]
    mock_proxmox_client._node_mock.storage.get.return_value = storage_without_fraction

    with patch(
        "homeassistant.components.proxmoxve.PLATFORMS",
        [Platform.SENSOR],
    ):
        await setup_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.storage_local_storage_usage_percentage")
    assert state.state == STATE_UNKNOWN


async def test_sensors_according_to_permissions(
    hass: HomeAssistant,
    mock_proxmox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that sensors are not created when not allowed."""
    mock_proxmox_client.access.permissions.get.return_value = PVEVMUSER_PERMISSIONS

    with patch(
        "homeassistant.components.proxmoxve.PLATFORMS",
        [Platform.SENSOR],
    ):
        await setup_integration(hass, mock_config_entry)

    entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )

    assert "sensor.pve1_status" in {e.entity_id for e in entries}
    assert "sensor.pve1_cpu" not in {e.entity_id for e in entries}


async def test_sensors_for_offline_node(
    hass: HomeAssistant,
    mock_proxmox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that node sensors except status are unavailable."""
    mock_proxmox_client.nodes.get.return_value = mock_proxmox_client._all_nodes

    with patch(
        "homeassistant.components.proxmoxve.PLATFORMS",
        [Platform.SENSOR],
    ):
        await setup_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.pve3_status")
    assert state.state == "offline"

    state = hass.states.get("sensor.pve3_disk_usage")
    assert state.state == STATE_UNAVAILABLE

    state = hass.states.get("sensor.pve4_status")
    assert state.state == "unknown"

    state = hass.states.get("sensor.pve4_disk_usage")
    assert state.state == STATE_UNAVAILABLE


GUEST_UPTIME_PARAMS = [
    pytest.param("qemu", 100, "sensor.vm_web_uptime", id="vm"),
    pytest.param("lxc", "200", "sensor.ct_nginx_uptime", id="container"),
]


def _guest(
    mock_proxmox_client: MagicMock, endpoint: str, vmid: int | str
) -> dict[str, Any]:
    """Return the mocked API data of a guest."""
    guests = getattr(mock_proxmox_client._node_mock, endpoint).get.return_value
    return next(guest for guest in guests if guest["vmid"] == vmid)


async def _poll(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, seconds: float
) -> None:
    """Advance the clock and let the coordinator poll once."""
    freezer.tick(timedelta(seconds=seconds))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)


@pytest.mark.parametrize(("endpoint", "vmid", "entity_id"), GUEST_UPTIME_PARAMS)
@pytest.mark.parametrize(
    ("status", "uptime"),
    [
        pytest.param("stopped", 0, id="stopped"),
        pytest.param("stopped", 3600, id="stopped_with_uptime"),
        pytest.param("running", 0, id="running_without_uptime"),
        pytest.param("running", None, id="running_uptime_none"),
    ],
)
async def test_guest_uptime_unknown(
    hass: HomeAssistant,
    mock_proxmox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    endpoint: str,
    vmid: int | str,
    entity_id: str,
    status: str,
    uptime: int | None,
) -> None:
    """Test the uptime is unknown and stays unchanged for a guest that is not up."""
    guest = _guest(mock_proxmox_client, endpoint, vmid)
    guest["status"] = status
    guest["uptime"] = uptime

    with patch("homeassistant.components.proxmoxve.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    state = hass.states.get(entity_id)
    assert state.state == STATE_UNKNOWN
    last_changed = state.last_changed

    await _poll(hass, freezer, DEFAULT_UPDATE_INTERVAL.total_seconds())

    state = hass.states.get(entity_id)
    assert state.state == STATE_UNKNOWN
    assert state.last_changed == last_changed


@pytest.mark.freeze_time("2026-05-03T12:00:00.250000+00:00")
@pytest.mark.parametrize(("endpoint", "vmid", "entity_id"), GUEST_UPTIME_PARAMS)
async def test_guest_uptime_stable_while_running(
    hass: HomeAssistant,
    mock_proxmox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    endpoint: str,
    vmid: int | str,
    entity_id: str,
) -> None:
    """Test the boot time does not change between polls of a running guest."""
    guest = _guest(mock_proxmox_client, endpoint, vmid)
    guest["uptime"] = 3600

    with patch("homeassistant.components.proxmoxve.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    state = hass.states.get(entity_id)
    assert state.state == "2026-05-03T11:00:00+00:00"
    last_changed = state.last_changed

    # Wall clock and reported uptime drift apart by a fraction of a second
    guest["uptime"] = 3600 + 60
    await _poll(hass, freezer, 60.8)

    state = hass.states.get(entity_id)
    assert state.state == "2026-05-03T11:00:00+00:00"
    assert state.last_changed == last_changed


@pytest.mark.freeze_time("2026-05-03T12:00:00+00:00")
@pytest.mark.parametrize(("endpoint", "vmid", "entity_id"), GUEST_UPTIME_PARAMS)
async def test_guest_uptime_running_stopped_running(
    hass: HomeAssistant,
    mock_proxmox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    endpoint: str,
    vmid: int | str,
    entity_id: str,
) -> None:
    """Test the uptime follows a guest that is stopped and started again."""
    guest = _guest(mock_proxmox_client, endpoint, vmid)
    guest["uptime"] = 3600

    with patch("homeassistant.components.proxmoxve.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    assert hass.states.get(entity_id).state == "2026-05-03T11:00:00+00:00"

    guest["status"] = "stopped"
    guest["uptime"] = 0
    await _poll(hass, freezer, 60)

    assert hass.states.get(entity_id).state == STATE_UNKNOWN

    guest["status"] = "running"
    guest["uptime"] = 5
    await _poll(hass, freezer, 60)

    assert hass.states.get(entity_id).state == "2026-05-03T12:01:55+00:00"
