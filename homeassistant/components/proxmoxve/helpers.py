"""Helpers for Proxmox VE."""

from .const import PERM_POWER


def is_granted(
    permissions: dict[str, dict[str, int]],
    p_type: str = "vms",
    p_id: str | int | None = None,  # can be str for nodes
    permission: str = PERM_POWER,
) -> bool:
    """Validate user permissions for the given type and permission."""
    # Most specific permission matching
    if p_id is not None:
        path = f"/{p_type}/{p_id}"
        if permission in permissions.get(path, {}):
            return permissions.get(path, {}).get(permission) == 1
    # Type specific permission
    path = f"/{p_type}"
    if permission in permissions.get(path, {}):
        return permissions.get(path, {}).get(permission) == 1
    # Global permission
    return permissions.get("/", {}).get(permission) == 1
