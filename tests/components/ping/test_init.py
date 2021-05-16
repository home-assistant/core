"""Test ping id allocation."""

from homeassistant.components.ping import async_get_next_ping_id
from homeassistant.components.ping.const import (
    DEFAULT_START_ID,
    DOMAIN,
    MAX_PING_ID,
    PING_ID,
)


async def test_async_get_next_ping_id(hass):
    """Verify we allocate ping ids as expected."""
    hass.data[DOMAIN] = {PING_ID: DEFAULT_START_ID}

    assert async_get_next_ping_id(hass) == DEFAULT_START_ID + 1
    assert async_get_next_ping_id(hass) == DEFAULT_START_ID + 2
    assert async_get_next_ping_id(hass, 2) == DEFAULT_START_ID + 3
    assert async_get_next_ping_id(hass) == DEFAULT_START_ID + 5

    hass.data[DOMAIN][PING_ID] = MAX_PING_ID
    assert async_get_next_ping_id(hass) == DEFAULT_START_ID + 1
    assert async_get_next_ping_id(hass) == DEFAULT_START_ID + 2

    hass.data[DOMAIN][PING_ID] = MAX_PING_ID
    assert async_get_next_ping_id(hass, 2) == DEFAULT_START_ID + 1
    assert async_get_next_ping_id(hass) == DEFAULT_START_ID + 3
