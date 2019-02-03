"""Test configuration for the ZHA component."""
from unittest.mock import patch
import pytest
from homeassistant import config_entries
from homeassistant.components.zha.core.const import (
    DOMAIN, DATA_ZHA
)
from homeassistant.components.zha.core.gateway import ZHAGateway
from .common import async_setup_entry


@pytest.fixture(name='config_entry')
def config_entry_fixture(hass):
    """Fixture representing a config entry."""
    config_entry = config_entries.ConfigEntry(
        1, DOMAIN, 'Mock Title', {}, 'test',
        config_entries.CONN_CLASS_LOCAL_PUSH)
    return config_entry


@pytest.fixture(name='zha_gateway')
def zha_gateway_fixture(hass):
    """Fixture representing a zha gateway."""
    return ZHAGateway(hass, {})


@pytest.fixture(autouse=True)
async def setup_zha(hass, config_entry):
    """Load the ZHA component."""
    # this prevents needing an actual radio and zigbee network available
    with patch('homeassistant.components.zha.async_setup_entry',
               async_setup_entry):
        hass.data[DATA_ZHA] = {}

        # init ZHA
        await hass.config_entries.async_forward_entry_setup(
            config_entry, DOMAIN)
        await hass.async_block_till_done()
