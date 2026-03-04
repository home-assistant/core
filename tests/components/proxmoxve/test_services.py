"""Tests for the Proxmox VE create_snapshot service."""

from __future__ import annotations

from unittest.mock import MagicMock

from proxmoxer.core import ResourceException
import pytest

from homeassistant.components.proxmoxve.const import DOMAIN, SERVICE_CREATE_SNAPSHOT
from homeassistant.const import __version__ as HA_VERSION
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr

from . import setup_integration

from tests.common import MockConfigEntry


async def test_create_snapshot_vm_uses_core_version(
    hass: HomeAssistant,
    mock_proxmox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that create_snapshot on a VM uses the running HA version by default."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_CREATE_SNAPSHOT,
        {"target": {"entity_id": "button.vm_web_start"}},
        blocking=True,
    )

    snapshot_mock = mock_proxmox_client._qemu_mocks[100].snapshot.post
    snapshot_mock.assert_called_once()
    call_kwargs = snapshot_mock.call_args.kwargs
    sanitized = HA_VERSION.replace(".", "_")
    assert call_kwargs["snapname"] == f"Home_Assistant_{sanitized}"
    assert call_kwargs["description"] == HA_VERSION
    assert call_kwargs["vmstate"] == 0


async def test_create_snapshot_vm_include_ram(
    hass: HomeAssistant,
    mock_proxmox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that include_ram=True passes vmstate=1 to the Proxmox API."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_CREATE_SNAPSHOT,
        {"target": {"entity_id": "button.vm_web_start"}, "include_ram": True},
        blocking=True,
    )

    call_kwargs = mock_proxmox_client._qemu_mocks[100].snapshot.post.call_args.kwargs
    assert call_kwargs["vmstate"] == 1


async def test_create_snapshot_container_uses_core_version(
    hass: HomeAssistant,
    mock_proxmox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that create_snapshot on a container uses the running HA version by default."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_CREATE_SNAPSHOT,
        {"target": {"entity_id": "button.ct_nginx_start"}},
        blocking=True,
    )

    snapshot_mock = mock_proxmox_client._lxc_mocks[200].snapshot.post
    snapshot_mock.assert_called_once()
    call_kwargs = snapshot_mock.call_args.kwargs
    sanitized = HA_VERSION.replace(".", "_")
    assert call_kwargs["snapname"] == f"Home_Assistant_{sanitized}"
    assert call_kwargs["description"] == HA_VERSION
    # LXC snapshots do not accept vmstate
    assert "vmstate" not in call_kwargs


async def test_create_snapshot_vm_uses_version_entity(
    hass: HomeAssistant,
    mock_proxmox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that create_snapshot uses version_entity state when provided."""
    await setup_integration(hass, mock_config_entry)

    hass.states.async_set("sensor.local_version", "2026.3.0")

    await hass.services.async_call(
        DOMAIN,
        SERVICE_CREATE_SNAPSHOT,
        {
            "target": {"entity_id": "button.vm_web_start"},
            "version_entity": "sensor.local_version",
        },
        blocking=True,
    )

    snapshot_mock = mock_proxmox_client._qemu_mocks[100].snapshot.post
    snapshot_mock.assert_called_once()
    call_kwargs = snapshot_mock.call_args.kwargs
    assert call_kwargs["snapname"] == "Home_Assistant_2026_3_0"
    assert call_kwargs["description"] == "2026.3.0"


async def test_create_snapshot_by_vm_device_id(
    hass: HomeAssistant,
    mock_proxmox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test create_snapshot resolves correctly when targeting a VM device directly."""
    await setup_integration(hass, mock_config_entry)

    dev_reg = dr.async_get(hass)
    vm_device = next(
        (
            d
            for d in dr.async_entries_for_config_entry(
                dev_reg, mock_config_entry.entry_id
            )
            if any(
                ident[0] == DOMAIN and "_vm_" in str(ident[1])
                for ident in d.identifiers
            )
        ),
        None,
    )
    assert vm_device is not None

    await hass.services.async_call(
        DOMAIN,
        SERVICE_CREATE_SNAPSHOT,
        {"target": {"device_id": vm_device.id}},
        blocking=True,
    )

    snapshot_mock = mock_proxmox_client._qemu_mocks[100].snapshot.post
    snapshot_mock.assert_called_once()
    call_kwargs = snapshot_mock.call_args.kwargs
    sanitized = HA_VERSION.replace(".", "_")
    assert call_kwargs["snapname"] == f"Home_Assistant_{sanitized}"
    assert call_kwargs["vmstate"] == 0


async def test_create_snapshot_by_container_device_id(
    hass: HomeAssistant,
    mock_proxmox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test create_snapshot resolves correctly when targeting a container device."""
    await setup_integration(hass, mock_config_entry)

    dev_reg = dr.async_get(hass)
    container_device = next(
        (
            d
            for d in dr.async_entries_for_config_entry(
                dev_reg, mock_config_entry.entry_id
            )
            if any(
                ident[0] == DOMAIN and "_container_" in str(ident[1])
                for ident in d.identifiers
            )
        ),
        None,
    )
    assert container_device is not None

    await hass.services.async_call(
        DOMAIN,
        SERVICE_CREATE_SNAPSHOT,
        {"target": {"device_id": container_device.id}},
        blocking=True,
    )

    snapshot_mock = mock_proxmox_client._lxc_mocks[200].snapshot.post
    snapshot_mock.assert_called_once()
    call_kwargs = snapshot_mock.call_args.kwargs
    sanitized = HA_VERSION.replace(".", "_")
    assert call_kwargs["snapname"] == f"Home_Assistant_{sanitized}"
    assert "vmstate" not in call_kwargs


async def test_create_snapshot_invalid_target_single(
    hass: HomeAssistant,
    mock_proxmox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that targeting more than one entity raises ServiceValidationError."""
    await setup_integration(hass, mock_config_entry)

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_CREATE_SNAPSHOT,
            {
                "target": {
                    "entity_id": [
                        "button.vm_web_start",
                        "button.vm_web_stop",
                    ]
                }
            },
            blocking=True,
        )

    assert exc_info.value.translation_key == "invalid_target_single"


async def test_create_snapshot_version_entity_unavailable(
    hass: HomeAssistant,
    mock_proxmox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that a missing version_entity raises ServiceValidationError."""
    await setup_integration(hass, mock_config_entry)

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_CREATE_SNAPSHOT,
            {
                "target": {"entity_id": "button.vm_web_start"},
                "version_entity": "sensor.nonexistent",
            },
            blocking=True,
        )

    assert exc_info.value.translation_key == "version_entity_unavailable"


async def test_create_snapshot_api_error(
    hass: HomeAssistant,
    mock_proxmox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that a Proxmox API failure raises HomeAssistantError."""
    await setup_integration(hass, mock_config_entry)

    # Trigger lazy initialisation of the qemu mock for vmid 100.
    await hass.services.async_call(
        DOMAIN,
        SERVICE_CREATE_SNAPSHOT,
        {"target": {"entity_id": "button.vm_web_start"}},
        blocking=True,
    )
    mock_proxmox_client._qemu_mocks[100].snapshot.post.side_effect = ResourceException(
        500, "Internal error", ""
    )

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_CREATE_SNAPSHOT,
            {"target": {"entity_id": "button.vm_web_start"}},
            blocking=True,
        )

    assert exc_info.value.translation_key == "snapshot_failed"
