"""Tests for the TP-Link component."""
from __future__ import annotations

from unittest.mock import patch

from homeassistant.components import tplink
from homeassistant.setup import async_setup_component


async def test_configuring_tplink_causes_discovery(hass):
    """Test that specifying empty config does discovery."""
    with patch("homeassistant.components.tplink.Discover.discover") as discover:
        discover.return_value = {"host": 1234}
        await async_setup_component(hass, tplink.DOMAIN, {tplink.DOMAIN: {}})
        await hass.async_block_till_done()

    assert len(discover.mock_calls) == 1
