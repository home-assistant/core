"""Tests for the Proxmox VE update platform."""

from collections.abc import Callable
from dataclasses import replace
from unittest.mock import MagicMock, patch

from aioproxmox.exceptions import ProxmoxConnectionError
from aioproxmox.model import PVEPermissions
from aioproxmox.model.pve import (
    AptArchType,
    NodeAptUpdate,
    NodeAptUpdateProperty,
    OperationalStatus,
    ResourceType,
)
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from pytest_homeassistant.typing import WebSocketGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.proxmoxve.coordinator import (
    SOFTWARE_UPDATE_INTERVAL,
    STATUS_UPDATE_INTERVAL,
)
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import AUDIT_PERMISSIONS, MERGED_PERMISSIONS, setup_integration

ENTITY_ID = "update.pve1_software_update"
NEW_NODE_ENTITY_ID = "update.pve2_software_update"
NODE_STATUS_ENTITY_ID = "binary_sensor.pve1_status"


def _apt_update(package: str, version: str, origin: str = "") -> NodeAptUpdateProperty:
    """Return an apt update with only the fields relevant for versioning."""
    return NodeAptUpdateProperty(
        description="",
        arch=AptArchType.ALL,
        package=package,
        priority="optional",
        section="admin",
        title="",
        version=version,
        origin=origin,
    )


