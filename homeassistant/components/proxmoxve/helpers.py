"""Helpers for Proxmox VE."""

from .const import PERM_POWER


def is_granted(
    permissions: dict[str, dict[str, int]],
    p_type: str = "vms",
    permission: str = PERM_POWER,
) -> bool:
    """Validate user permissions for the given type and permission."""
    path = f"/{p_type}"
    return permissions.get(path, {}).get(permission) == 1
