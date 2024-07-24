"""Test Guardian diagnostics."""

from syrupy import SnapshotAssertion

from homeassistant.components.guardian import DOMAIN, GuardianData
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.diagnostics import snapshot_get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_entry_diagnostics(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
    setup_guardian: None,  # relies on config_entry fixture
) -> None:
    """Test config entry diagnostics."""
    data: GuardianData = hass.data[DOMAIN][config_entry.entry_id]

    # Simulate the pairing of a paired sensor:
    await data.paired_sensor_manager.async_pair_sensor("AABBCCDDEEFF")

    assert await snapshot_get_diagnostics_for_config_entry(
        hass, hass_client, config_entry, snapshot
    )
