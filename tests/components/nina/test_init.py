"""Test the Nina init file."""
from typing import Any, Dict

from homeassistant.components.nina.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

ENTRY_DATA: Dict[str, Any] = {
    "slots": 5,
    "corona_filter": True,
    "regions": {"083350000000": "Aach, Stadt"},
}


async def test_config_entry_not_ready(hass: HomeAssistant) -> None:
    """Test the configuration entry."""
    entry: MockConfigEntry = MockConfigEntry(
        domain=DOMAIN, title="NINA", data=ENTRY_DATA
    )
    entry.add_to_hass(hass)

    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    assert entry.state == ConfigEntryState.LOADED
