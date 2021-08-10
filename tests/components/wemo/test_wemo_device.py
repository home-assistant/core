"""Tests for wemo_device.py."""
from unittest.mock import patch

import pytest
from pywemo import PyWeMoException

from homeassistant.components.wemo import CONF_DISCOVERY, CONF_STATIC, wemo_device
from homeassistant.components.wemo.const import DOMAIN
from homeassistant.helpers import device_registry
from homeassistant.setup import async_setup_component

from .conftest import MOCK_HOST


@pytest.fixture
def pywemo_model():
    """Pywemo Dimmer models use the light platform (WemoDimmer class)."""
    return "Dimmer"


async def test_async_register_device_longpress_fails(hass, pywemo_device):
    """Device is still registered if ensure_long_press_virtual_device fails."""
    with patch.object(pywemo_device, "ensure_long_press_virtual_device") as elp:
        elp.side_effect = PyWeMoException
        assert await async_setup_component(
            hass,
            DOMAIN,
            {
                DOMAIN: {
                    CONF_DISCOVERY: False,
                    CONF_STATIC: [MOCK_HOST],
                },
            },
        )
        await hass.async_block_till_done()
    dr = device_registry.async_get(hass)
    device_entries = list(dr.devices.values())
    assert len(device_entries) == 1
    device_wrapper = wemo_device.async_get_device(hass, device_entries[0].id)
    assert device_wrapper.supports_long_press is False
