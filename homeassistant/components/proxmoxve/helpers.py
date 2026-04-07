"""Helpers for Proxmox VE."""

from dataclasses import dataclass
from typing import Any

from packaging.version import parse as parse_version

from .const import ProxmoxPermission


@dataclass(frozen=True)
class ProxmoxUpdateInfo:
    """Describes Proxmox VE update information."""

    latest_version: str
    latest_version_id: str
    total_updates: int
    proxmox_updates: int
    other_updates: int


def is_granted(
    permissions: dict[str, dict[str, int]],
    p_type: str = "vms",
    p_id: str | int | None = None,  # can be str for nodes
    permission: ProxmoxPermission = ProxmoxPermission.POWER,
) -> bool:
    """Validate user permissions for the given type and permission."""
    paths = [f"/{p_type}/{p_id}", f"/{p_type}", "/"]
    for path in paths:
        value = permissions.get(path, {}).get(permission)
        if value is not None:
            return value == 1
    return False


def is_proxmox_package(update: dict[str, Any]) -> bool:
    """Indicate if the given update is related to Proxmox VE."""
    package = update.get("Package", "")
    origin = update.get("Origin", "")
    title = update.get("Title", "")
    return (
        package.startswith(("pve-", "libpve-"))
        or "proxmox" in origin.lower()
        or "proxmox" in title.lower()
    )


def latest_version(versions: list[str]) -> str:
    """Return the latest version from a list of version strings."""
    # Fix proxmox -pve1 style suffixes
    safe_versions = [v.split("-")[0] for v in versions]
    return max(safe_versions, key=parse_version)


def update_version(
    current_version: str,
    updates: list[dict[str, Any]],
) -> ProxmoxUpdateInfo:
    """Return the updated version based on the current version and updates."""

    count = len(updates)
    pve_count = sum(is_proxmox_package(u) for u in updates)
    other_count = len(updates) - pve_count
    versions = [current_version] + [
        u["Version"] for u in updates if is_proxmox_package(u)
    ]

    latest = latest_version(versions) if pve_count else current_version
    return ProxmoxUpdateInfo(
        latest_version=latest if count else current_version,
        latest_version_id=f"{latest}-p{pve_count}-d{other_count}"
        if count
        else current_version,
        total_updates=count,
        proxmox_updates=pve_count,
        other_updates=other_count,
    )
