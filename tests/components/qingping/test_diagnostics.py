"""Tests for the diagnostics data provided by the Qingping integration."""

from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant.components.qingping.const import DOMAIN
from homeassistant.core import HomeAssistant

from . import LIGHT_AND_SIGNAL_SERVICE_INFO

from tests.common import MockConfigEntry
from tests.components.bluetooth import inject_bluetooth_service_info
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics for a config entry."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id="aa:bb:cc:dd:ee:ff")
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    inject_bluetooth_service_info(hass, LIGHT_AND_SIGNAL_SERVICE_INFO)
    await hass.async_block_till_done()

    assert await get_diagnostics_for_config_entry(hass, hass_client, entry) == snapshot(
        exclude=props("created_at", "modified_at", "entry_id", "time")
    )
