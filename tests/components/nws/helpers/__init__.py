"""Helpers for nws tests."""
from homeassistant import config_entries
from homeassistant.components.nws import DOMAIN


async def setup_nws(hass):
    """Set up nws integration with default config entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"latitude": 50, "longitude": -75, "api_key": "test_key"},
    )
    await hass.config_entries.flow.async_configure(
        result2["flow_id"], {"station": "ABC"},
    )
    await hass.async_block_till_done()
