"""Proxmox VE service handlers."""

from __future__ import annotations

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
from homeassistant.util import dt as dt_util

from .const import DOMAIN, SERVICE_CREATE_SNAPSHOT, ResourceType
from .coordinator import ProxmoxConfigEntry, ProxmoxCoordinator

_LOGGER = logging.getLogger(__name__)

# Proxmox snapshot names only allow alphanumeric characters and hyphens/underscores.
# Dots are NOT valid despite appearing in Proxmox docs — the API rejects them.
_SNAPSHOT_NAME_RE = re.compile(r"[^a-zA-Z0-9_-]+")

# Maximum length for the base snapshot name before conflict suffix (_a … _z, 2 chars).
_SNAPNAME_MAX_BASE_LEN = 37

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
        vol.Optional("vm_name", default=""): vol.All(cv.string, str.strip),
        vol.Optional("snapshot_name", default=""): vol.All(cv.string, str.strip),
        vol.Optional("description", default=""): vol.All(cv.string, str.strip),
        vol.Optional("version_entity"): cv.entity_id,
        vol.Optional("include_ram", default=False): cv.boolean,
    }
)


def _build_base_snapname(
    snapshot_name_input: str,
    vm_name_input: str,
    device_name: str,
    vmid: int,
    version: str | None,
    today: str,
) -> str:
    """Build the base snapshot name (before conflict-resolution suffix).

    Priority for the name source:
    1. User-supplied ``snapshot_name`` — used as the base name (sanitized and may be truncated).
    2. User-supplied ``vm_name`` combined with version or date.
    3. Device registry name combined with version or date.
    4. VM ID as string combined with version or date.

    The result is truncated to ``_SNAPNAME_MAX_BASE_LEN`` characters to leave
    room for the ``_a`` … ``_z`` conflict suffix.
    """
    if snapshot_name_input:
        base = _SNAPSHOT_NAME_RE.sub("_", snapshot_name_input.strip())
    else:
        vm_part = _SNAPSHOT_NAME_RE.sub(
            "_", (vm_name_input or device_name or str(vmid)).strip()
        )
        suffix = (
            _SNAPSHOT_NAME_RE.sub("_", version.strip())
            if version is not None
            else today
        )
        base = f"{vm_part}_{suffix}"

    if len(base) > _SNAPNAME_MAX_BASE_LEN:
        base = base[:_SNAPNAME_MAX_BASE_LEN].rstrip("_")

    return base


