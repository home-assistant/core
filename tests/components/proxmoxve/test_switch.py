"""Tests for the Proxmox VE switch platform."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from proxmoxer import AuthenticationError
from proxmoxer.core import ResourceException
import pytest
from requests.exceptions import ConnectTimeout, SSLError
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture(autouse=True)
def enable_all_entities(entity_registry_enabled_by_default: None) -> None:
    """Make sure all entities are enabled."""


@pytest.mark.usefixtures("mock_proxmox_client")
async def test_all_switch_entities_snapshot(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Snapshot test for all Proxmox VE switch entities."""
    with patch(
        "homeassistant.components.proxmoxve.PLATFORMS",
        [Platform.SWITCH],
    ):
        await setup_integration(hass, mock_config_entry)
        await snapshot_platform(
            hass, entity_registry, snapshot, mock_config_entry.entry_id
        )


@pytest.mark.parametrize(
    ("entity_id", "resource_type"),
    [
        ("switch.vm_web_virtual_machine", "qemu"),
        ("switch.ct_nginx_container", "lxc"),
    ],
    ids=["vm", "container"],
)
@pytest.mark.parametrize(
    ("service_call", "action"),
    [
        (SERVICE_TURN_ON, "start"),
        (SERVICE_TURN_OFF, "stop"),
    ],
)
async def test_switch_turn_on_off(
    hass: HomeAssistant,
    mock_proxmox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_id: str,
    resource_type: str,
    service_call: str,
    action: str,
) -> None:
    """Test turning Proxmox VM and container switches on and off."""
    await setup_integration(hass, mock_config_entry)

    resource_mock = MagicMock()
    node_mock = mock_proxmox_client._node_mock
    getattr(node_mock, resource_type).side_effect = None
    getattr(node_mock, resource_type).return_value = resource_mock

    await hass.services.async_call(
        SWITCH_DOMAIN,
        service_call,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    getattr(resource_mock.status, action).post.assert_called_once()


@pytest.mark.parametrize(
    ("entity_id", "resource_type"),
    [
        ("switch.vm_web_virtual_machine", "qemu"),
        ("switch.ct_nginx_container", "lxc"),
    ],
    ids=["vm", "container"],
)
@pytest.mark.parametrize(
    ("service_call", "action"),
    [
        (SERVICE_TURN_ON, "start"),
        (SERVICE_TURN_OFF, "stop"),
    ],
)
@pytest.mark.parametrize(
    "raise_exception",
    [
        AuthenticationError("Invalid credentials"),
        SSLError("SSL handshake failed"),
        ConnectTimeout("Connection timed out"),
        ResourceException(500, "Internal Server Error", "error details"),
    ],
    ids=["auth_error", "ssl_error", "connect_timeout", "resource_exception"],
)
async def test_switch_exceptions(
    hass: HomeAssistant,
    mock_proxmox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_id: str,
    resource_type: str,
    service_call: str,
    action: str,
    raise_exception: Exception,
) -> None:
    """Test that Proxmox API errors are raised as HomeAssistantError."""
    await setup_integration(hass, mock_config_entry)

    resource_mock = MagicMock()
    node_mock = mock_proxmox_client._node_mock
    getattr(node_mock, resource_type).side_effect = None
    getattr(node_mock, resource_type).return_value = resource_mock
    getattr(resource_mock.status, action).post.side_effect = raise_exception

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            service_call,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
