"""Test for wallbox Sensor."""

from unittest.mock import MagicMock

from homeassistant.components.wallbox.const import DOMAIN
from homeassistant.components.wallbox.sensor import async_setup_entry

from .const import MOCK_CONFIG

from tests.common import MockConfigEntry


async def test_async_setup_entry(hass):
    """Test setup of sensor."""
    async_add_entities = MagicMock()

    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    assert await async_setup_entry(hass, config_entry, async_add_entities)
    await hass.async_block_till_done()
