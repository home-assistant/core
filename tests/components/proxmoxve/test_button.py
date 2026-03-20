"""Tests for the ProxmoxVE button platform."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from proxmoxer import AuthenticationError
from proxmoxer.core import ResourceException
import pytest
from requests.exceptions import ConnectTimeout, SSLError
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.button import SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er

from . import AUDIT_PERMISSIONS, setup_integration

from tests.common import MockConfigEntry, snapshot_platform

BUTTON_DOMAIN = "button"


@pytest.fixture(autouse=True)
def enable_all_entities(entity_registry_enabled_by_default: None) -> None:
    """Enable all entities for button tests."""


async def test_all_button_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_proxmox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Snapshot test for all ProxmoxVE button entities."""
    with patch(
        "homeassistant.components.proxmoxve.PLATFORMS",
        [Platform.BUTTON],
    ):
        await setup_integration(hass, mock_config_entry)
        await snapshot_platform(
            hass, entity_registry, snapshot, mock_config_entry.entry_id
        )


@pytest.mark.parametrize(
    ("entity_id", "command"),
    [
        ("button.pve1_restart", "reboot"),
        ("button.pve1_shutdown", "shutdown"),
    ],
)
async def test_node_buttons(
    hass: HomeAssistant,
    mock_proxmox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_id: str,
    command: str,
) -> None:
    """Test pressing a ProxmoxVE node action button triggers the correct API call."""
    await setup_integration(hass, mock_config_entry)

    method_mock = mock_proxmox_client._node_mock.status.post
    pre_calls = len(method_mock.mock_calls)

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    assert len(method_mock.mock_calls) == pre_calls + 1
    method_mock.assert_called_with(command=command)


@pytest.mark.parametrize(
    ("entity_id", "attr"),
    [
        ("button.pve1_start_all", "startall"),
        ("button.pve1_stop_all", "stopall"),
    ],
)
async def test_node_startall_stopall_buttons(
    hass: HomeAssistant,
    mock_proxmox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_id: str,
    attr: str,
) -> None:
    """Test pressing a ProxmoxVE node start all / stop all button triggers the correct API call."""
    await setup_integration(hass, mock_config_entry)

    method_mock = getattr(mock_proxmox_client._node_mock, attr).post
    pre_calls = len(method_mock.mock_calls)

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    assert len(method_mock.mock_calls) == pre_calls + 1


@pytest.mark.parametrize(
    ("entity_id", "vmid", "action"),
    [
        ("button.vm_web_start", 100, "start"),
        ("button.vm_web_stop", 100, "stop"),
        ("button.vm_web_restart", 100, "restart"),
        ("button.vm_web_hibernate", 100, "hibernate"),
        ("button.vm_web_reset", 100, "reset"),
    ],
)
async def test_vm_buttons(
    hass: HomeAssistant,
    mock_proxmox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_id: str,
    vmid: int,
    action: str,
) -> None:
    """Test pressing a ProxmoxVE VM action button triggers the correct API call."""
    await setup_integration(hass, mock_config_entry)

    mock_proxmox_client._node_mock.qemu(vmid)
    method_mock = getattr(mock_proxmox_client._qemu_mocks[vmid].status, action).post
    pre_calls = len(method_mock.mock_calls)

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    assert len(method_mock.mock_calls) == pre_calls + 1


@pytest.mark.parametrize(
    ("entity_id", "vmid", "action"),
    [
        ("button.ct_nginx_start", 200, "start"),
        ("button.ct_nginx_stop", 200, "stop"),
        ("button.ct_nginx_restart", 200, "restart"),
    ],
)
async def test_container_buttons(
    hass: HomeAssistant,
    mock_proxmox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_id: str,
    vmid: int,
    action: str,
) -> None:
    """Test pressing a ProxmoxVE container action button triggers the correct API call."""
    await setup_integration(hass, mock_config_entry)

    mock_proxmox_client._node_mock.lxc(vmid)
    method_mock = getattr(mock_proxmox_client._lxc_mocks[vmid].status, action).post
    pre_calls = len(method_mock.mock_calls)

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    assert len(method_mock.mock_calls) == pre_calls + 1


