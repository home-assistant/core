"""Test initialization of Acaia integration."""
from homeassistant.components.acaia.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from . import init_integration


async def test_async_setup_entry(hass: HomeAssistant) -> None:
    """Test a successful setup entry."""
    await init_integration(hass)

    state = hass.states.get("button.lunar_1234_3")
    assert state is not None
    assert state.state != STATE_UNAVAILABLE


async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test successful unload of entry."""
    entry = await init_integration(hass)

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert not hass.data.get(DOMAIN)
