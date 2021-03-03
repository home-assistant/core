"""Test Litter-Robot setup process."""
from homeassistant.components import litterrobot
from homeassistant.setup import async_setup_component

from .common import CONFIG

from tests.common import MockConfigEntry


async def test_unload_entry(hass):
    """Test being able to unload an entry."""
    entry = MockConfigEntry(
        domain=litterrobot.DOMAIN,
        data=CONFIG[litterrobot.DOMAIN],
    )
    entry.add_to_hass(hass)

    assert await async_setup_component(hass, litterrobot.DOMAIN, {}) is True
    assert await litterrobot.async_unload_entry(hass, entry)
    assert hass.data[litterrobot.DOMAIN] == {}
