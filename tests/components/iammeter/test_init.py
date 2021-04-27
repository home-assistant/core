"""Test the IamMeter component."""

from homeassistant.components.iammeter.const import DOMAIN
from homeassistant.config_entries import ENTRY_STATE_LOADED, ENTRY_STATE_NOT_LOADED
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT

from .const import HOST, NAME, PORT

from tests.common import MockConfigEntry


async def test_async_setup_entry(hass):
    """Test that it will forward setup entry."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_NAME: NAME, CONF_HOST: HOST, CONF_PORT: PORT}
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state == ENTRY_STATE_LOADED

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state == ENTRY_STATE_NOT_LOADED
    assert not hass.data.get(DOMAIN)