@pytest.mark.parametrize(
    ("updates", "expected_latest_version"),
    [
        pytest.param(
            [
                _apt_update("bind9-host", "1", "Debian"),
                _apt_update("pve-manager", "9.1.7", "Proxmox"),
                _apt_update("libpve-common-perl", "9.1.9", "Proxmox"),
                _apt_update("corosync", "3.1.10", "Proxmox"),
                _apt_update("pve-firmware", "3.18", "Proxmox"),
            ],
            "9.1.7-p4-d1",
            id="all-entities",
        ),
        pytest.param(
            [_apt_update("ceph-common", "19.2.6", "Proxmox")],
            "9.1.6-p1-d0",
            id="higher-ceph-version-is-not-pve-version",
        ),
        pytest.param(
            [_apt_update("libpve-storage-perl", "1+16.1+2+pmx1")],
            "9.1.6-p1-d0",
            id="debian-package-version-is-not-parsed",
        ),
        pytest.param(
            [
                _apt_update("ceph-common", "19.2.6", "Proxmox"),
                _apt_update("pve-manager", "9.2.21-1"),
            ],
            "9.2.21-p2-d0",
            id="pve-manager-version-is-used",
        ),
    ],
)
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_proxmox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    updates: list[NodeAptUpdateProperty],
    expected_latest_version: str,
) -> None:
    """Test all entities."""
    # Ensure Sys.Modify permissions to ensure update status can be determined
    mock_proxmox_client.access.permissions.return_value = (
        PVEPermissions.from_api_response(MERGED_PERMISSIONS)
    )
    mock_proxmox_client.nodes.return_value.apt.return_value.update.return_value = (
        NodeAptUpdate(items=updates)
    )

    with patch(
        "homeassistant.components.proxmoxve.PLATFORMS",
        [Platform.UPDATE],
    ):
        await setup_integration(hass, mock_config_entry)

    state = hass.states.get(ENTITY_ID)
    assert state.attributes["latest_version"] == expected_latest_version

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_update_entities_ignored(
    hass: HomeAssistant,
    mock_proxmox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that updates entities are not created with only auditor permissions."""
    mock_proxmox_client.access.permissions.return_value = (
        PVEPermissions.from_api_response(AUDIT_PERMISSIONS)
    )

    with patch(
        "homeassistant.components.proxmoxve.PLATFORMS",
        [Platform.UPDATE],
    ):
        await setup_integration(hass, mock_config_entry)

    assert hass.states.get(ENTITY_ID) is None


async def test_update_unavailable_on_permission_change(
    hass: HomeAssistant,
    mock_proxmox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that updates entities are unavailable with only auditor permissions."""
    mock_proxmox_client.access.permissions.return_value = (
        PVEPermissions.from_api_response(MERGED_PERMISSIONS)
    )

    with patch(
        "homeassistant.components.proxmoxve.PLATFORMS",
        [Platform.UPDATE],
    ):
        await setup_integration(hass, mock_config_entry)

    assert hass.states.get(ENTITY_ID).state is not None

    mock_proxmox_client.access.permissions.return_value = (
        PVEPermissions.from_api_response(AUDIT_PERMISSIONS)
    )

    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    "failing_call",
    [
        pytest.param(lambda node: node.version, id="version"),
        pytest.param(lambda node: node.apt.return_value.update, id="apt_update"),
    ],
)
async def test_update_unavailable_on_failed_software_update(
    hass: HomeAssistant,
    mock_proxmox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    failing_call: Callable[[MagicMock], MagicMock],
) -> None:
    """Test a failing software update only makes the update entity unavailable."""
    with patch(
        "homeassistant.components.proxmoxve.PLATFORMS",
        [Platform.BINARY_SENSOR, Platform.UPDATE],
    ):
        await setup_integration(hass, mock_config_entry)

    # Let the reload from enabling disabled-by-default entities settle
    freezer.tick(STATUS_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(ENTITY_ID).state == STATE_ON

    failing_call(mock_proxmox_client._node_mock).side_effect = ProxmoxConnectionError
    freezer.tick(SOFTWARE_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE
    assert hass.states.get(NODE_STATUS_ENTITY_ID).state == STATE_ON

    failing_call(mock_proxmox_client._node_mock).side_effect = None
    freezer.tick(SOFTWARE_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(ENTITY_ID).state == STATE_ON


async def test_update_unaffected_by_failed_status_update(
    hass: HomeAssistant,
    mock_proxmox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the update entity keeps its state while the status update fails."""
    with patch(
        "homeassistant.components.proxmoxve.PLATFORMS",
        [Platform.BINARY_SENSOR, Platform.UPDATE],
    ):
        await setup_integration(hass, mock_config_entry)

    # Let the reload from enabling disabled-by-default entities settle
    freezer.tick(STATUS_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    mock_proxmox_client.cluster.resources.side_effect = ProxmoxConnectionError
    freezer.tick(STATUS_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(NODE_STATUS_ENTITY_ID).state == STATE_UNAVAILABLE
    assert hass.states.get(ENTITY_ID).state == STATE_ON


async def test_software_update_interval(
    hass: HomeAssistant,
    mock_proxmox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test software info is fetched on its own interval, not on every status update."""
    with patch(
        "homeassistant.components.proxmoxve.PLATFORMS",
        [Platform.UPDATE],
    ):
        await setup_integration(hass, mock_config_entry)

    node = mock_proxmox_client._node_mock
    assert node.version.call_count == 1
    assert node.qemu_all.call_count == 1

    freezer.tick(STATUS_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert node.version.call_count == 1
    assert node.qemu_all.call_count == 2

    freezer.tick(SOFTWARE_UPDATE_INTERVAL - STATUS_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert node.version.call_count == 2
    assert node.apt.return_value.update.call_count == 2


async def test_new_node_fetches_software(
    hass: HomeAssistant,
    mock_proxmox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a node discovered after setup gets its update entity right away."""
    with patch(
        "homeassistant.components.proxmoxve.PLATFORMS",
        [Platform.UPDATE],
    ):
        await setup_integration(hass, mock_config_entry)

    assert hass.states.get(NEW_NODE_ENTITY_ID) is None

    mock_proxmox_client.cluster_resources.resources = [
        node
        for node in mock_proxmox_client._all_cluster_resources
        if node.node in ("pve1", "pve2")
    ]
    freezer.tick(STATUS_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(NEW_NODE_ENTITY_ID).state == STATE_ON


async def test_new_node_failed_software_retried_on_interval(
    hass: HomeAssistant,
    mock_proxmox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a failed software fetch for a new node is retried on the software interval."""
    with patch(
        "homeassistant.components.proxmoxve.PLATFORMS",
        [Platform.UPDATE],
    ):
        await setup_integration(hass, mock_config_entry)

    node = mock_proxmox_client._node_mock
    node.version.side_effect = ProxmoxConnectionError
    mock_proxmox_client.cluster_resources.resources = [
        node_resource
        for node_resource in mock_proxmox_client._all_cluster_resources
        if node_resource.node in ("pve1", "pve2")
    ]
    freezer.tick(STATUS_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert node.version.call_count == 2
    assert hass.states.get(NEW_NODE_ENTITY_ID).state == STATE_UNAVAILABLE

    # A failed software refresh must not be retried on every status update
    freezer.tick(STATUS_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert node.version.call_count == 2

    node.version.side_effect = None
    freezer.tick(SOFTWARE_UPDATE_INTERVAL - STATUS_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert node.version.call_count == 4
    assert hass.states.get(NEW_NODE_ENTITY_ID).state == STATE_ON


async def test_update_up_to_date(
    hass: HomeAssistant,
    mock_proxmox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that updates are up to date when no updates are pending."""
    mock_proxmox_client.access.permissions.return_value = (
        PVEPermissions.from_api_response(MERGED_PERMISSIONS)
    )
    mock_proxmox_client.nodes.return_value.apt.return_value.update.return_value = (
        NodeAptUpdate(items=[])
    )

    with patch(
        "homeassistant.components.proxmoxve.PLATFORMS",
        [Platform.UPDATE],
    ):
        await setup_integration(hass, mock_config_entry)

    state = hass.states.get(ENTITY_ID)
    assert state.attributes.get("latest_version") == "9.1.6"
    assert state.state == STATE_OFF


async def test_update_release_notes(
    hass: HomeAssistant,
    mock_proxmox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test that updates release notes are correctly set."""
    mock_proxmox_client.access.permissions.return_value = (
        PVEPermissions.from_api_response(MERGED_PERMISSIONS)
    )

    with patch(
        "homeassistant.components.proxmoxve.PLATFORMS",
        [Platform.UPDATE],
    ):
        await setup_integration(hass, mock_config_entry)

    ws_client = await hass_ws_client(hass)
    await ws_client.send_json(
        {"id": 1, "type": "update/release_notes", "entity_id": ENTITY_ID}
    )
    result = await ws_client.receive_json()
    assert "5 package" in result["result"]["release_notes"]


async def test_update_unavailable_when_node_offline(
    hass: HomeAssistant,
    mock_proxmox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the update entity follows the node status, not only the software data."""
    with patch(
        "homeassistant.components.proxmoxve.PLATFORMS",
        [Platform.UPDATE],
    ):
        await setup_integration(hass, mock_config_entry)

    assert hass.states.get(ENTITY_ID).state == STATE_ON

    online_resources = mock_proxmox_client.cluster_resources.resources
    mock_proxmox_client.cluster_resources.resources = [
        replace(resource, status=OperationalStatus.OFFLINE)
        if resource.resource_type == ResourceType.NODE and resource.node == "pve1"
        else resource
        for resource in online_resources
    ]
    freezer.tick(STATUS_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE

    mock_proxmox_client.cluster_resources.resources = online_resources
    freezer.tick(STATUS_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(ENTITY_ID).state == STATE_ON
