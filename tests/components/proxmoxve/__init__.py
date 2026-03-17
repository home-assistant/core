"""Tests for Proxmox VE integration."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry

# Example permissions dict with audit permissions granted for nodes and vms
AUDIT_PERMISSIONS = {
    "/nodes": {
        "VM.GuestAgent.Audit": 1,
        "Sys.Audit": 1,
        "VM.Audit": 1,
    },
    "/vms": {
        "Sys.Audit": 1,
        "VM.GuestAgent.Audit": 1,
        "VM.Audit": 1,
    },
    "/": {
        "VM.Audit": 1,
        "VM.GuestAgent.Audit": 1,
        "Sys.Audit": 1,
    },
}

POWER_PERMISSIONS = {
    "/nodes": {"VM.PowerMgmt": 1},
    "/vms": {"VM.PowerMgmt": 1},
    "/": {
        "VM.PowerMgmt": 1,
    },
}

MERGED_PERMISSIONS = {
    key: value | POWER_PERMISSIONS.get(key, {})
    for key, value in AUDIT_PERMISSIONS.items()
}


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
