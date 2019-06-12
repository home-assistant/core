"""Test configuration for the ZHA component."""
from unittest.mock import patch
import pytest
from homeassistant import config_entries
from homeassistant.components.zha.core.const import (
    DOMAIN, DATA_ZHA, COMPONENTS
)
from homeassistant.components.zha.core.gateway import ZHAGateway
from homeassistant.components.zha.core.registries import \
    establish_device_mappings
from homeassistant.components.zha.core.channels.registry \
    import populate_channel_registry
from .common import async_setup_entry
from homeassistant.components.zha.core.store import async_get_registry


@pytest.fixture(name='config_entry')
def config_entry_fixture(hass):
    """Fixture representing a config entry."""
    config_entry = config_entries.ConfigEntry(
        1, DOMAIN, 'Mock Title', {}, 'test',
        config_entries.CONN_CLASS_LOCAL_PUSH)
    return config_entry


@pytest.fixture(name='zha_gateway')
async def zha_gateway_fixture(hass):
    """Fixture representing a zha gateway.

    Create a ZHAGateway object that can be used to interact with as if we
    had a real zigbee network running.
    """
    populate_channel_registry()
    establish_device_mappings()
    for component in COMPONENTS:
        hass.data[DATA_ZHA][component] = (
            hass.data[DATA_ZHA].get(component, {})
        )
    zha_storage = await async_get_registry(hass)
    gateway = ZHAGateway(hass, {})
    gateway.zha_storage = zha_storage
    return gateway


@pytest.fixture(autouse=True)
async def setup_zha(hass, config_entry):
    """Load the ZHA component.

    This will init the ZHA component. It loads the component in HA so that
    we can test the domains that ZHA supports without actually having a zigbee
    network running.
    """
    # this prevents needing an actual radio and zigbee network available
    with patch('homeassistant.components.zha.async_setup_entry',
               async_setup_entry):
        hass.data[DATA_ZHA] = {}

        # init ZHA
        await hass.config_entries.async_forward_entry_setup(
            config_entry, DOMAIN)
        await hass.async_block_till_done()
