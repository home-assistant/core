"""Salus component tests."""
from unittest.mock import patch

from homeassistant.components.salus.const import DOMAIN

from .mocks import MOCK_CONFIG_ENTRY, _get_mock_salus

from tests.common import MockConfigEntry


async def test_init_success(hass):
    """Test that we can setup with valid config."""
    mock_salus = _get_mock_salus()

    with patch(
        "homeassistant.components.salus.Api",
        return_value=mock_salus,
    ):
        config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG_ENTRY)
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
