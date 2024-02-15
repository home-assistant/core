"""Test Enphase Envoy diagnostics."""
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator

# Fields to patch so they are the same between repeated runs
TO_REDACT = {
    "id",
    "device_id",
    "via_device_id",
    "last_updated",
    "last_changed",
}


async def test_entry_diagnostics(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    hass_client: ClientSessionGenerator,
    setup_enphase_envoy,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics."""
    result = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)
    # patch fields that change each run to fixed value and test
    assert async_redact_data(result, TO_REDACT) == snapshot
