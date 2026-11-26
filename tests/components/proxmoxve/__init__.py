"""Tests for Proxmox VE integration."""

from pytest_homeassistant.common import MockConfigEntry, load_json_object_fixture

from homeassistant.components.proxmoxve.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

# Real response for PVEAuditor on /, with ACLs on VMs outside the mocked cluster
AUDIT_PERMISSIONS = load_json_object_fixture("access_permissions.json", DOMAIN)
AUDITOR_PRIVILEGES = AUDIT_PERMISSIONS["/"]
# The real response grants VM 102 exactly the PVEVMUser role
PVEVMUSER_PRIVILEGES = AUDIT_PERMISSIONS["/vms/102"]

# Paths Proxmox lists for a role granted on /, each with what / propagates
ROOT_PROPAGATED_PATHS = [
    path for path in AUDIT_PERMISSIONS if not path.startswith("/vms/")
]

MERGED_PERMISSIONS = {
    **{
        path: {
            **AUDITOR_PRIVILEGES,
            "Sys.Modify": 1,
            "Sys.PowerMgmt": 1,
            "VM.PowerMgmt": 1,
            "VM.Snapshot": 1,
        }
        for path in ROOT_PROPAGATED_PATHS
    },
    # PVEAuditor on VM 101 replaces the power and snapshot rights from /
    "/vms/101": AUDITOR_PRIVILEGES,
}

PVEVMUSER_PERMISSIONS = {"/vms": PVEVMUSER_PRIVILEGES}


async def setup_integration(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Set up the Proxmox VE integration for testing and enable all entities."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)

    for entry in er.async_entries_for_config_entry(
        entity_registry, config_entry.entry_id
    ):
        if entry.disabled_by is not None:
            entity_registry.async_update_entity(entry.entity_id, disabled_by=None)

    await hass.async_block_till_done()
