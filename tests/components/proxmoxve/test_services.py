"""Tests for the Proxmox VE create_snapshot service."""

from __future__ import annotations

from unittest.mock import MagicMock

from freezegun import freeze_time
from proxmoxer.core import ResourceException
import pytest

from homeassistant.components.proxmoxve.const import DOMAIN, SERVICE_CREATE_SNAPSHOT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr

from . import setup_integration

from tests.common import MockConfigEntry

# Freeze to UTC noon on 2026-03-06 so dt_util.now() gives March 6 in all timezones.
_FROZEN_DATETIME_UTC = "2026-03-06T12:00:00+00:00"
_FROZEN_DATE = "2026-03-06"
_FROZEN_DATE_SNAPNAME = "2026_03_06"
_DEFAULT_DESCRIPTION = f"Snapshot triggered from Home Assistant on {_FROZEN_DATE}"


@freeze_time(_FROZEN_DATETIME_UTC)
async def test_create_snapshot_vm_default_name_uses_date(
    hass: HomeAssistant,
    mock_proxmox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that create_snapshot on a VM builds a date-based name by default."""
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
    assert call_kwargs["snapname"] == f"vm-web_{_FROZEN_DATE_SNAPNAME}"
    assert call_kwargs["description"] == _DEFAULT_DESCRIPTION
    assert "vmstate" not in call_kwargs


@freeze_time(_FROZEN_DATETIME_UTC)
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


@freeze_time(_FROZEN_DATETIME_UTC)
async def test_create_snapshot_container_default_name_uses_date(
    hass: HomeAssistant,
    mock_proxmox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that create_snapshot on a container builds a date-based name by default."""
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
    assert call_kwargs["snapname"] == f"ct-nginx_{_FROZEN_DATE_SNAPNAME}"
    assert call_kwargs["description"] == _DEFAULT_DESCRIPTION
    assert "vmstate" not in call_kwargs


@freeze_time(_FROZEN_DATETIME_UTC)
async def test_create_snapshot_version_mode(
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
    assert call_kwargs["snapname"] == "vm-web_2026_3_0"
    assert call_kwargs["description"] == _DEFAULT_DESCRIPTION


@freeze_time(_FROZEN_DATETIME_UTC)
async def test_create_snapshot_custom_vm_name(
    hass: HomeAssistant,
    mock_proxmox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that a custom vm_name replaces the device name in the snapshot name."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_CREATE_SNAPSHOT,
        {
            "target": {"entity_id": "button.vm_web_start"},
            "vm_name": "My VM",
        },
        blocking=True,
    )

    call_kwargs = mock_proxmox_client._qemu_mocks[100].snapshot.post.call_args.kwargs
    assert call_kwargs["snapname"] == f"My_VM_{_FROZEN_DATE_SNAPNAME}"


@freeze_time(_FROZEN_DATETIME_UTC)
async def test_create_snapshot_snapshot_name_override(
    hass: HomeAssistant,
    mock_proxmox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that snapshot_name is used verbatim as the full snapshot name."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_CREATE_SNAPSHOT,
        {
            "target": {"entity_id": "button.vm_web_start"},
            "snapshot_name": "before_upgrade",
        },
        blocking=True,
    )

    call_kwargs = mock_proxmox_client._qemu_mocks[100].snapshot.post.call_args.kwargs
    assert call_kwargs["snapname"] == "before_upgrade"


@freeze_time(_FROZEN_DATETIME_UTC)
async def test_create_snapshot_description_override(
    hass: HomeAssistant,
    mock_proxmox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that a custom description is passed through to Proxmox."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_CREATE_SNAPSHOT,
        {
            "target": {"entity_id": "button.vm_web_start"},
            "description": "my custom description",
        },
        blocking=True,
    )

    call_kwargs = mock_proxmox_client._qemu_mocks[100].snapshot.post.call_args.kwargs
    assert call_kwargs["description"] == "my custom description"


@freeze_time(_FROZEN_DATETIME_UTC)
async def test_create_snapshot_default_description(
    hass: HomeAssistant,
    mock_proxmox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that the default description includes the current date."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_CREATE_SNAPSHOT,
        {"target": {"entity_id": "button.vm_web_start"}},
        blocking=True,
    )

    call_kwargs = mock_proxmox_client._qemu_mocks[100].snapshot.post.call_args.kwargs
    assert call_kwargs["description"] == _DEFAULT_DESCRIPTION


@freeze_time(_FROZEN_DATETIME_UTC)
async def test_create_snapshot_conflict_appends_letter(
    hass: HomeAssistant,
    mock_proxmox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that _a is appended when the base snapshot name already exists."""
    await setup_integration(hass, mock_config_entry)

    # Make one call to initialize the lazy qemu mock for vmid 100.
    await hass.services.async_call(
        DOMAIN,
        SERVICE_CREATE_SNAPSHOT,
        {"target": {"entity_id": "button.vm_web_start"}},
        blocking=True,
    )

    base = f"vm-web_{_FROZEN_DATE_SNAPNAME}"
    mock_proxmox_client._qemu_mocks[100].snapshot.get.return_value = [{"name": base}]
    mock_proxmox_client._qemu_mocks[100].snapshot.post.reset_mock()

    await hass.services.async_call(
        DOMAIN,
        SERVICE_CREATE_SNAPSHOT,
        {"target": {"entity_id": "button.vm_web_start"}},
        blocking=True,
    )

    call_kwargs = mock_proxmox_client._qemu_mocks[100].snapshot.post.call_args.kwargs
    assert call_kwargs["snapname"] == f"{base}_a"


@freeze_time(_FROZEN_DATETIME_UTC)
async def test_create_snapshot_conflict_multiple(
    hass: HomeAssistant,
    mock_proxmox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that _b is used when both base and _a are already taken."""
    await setup_integration(hass, mock_config_entry)

    # Make one call to initialize the lazy qemu mock for vmid 100.
    await hass.services.async_call(
        DOMAIN,
        SERVICE_CREATE_SNAPSHOT,
        {"target": {"entity_id": "button.vm_web_start"}},
        blocking=True,
    )

    base = f"vm-web_{_FROZEN_DATE_SNAPNAME}"
    mock_proxmox_client._qemu_mocks[100].snapshot.get.return_value = [
        {"name": base},
        {"name": f"{base}_a"},
    ]
    mock_proxmox_client._qemu_mocks[100].snapshot.post.reset_mock()

    await hass.services.async_call(
        DOMAIN,
        SERVICE_CREATE_SNAPSHOT,
        {"target": {"entity_id": "button.vm_web_start"}},
        blocking=True,
    )

    call_kwargs = mock_proxmox_client._qemu_mocks[100].snapshot.post.call_args.kwargs
    assert call_kwargs["snapname"] == f"{base}_b"


@freeze_time(_FROZEN_DATETIME_UTC)
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
    assert call_kwargs["snapname"] == f"vm-web_{_FROZEN_DATE_SNAPNAME}"
    assert "vmstate" not in call_kwargs


@freeze_time(_FROZEN_DATETIME_UTC)
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
    assert call_kwargs["snapname"] == f"ct-nginx_{_FROZEN_DATE_SNAPNAME}"
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


@freeze_time(_FROZEN_DATETIME_UTC)
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
