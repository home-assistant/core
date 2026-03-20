"""Helpers for Proxmox VE."""

from .const import PERM_POWER


def is_granted(
    permissions: dict[str, dict[str, int]],
    p_type: str = "vms",
    p_id: str | int | None = None,  # can be str for nodes
    permission: str = PERM_POWER,
) -> bool:
    """Validate user permissions for the given type and permission."""
    paths = [f"/{p_type}/{p_id}", f"/{p_type}", "/"]
    for path in paths:
        value = permissions.get(path, {}).get(permission)
        if value is not None:
            return value == 1
    return False
