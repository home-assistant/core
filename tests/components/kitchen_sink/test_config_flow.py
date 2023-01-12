"""Test the Everything but the Kitchen Sink config flow."""
from unittest.mock import patch

from homeassistant import setup
from homeassistant.components.kitchen_sink import DOMAIN


async def test_import(hass):
    """Test that we can import a config entry."""
    with patch("homeassistant.components.kitchen_sink.async_setup_entry"):
        assert await setup.async_setup_component(hass, DOMAIN, {DOMAIN: {}})
        await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.data == {}

    # Test importing again doesn't create a 2nd entry
    with patch("homeassistant.components.kitchen_sink.async_setup_entry"):
        assert await setup.async_setup_component(hass, DOMAIN, {DOMAIN: {}})
        await hass.async_block_till_done()
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
