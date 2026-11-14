"""Helpers for Proxmox VE."""

from dataclasses import dataclass

from aioproxmox.model.pve import NodeAptUpdateProperty


@dataclass(frozen=True)
class ProxmoxUpdateInfo:
    """Describes Proxmox VE update information."""

    latest_version: str | None = None
    latest_version_id: str | None = None
    total_updates: int = 0
    proxmox_updates: int = 0
    other_updates: int = 0


def is_proxmox_package(update: NodeAptUpdateProperty) -> bool:
    """Indicate if the given update is related to Proxmox VE."""
    return (
        update.package.startswith(("pve-", "libpve-"))
        or "proxmox" in update.origin.lower()
        or "proxmox" in update.title.lower()
    )


def update_version(
    current_version: str,
    updates: list[NodeAptUpdateProperty],
) -> ProxmoxUpdateInfo:
    """Return the updated version based on the current version and updates."""

    count = len(updates)
    pve_count = sum(is_proxmox_package(u) for u in updates)
    other_count = count - pve_count
    pve_manager_update = next(
        (update for update in updates if update.package == "pve-manager"),
        None,
    )
    latest = (
        pve_manager_update.version.split("-")[0]
        if pve_manager_update
        else current_version
    )
    return ProxmoxUpdateInfo(
        latest_version=latest,
        latest_version_id=f"{latest}-p{pve_count}-d{other_count}"
        if count
        else current_version,
        total_updates=count,
        proxmox_updates=pve_count,
        other_updates=other_count,
    )
