"""Test air-Q diagnostics."""

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.airq.const import DOMAIN
from homeassistant.core import HomeAssistant

from .common import TEST_DEVICE_INFO, TEST_USER_DATA

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_airq,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data=TEST_USER_DATA, unique_id=TEST_DEVICE_INFO["id"]
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)

    assert result == snapshot
