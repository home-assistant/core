"""Test openSenseData component setup process."""

from homeassistant.components.opensensemap.const import DOMAIN
from homeassistant.core import HomeAssistant

from .conftest import ComponentSetup

from tests.common import MockConfigEntry


async def test_load_unload_entry(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    valid_config_entry: MockConfigEntry,
) -> None:
    """Test load and unload entry."""
    await setup_integration(valid_config_entry)
    entry = hass.config_entries.async_entries(DOMAIN)[0]

    assert await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()
