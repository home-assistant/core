"""Tests for the Proxmox VE update platform."""

from unittest.mock import MagicMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.proxmoxve.helpers import update_version
from homeassistant.const import STATE_OFF, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import AUDIT_PERMISSIONS, MERGED_PERMISSIONS, setup_integration

from tests.common import MockConfigEntry, snapshot_platform
from tests.typing import WebSocketGenerator

ENTITY_ID = "update.pve1_software_update"


@pytest.mark.parametrize(
    ("updates", "expected_version"),
    [
        pytest.param(
            [{"Package": "ceph-common", "Version": "19.2.6", "Origin": "Proxmox"}],
            "9.2.3",
            id="higher-ceph-version-is-not-pve-version",
        ),
        pytest.param(
            [{"Package": "libpve-storage-perl", "Version": "1+16.1+2+pmx1"}],
            "9.2.3",
            id="debian-package-version-is-not-parsed",
        ),
        pytest.param(
            [
                {"Package": "ceph-common", "Version": "19.2.6", "Origin": "Proxmox"},
                {"Package": "pve-manager", "Version": "9.2.21-1"},
            ],
            "9.2.21",
            id="pve-manager-version-is-used",
        ),
    ],
)
def test_update_version_uses_pve_manager(
    updates: list[dict[str, str]], expected_version: str
) -> None:
    """The PVE version must come only from pve-manager."""
    info = update_version("9.2.3", updates)

    assert info.latest_version == expected_version
    assert info.total_updates == len(updates)


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_proxmox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    # Ensure Sys.Modify permissions to ensure update status can be determined
    mock_proxmox_client.access.permissions.get.return_value = MERGED_PERMISSIONS
    with patch(
        "homeassistant.components.proxmoxve.PLATFORMS",
        [Platform.UPDATE],
    ):
        await setup_integration(hass, mock_config_entry)
        await snapshot_platform(
            hass, entity_registry, snapshot, mock_config_entry.entry_id
        )


async def test_update_entities_ignored(
    hass: HomeAssistant,
    mock_proxmox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that updates entities are not created with only auditor permissions."""
    mock_proxmox_client.access.permissions.get.return_value = AUDIT_PERMISSIONS

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
    mock_proxmox_client.access.permissions.get.return_value = MERGED_PERMISSIONS

    with patch(
        "homeassistant.components.proxmoxve.PLATFORMS",
        [Platform.UPDATE],
    ):
        await setup_integration(hass, mock_config_entry)

    assert hass.states.get(ENTITY_ID).state is not None

    mock_proxmox_client.access.permissions.get.return_value = AUDIT_PERMISSIONS

    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_UNAVAILABLE


async def test_update_up_to_date(
    hass: HomeAssistant,
    mock_proxmox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that updates are up to date when no updates are pending."""
    mock_proxmox_client.access.permissions.get.return_value = MERGED_PERMISSIONS
    mock_proxmox_client.nodes.return_value.apt.update.get.return_value = []

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
    mock_proxmox_client.access.permissions.get.return_value = MERGED_PERMISSIONS

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
    assert "5 package" in result["result"]
