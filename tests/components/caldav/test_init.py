"""Test the Caldav component."""

from unittest.mock import patch

from homeassistant.components.caldav import async_setup_entry, async_unload_entry
from homeassistant.components.caldav.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_URL, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_unload_component(hass: HomeAssistant):
    """Test unload component."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        data={CONF_URL: "url", CONF_USERNAME: "username"},
        entry_id=1,
        unique_id="username:url",
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.caldav.async_caldav_connect",
        return_value=[],
    ):
        assert await async_setup_entry(hass, entry)
        await hass.async_block_till_done()

        assert await async_unload_entry(hass, entry)
        assert not hass.data[DOMAIN]
