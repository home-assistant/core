"""Tests for init module."""
from unittest.mock import patch

from homeassistant.components.nws.const import DOMAIN

from .helpers import setup_nws
from .helpers.pynws import mock_nws


async def test_unload(hass):
    """Test a successful unload of entry."""
    MockNws = mock_nws()
    with patch("homeassistant.components.nws.SimpleNWS", return_value=MockNws()), patch(
        "homeassistant.components.nws.config_flow.SimpleNWS", return_value=MockNws()
    ):
        await setup_nws(hass)
        await hass.async_block_till_done()

    assert len(hass.data[DOMAIN]) == 1
    entry_id = list(hass.data[DOMAIN].keys())[0]
    assert entry_id is not None

    # Unload config entry.
    assert await hass.config_entries.async_unload(entry_id)
    await hass.async_block_till_done()
    assert hass.data[DOMAIN].get(entry_id) is None
