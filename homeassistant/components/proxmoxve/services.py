"""Proxmox VE service handlers."""

from __future__ import annotations

from enum import StrEnum
import logging
import re
from typing import cast

from proxmoxer import AuthenticationError
from proxmoxer.core import ResourceException
import requests
from requests.exceptions import ConnectTimeout, ReadTimeout, SSLError
import voluptuous as vol

from homeassistant.const import (
    ATTR_AREA_ID,
    ATTR_DEVICE_ID,
    ATTR_ENTITY_ID,
    ATTR_FLOOR_ID,
    ATTR_LABEL_ID,
    ENTITY_MATCH_NONE,
    __version__ as HA_VERSION,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.target import (
    TargetSelection,
    async_extract_referenced_entity_ids,
)

from .const import DOMAIN, SERVICE_CREATE_SNAPSHOT
from .coordinator import ProxmoxConfigEntry, ProxmoxCoordinator

_LOGGER = logging.getLogger(__name__)

# Proxmox snapshot names only allow alphanumeric characters and hyphens/underscores.
# Dots are NOT valid despite appearing in Proxmox docs — the API rejects them.
_SNAPSHOT_NAME_RE = re.compile(r"[^a-zA-Z0-9_-]+")

CREATE_SNAPSHOT_SCHEMA = vol.Schema(
    {
        vol.Optional("target"): cv.TARGET_SERVICE_FIELDS,
        # Core merges target fields into service_data when called from Actions UI.
        vol.Optional(ATTR_ENTITY_ID): cv.comp_entity_ids_or_uuids,
        vol.Optional(ATTR_DEVICE_ID): vol.Any(
            ENTITY_MATCH_NONE,
            vol.All(cv.ensure_list, [str]),
        ),
        vol.Optional(ATTR_AREA_ID): vol.Any(
            ENTITY_MATCH_NONE,
            vol.All(cv.ensure_list, [str]),
        ),
        vol.Optional(ATTR_FLOOR_ID): vol.Any(
            ENTITY_MATCH_NONE,
            vol.All(cv.ensure_list, [str]),
        ),
        vol.Optional(ATTR_LABEL_ID): vol.Any(
            ENTITY_MATCH_NONE,
            vol.All(cv.ensure_list, [str]),
        ),
        vol.Optional("version_entity"): cv.entity_id,
        vol.Optional("include_ram", default=False): cv.boolean,
    }
)


class _ResourceType(StrEnum):
    """Proxmox resource types that support snapshots."""

    VM = "vm"
    CONTAINER = "container"


def _sanitize_snapshot_version(version: str) -> str:
    """Replace characters invalid in a Proxmox snapshot name with underscores."""
    return _SNAPSHOT_NAME_RE.sub("_", version.strip())


def _parse_device_identifier(
    hass: HomeAssistant,
    device: dr.DeviceEntry,
    label: str,
) -> tuple[ProxmoxConfigEntry, str, int, _ResourceType]:
    """Return config entry, node name, vmid, and resource type for a Proxmox device.

    Inspects the device's domain-specific identifier to determine whether it is
    a VM (``{entry_id}_vm_{vmid}``) or LXC container
    (``{entry_id}_container_{vmid}``), then resolves the parent node device.
    """
    raw_identifier = next(
        (ident[1] for ident in device.identifiers if ident[0] == DOMAIN),
        None,
    )
    if raw_identifier is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_target_entity",
            translation_placeholders={"entity_id": label},
        )

    if "_vm_" in raw_identifier:
        resource_type = _ResourceType.VM
        entry_id, vmid_str = raw_identifier.rsplit("_vm_", 1)
    elif "_container_" in raw_identifier:
        resource_type = _ResourceType.CONTAINER
        entry_id, vmid_str = raw_identifier.rsplit("_container_", 1)
    else:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_target_not_vm_or_container",
            translation_placeholders={"entity_id": label},
        )

    try:
        vmid = int(vmid_str)
    except ValueError:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_target_entity",
            translation_placeholders={"entity_id": label},
        ) from None

    entry = hass.config_entries.async_get_entry(entry_id)
    if (
        entry is None
        or entry.domain != DOMAIN
        or not isinstance(entry.runtime_data, ProxmoxCoordinator)
    ):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_target_entity",
            translation_placeholders={"entity_id": label},
        )

    # The parent device of every VM/container device is the Proxmox node device,
    # and its name is the node name used in Proxmox API calls.
    if device.via_device_id is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_target_not_vm_or_container",
            translation_placeholders={"entity_id": label},
        )

    dev_reg = dr.async_get(hass)
    node_device = dev_reg.async_get(device.via_device_id)
    if node_device is None or node_device.name is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_target_entity",
            translation_placeholders={"entity_id": label},
        )

    return cast(ProxmoxConfigEntry, entry), node_device.name, vmid, resource_type


def _resolve_from_device(
    hass: HomeAssistant,
    device_id: str,
) -> tuple[ProxmoxConfigEntry, str, int, _ResourceType]:
    """Resolve config entry, node name, vmid, and resource type from a device ID."""
    dev_reg = dr.async_get(hass)
    device = dev_reg.async_get(device_id)
    if device is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_target_entity",
            translation_placeholders={"entity_id": device_id},
        )
    return _parse_device_identifier(hass, device, device_id)


def _resolve_from_entity(
    hass: HomeAssistant,
    entity_id: str,
) -> tuple[ProxmoxConfigEntry, str, int, _ResourceType]:
    """Resolve config entry, node name, vmid, and resource type from an entity ID."""
    ent_reg = er.async_get(hass)
    entity_entry = ent_reg.async_get(entity_id)
    if entity_entry is None or entity_entry.device_id is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_target_entity",
            translation_placeholders={"entity_id": entity_id},
        )

    dev_reg = dr.async_get(hass)
    device = dev_reg.async_get(entity_entry.device_id)
    if device is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_target_entity",
            translation_placeholders={"entity_id": entity_id},
        )
    return _parse_device_identifier(hass, device, entity_id)


