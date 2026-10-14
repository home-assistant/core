"""Tests for Proxmox VE helpers."""

import pytest

from homeassistant.components.proxmoxve.const import ProxmoxPermission
from homeassistant.components.proxmoxve.helpers import is_granted


@pytest.mark.parametrize(
    ("permissions", "expected"),
    [
        pytest.param(
            {"/vms/100": {ProxmoxPermission.POWER: 0}}, True, id="exact_no_propagate"
        ),
        pytest.param(
            {"/vms/100": {ProxmoxPermission.POWER: 1}}, True, id="exact_propagate"
        ),
        pytest.param(
            {
                "/vms/100": {ProxmoxPermission.VMAUDIT: 1},
                "/vms": {ProxmoxPermission.POWER: 1},
            },
            False,
            id="exact_overrides_parent",
        ),
        pytest.param(
            {"/vms": {ProxmoxPermission.POWER: 1}}, True, id="parent_propagate"
        ),
        pytest.param(
            {"/vms": {ProxmoxPermission.POWER: 0}}, False, id="parent_no_propagate"
        ),
        pytest.param(
            {"/": {ProxmoxPermission.POWER: 1}}, False, id="root_not_consulted"
        ),
        pytest.param({}, False, id="no_permissions"),
    ],
)
def test_is_granted(permissions: dict[str, dict[str, int]], expected: bool) -> None:
    """Test permission resolution against the Proxmox VE permissions tree."""
    assert (
        is_granted(
            permissions, p_type="vms", p_id=100, permission=ProxmoxPermission.POWER
        )
        is expected
    )
