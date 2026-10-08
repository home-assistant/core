"""Tests for Proxmox VE update version selection."""

import pytest

from homeassistant.components.proxmoxve.helpers import update_version


@pytest.mark.parametrize(
    ("updates", "expected_version"),
    [
        pytest.param(
            [{"Package": "ceph-common", "Version": "19.2.6", "Origin": "Proxmox"}],
            "9.2.3",
            id="higher-ceph-version-is-not-pve-version",
        ),
        pytest.param(
            [{"Package": "libpve-storage-perl", "Version": "1+16.1+2+pmx1"}],
            "9.2.3",
            id="debian-package-version-is-not-parsed",
        ),
        pytest.param(
            [
                {"Package": "ceph-common", "Version": "19.2.6", "Origin": "Proxmox"},
                {"Package": "pve-manager", "Version": "9.2.21-1"},
            ],
            "9.2.21",
            id="pve-manager-version-is-used",
        ),
    ],
)
def test_update_version_uses_pve_manager(
    updates: list[dict[str, str]], expected_version: str
) -> None:
    """The PVE version must come only from pve-manager."""
    info = update_version("9.2.3", updates)

    assert info.latest_version == expected_version
    assert info.total_updates == len(updates)