def _parse_device_identifier(
    hass: HomeAssistant,
    device: dr.DeviceEntry,
    label: str,
) -> tuple[ProxmoxConfigEntry, str, int, ResourceType, str]:
    """Return config entry, node name, vmid, resource type, and device name.

    Inspects the device's domain-specific identifier to determine whether it is
    a VM (``{entry_id}_vm_{vmid}``) or LXC container
    (``{entry_id}_container_{vmid}``), then resolves the parent node device.
    The device name (fifth element) is the VM or container name from the registry.
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
        resource_type = ResourceType.VM
        entry_id, vmid_str = raw_identifier.rsplit("_vm_", 1)
    elif "_container_" in raw_identifier:
        resource_type = ResourceType.CONTAINER
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

    return (
        cast(ProxmoxConfigEntry, entry),
        node_device.name,
        vmid,
        resource_type,
        device.name or "",
    )


def _resolve_from_device(
    hass: HomeAssistant,
    device_id: str,
) -> tuple[ProxmoxConfigEntry, str, int, ResourceType, str]:
    """Resolve config entry, node name, vmid, resource type, and device name from a device ID."""
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
) -> tuple[ProxmoxConfigEntry, str, int, ResourceType, str]:
    """Resolve config entry, node name, vmid, resource type, and device name from an entity ID."""
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
    resource_type: ResourceType,
    base_snapname: str,
    description: str,
    include_ram: bool,
) -> str:
    """Call the Proxmox snapshot API synchronously with conflict resolution.

    Lists existing snapshots and appends ``_a``, ``_b``, … if the base name is
    already taken.  VMs support saving RAM state (vmstate); LXC containers do
    not.  Returns the final snapshot name that was created.
    """
    if resource_type is ResourceType.VM:
        existing = coordinator.proxmox.nodes(node).qemu(vmid).snapshot.get()
    else:
        existing = coordinator.proxmox.nodes(node).lxc(vmid).snapshot.get()

    existing_names = {s["name"] for s in existing if s.get("name") != "current"}

    # Try the base name first, then append _a … _z until a free slot is found.
    snapname = base_snapname
    for letter in "abcdefghijklmnopqrstuvwxyz":
        if snapname not in existing_names:
            break
        snapname = f"{base_snapname}_{letter}"

    if snapname in existing_names:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="snapshot_name_conflict",
            translation_placeholders={"base_name": base_snapname},
        )

    if resource_type is ResourceType.VM:
        _LOGGER.debug(
            "Creating VM snapshot %s on %s/%s (include_ram=%s)",
            snapname,
            node,
            vmid,
            include_ram,
        )
        kwargs: dict[str, object] = {
            "snapname": snapname,
            "description": description,
        }
        if include_ram:
            kwargs["vmstate"] = 1
        coordinator.proxmox.nodes(node).qemu(vmid).snapshot.post(**kwargs)
    else:
        coordinator.proxmox.nodes(node).lxc(vmid).snapshot.post(
            snapname=snapname,
            description=description,
        )

    return snapname


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
    resource_type: ResourceType,
    base_snapname: str,
    description: str,
    include_ram: bool,
) -> str:
    """Run the snapshot API call and translate Proxmox exceptions to HA errors.

    Returns the final snapshot name used after conflict resolution.
    """
    coordinator: ProxmoxCoordinator = entry.runtime_data
    try:
        return await hass.async_add_executor_job(
            _create_snapshot_blocking,
            coordinator,
            node_name,
            vmid,
            resource_type,
            base_snapname,
            description,
            include_ram,
        )
    except AuthenticationError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="invalid_auth_no_details",
        ) from err
    except SSLError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="cannot_connect_no_details",
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
    """Create a snapshot on a VM or LXC container.

    The snapshot name defaults to ``{vm_name}_{YYYY_MM_DD}``, derived from the
    device registry name and the current date.  When ``version_entity`` is set,
    the date is replaced by the version string from that entity.  If the
    generated name conflicts with an existing snapshot, a letter suffix
    (``_a``, ``_b``, …) is appended automatically.
    """
    hass = call.hass
    target = _build_target(call.data)
    version_entity_id: str | None = call.data.get("version_entity")
    vm_name_input: str = call.data["vm_name"]
    snapshot_name_input: str = call.data["snapshot_name"]
    description_input: str = call.data["description"]
    include_ram: bool = call.data["include_ram"]

    version: str | None = None
    if version_entity_id:
        state = hass.states.get(version_entity_id)
        if state is None or state.state in ("unknown", "unavailable", ""):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="version_entity_unavailable",
                translation_placeholders={"entity_id": version_entity_id},
            )
        version = state.state.strip()

    now = dt_util.now()
    today = now.strftime("%Y_%m_%d")
    description = (
        description_input
        or f"Snapshot triggered from Home Assistant on {now.strftime('%Y-%m-%d')}"
    )

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
            entry, node_name, vmid, resource_type, device_name = _resolve_from_device(
                hass, device_ids[0]
            )
            base_snapname = _build_base_snapname(
                snapshot_name_input,
                vm_name_input,
                device_name,
                vmid,
                version,
                today,
            )
            snapname = await _call_snapshot(
                hass,
                entry,
                node_name,
                vmid,
                resource_type,
                base_snapname,
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
    entry, node_name, vmid, resource_type, device_name = _resolve_from_entity(
        hass, entity_id
    )
    base_snapname = _build_base_snapname(
        snapshot_name_input,
        vm_name_input,
        device_name,
        vmid,
        version,
        today,
    )
    snapname = await _call_snapshot(
        hass,
        entry,
        node_name,
        vmid,
        resource_type,
        base_snapname,
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
