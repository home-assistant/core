"""Test System Nexa 2 diagnostics."""

from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_system_nexa_2_device,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics for config entry."""
    entry = MockConfigEntry(
        domain="systemnexa2",
        data={
            "host": "10.0.0.131",
            "name": "Test Device",
            "device_id": "test_device_id",
            "model": "Test Model",
        },
        unique_id="test_device_id",
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await get_diagnostics_for_config_entry(hass, hass_client, entry)

    assert result == snapshot