@pytest.mark.parametrize(
    ("entity_id", "exception"),
    [
        ("button.pve1_restart", AuthenticationError("auth failed")),
        ("button.pve1_restart", SSLError("ssl error")),
        ("button.pve1_restart", ConnectTimeout("timeout")),
        ("button.pve1_shutdown", ResourceException(500, "error", {})),
    ],
)
async def test_node_buttons_exceptions(
    hass: HomeAssistant,
    mock_proxmox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_id: str,
    exception: Exception,
) -> None:
    """Test that ProxmoxVE node button errors are raised as HomeAssistantError."""
    await setup_integration(hass, mock_config_entry)

    mock_proxmox_client._node_mock.status.post.side_effect = exception

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )


@pytest.mark.parametrize(
    ("entity_id", "vmid", "action", "exception"),
    [
        (
            "button.vm_web_start",
            100,
            "start",
            AuthenticationError("auth failed"),
        ),
        (
            "button.vm_web_start",
            100,
            "start",
            SSLError("ssl error"),
        ),
        (
            "button.vm_web_hibernate",
            100,
            "hibernate",
            ConnectTimeout("timeout"),
        ),
        (
            "button.vm_web_reset",
            100,
            "reset",
            ResourceException(500, "error", {}),
        ),
    ],
)
async def test_vm_buttons_exceptions(
    hass: HomeAssistant,
    mock_proxmox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_id: str,
    vmid: int,
    action: str,
    exception: Exception,
) -> None:
    """Test that ProxmoxVE VM button errors are raised as HomeAssistantError."""
    await setup_integration(hass, mock_config_entry)

    mock_proxmox_client._node_mock.qemu(vmid)
    getattr(
        mock_proxmox_client._qemu_mocks[vmid].status, action
    ).post.side_effect = exception

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )


@pytest.mark.parametrize(
    ("entity_id", "vmid", "action", "exception"),
    [
        (
            "button.ct_nginx_start",
            200,
            "start",
            AuthenticationError("auth failed"),
        ),
        (
            "button.ct_nginx_start",
            200,
            "start",
            SSLError("ssl error"),
        ),
        (
            "button.ct_nginx_restart",
            200,
            "restart",
            ConnectTimeout("timeout"),
        ),
        (
            "button.ct_nginx_stop",
            200,
            "stop",
            ResourceException(500, "error", {}),
        ),
    ],
)
async def test_container_buttons_exceptions(
    hass: HomeAssistant,
    mock_proxmox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_id: str,
    vmid: int,
    action: str,
    exception: Exception,
) -> None:
    """Test that ProxmoxVE container button errors are raised as HomeAssistantError."""
    await setup_integration(hass, mock_config_entry)

    mock_proxmox_client._node_mock.lxc(vmid)
    getattr(
        mock_proxmox_client._lxc_mocks[vmid].status, action
    ).post.side_effect = exception

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )


@pytest.mark.parametrize(
    ("entity_id", "translation_key"),
    [
        ("button.pve1_start_all", "no_permission_node_power"),
        ("button.ct_nginx_start", "no_permission_vm_lxc_power"),
        ("button.vm_web_start", "no_permission_vm_lxc_power"),
    ],
)
async def test_node_buttons_permission_denied_for_auditor_role(
    hass: HomeAssistant,
    mock_proxmox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_id: str,
    translation_key: str,
) -> None:
    """Test that buttons are raising accordingly for Auditor permissions."""
    mock_proxmox_client.access.permissions.get.return_value = AUDIT_PERMISSIONS

    await setup_integration(hass, mock_config_entry)

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
    assert exc_info.value.translation_key == translation_key


async def test_vm_buttons_denied_for_specific_vm(
    hass: HomeAssistant,
    mock_proxmox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that button only works on actual permissions."""
    await setup_integration(hass, mock_config_entry)
    mock_proxmox_client._node_mock.qemu(101)

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: "button.vm_db_start"},
            blocking=True,
        )