def _create_snapshot_blocking(
    coordinator: ProxmoxCoordinator,
    node: str,
    vmid: int,
    resource_type: _ResourceType,
    snapname: str,
    description: str,
    include_ram: bool,
) -> None:
    """Call the Proxmox snapshot API synchronously.

    VMs support saving RAM state (vmstate); LXC containers do not.
    """
    if resource_type is _ResourceType.VM:
        coordinator.proxmox.nodes(node).qemu(vmid).snapshot.post(
            snapname=snapname,
            description=description,
            vmstate=1 if include_ram else 0,
        )
    else:
        coordinator.proxmox.nodes(node).lxc(vmid).snapshot.post(
            snapname=snapname,
            description=description,
        )


def _build_target(data: dict) -> dict:
    """Merge top-level target fields and the nested ``target`` key into one dict.

    Home Assistant's Actions UI merges target fields (entity_id, device_id,
    area_id, floor_id, label_id) directly into service_data rather than nesting
    them under a ``target`` key.  This function handles both shapes.
    """
    target = dict(data.get("target") or {})
    for key in (
        ATTR_ENTITY_ID,
        ATTR_DEVICE_ID,
        ATTR_AREA_ID,
        ATTR_FLOOR_ID,
        ATTR_LABEL_ID,
    ):
        if key in data and data[key] is not None:
            target[key] = data[key]
    return target


async def _call_snapshot(
    hass: HomeAssistant,
    entry: ProxmoxConfigEntry,
    node_name: str,
    vmid: int,
    resource_type: _ResourceType,
    snapname: str,
    description: str,
    include_ram: bool,
) -> None:
    """Run the snapshot API call and translate Proxmox exceptions to HA errors."""
    coordinator: ProxmoxCoordinator = entry.runtime_data
    try:
        await hass.async_add_executor_job(
            _create_snapshot_blocking,
            coordinator,
            node_name,
            vmid,
            resource_type,
            snapname,
            description,
            include_ram,
        )
    except AuthenticationError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="cannot_connect_no_details",
        ) from err
    except SSLError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="invalid_auth_no_details",
        ) from err
    except (ConnectTimeout, ReadTimeout) as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="timeout_connect_no_details",
        ) from err
    except (ResourceException, requests.exceptions.ConnectionError) as err:
        _LOGGER.warning(
            "Snapshot failed for %s %s/%s: %s",
            resource_type,
            node_name,
            vmid,
            err,
        )
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="snapshot_failed",
        ) from err


async def async_create_snapshot(call: ServiceCall) -> None:
    """Create a snapshot named ``Home_Assistant_{version}`` on a VM or container.

    The snapshot name is derived from the running Home Assistant version by
    default, or from an optional sensor entity when ``version_entity`` is set.
    Snapshot creation is supported on both QEMU VMs and LXC containers.
    """
    hass = call.hass
    target = _build_target(call.data)
    version_entity_id: str | None = call.data.get("version_entity")

    if version_entity_id:
        state = hass.states.get(version_entity_id)
        if state is None or state.state in ("unknown", "unavailable", ""):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="version_entity_unavailable",
                translation_placeholders={"entity_id": version_entity_id},
            )
        version = state.state.strip()
    else:
        version = HA_VERSION

    snapname = f"Home_Assistant_{_sanitize_snapshot_version(version)}"
    description = version
    include_ram: bool = call.data["include_ram"]

    # Prefer device targeting when a single device_id is provided, as it
    # unambiguously identifies the VM or container.
    device_ids_raw = target.get(ATTR_DEVICE_ID)
    if device_ids_raw is not None and device_ids_raw != ENTITY_MATCH_NONE:
        device_ids = [
            did for did in cv.ensure_list(device_ids_raw) if did != ENTITY_MATCH_NONE
        ]
        if len(device_ids) > 1:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_target_single",
            )
        if len(device_ids) == 1:
            entry, node_name, vmid, resource_type = _resolve_from_device(
                hass, device_ids[0]
            )
            await _call_snapshot(
                hass,
                entry,
                node_name,
                vmid,
                resource_type,
                snapname,
                description,
                include_ram,
            )
            _LOGGER.debug(
                "Created snapshot %s on %s %s/%s",
                snapname,
                resource_type,
                node_name,
                vmid,
            )
            return

    # Fall back to entity targeting; exactly one entity must be resolved.
    ref = async_extract_referenced_entity_ids(
        hass, TargetSelection(target), expand_group=True
    )
    all_entities = ref.referenced | ref.indirectly_referenced
    if len(all_entities) != 1:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_target_single",
        )

    entity_id = next(iter(all_entities))
    entry, node_name, vmid, resource_type = _resolve_from_entity(hass, entity_id)
    await _call_snapshot(
        hass, entry, node_name, vmid, resource_type, snapname, description, include_ram
    )
    _LOGGER.debug(
        "Created snapshot %s on %s %s/%s",
        snapname,
        resource_type,
        node_name,
        vmid,
    )


def async_setup_services(hass: HomeAssistant) -> None:
    """Register Proxmox VE services."""
    hass.services.async_register(
        DOMAIN,
        SERVICE_CREATE_SNAPSHOT,
        async_create_snapshot,
        schema=CREATE_SNAPSHOT_SCHEMA,
    )


def async_unload_services(hass: HomeAssistant) -> None:
    """Unload Proxmox VE services."""
    hass.services.async_remove(DOMAIN, SERVICE_CREATE_SNAPSHOT)
