"""Test Enphase Envoy diagnostics."""

from syrupy import SnapshotAssertion

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator

# Fields to exclude from snapshot as they change each run
TO_EXCLUDE = {
    "id",
    "device_id",
    "via_device_id",
    "last_updated",
    "last_changed",
    "last_reported",
}


def limit_diagnostic_attrs(prop, path) -> bool:
    """Mark attributes to exclude from diagnostic snapshot."""
    return prop in TO_EXCLUDE


async def test_entry_diagnostics(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    hass_client: ClientSessionGenerator,
    setup_enphase_envoy,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics."""
    assert await get_diagnostics_for_config_entry(
        hass, hass_client, config_entry
    ) == snapshot(exclude=limit_diagnostic_attrs)
