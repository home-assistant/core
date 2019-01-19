"""Tests for the TP-Link component."""
from unittest.mock import patch
import pytest
from homeassistant import config_entries, data_entry_flow
from homeassistant.setup import async_setup_component
from homeassistant.components import tplink

from tests.common import MockDependency, mock_coro
from pyHS100 import SmartPlug, SmartBulb


mock_pyhs110 = MockDependency("pyHS100")


async def test_creating_entry_tries_discover(hass):
    """Test setting up does discovery."""
    with patch('homeassistant.components.tplink.async_setup_entry',
               return_value=mock_coro(True)) as mock_setup, \
            mock_pyhs110, \
            patch('pyHS100.Discover.discover',
                  return_value={'host': 1234}):
        result = await hass.config_entries.flow.async_init(
            tplink.DOMAIN, context={'source': config_entries.SOURCE_USER})

        # Confirmation form
        assert result['type'] == data_entry_flow.RESULT_TYPE_FORM

        result = await hass.config_entries.flow.async_configure(
            result['flow_id'], {})
        assert result['type'] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY

        await hass.async_block_till_done()

    assert len(mock_setup.mock_calls) == 1


# Only tplink: in the config file
async def test_configuring_tplink_causes_discovery(hass):
    """Test that specifying empty config does discovery."""
    with mock_pyhs110, patch('pyHS100.Discover.discover') as discover:
        discover.return_value = {'host': 1234}
        await async_setup_component(hass, tplink.DOMAIN, {
            'tplink': {}
        })
        await hass.async_block_till_done()

    assert len(discover.mock_calls) == 1


@pytest.mark.parametrize("name,cls,platform", [
    ('pyHS100.SmartPlug', SmartPlug, 'switch'),
    ('pyHS100.SmartBulb', SmartBulb, 'light')
])
async def test_configuring_switch(hass, name, cls, platform):
    """Test that light or switch platform list is filled correctly."""
    with patch('pyHS100.Discover.discover') as discover, \
            patch('pyHS100.SmartDevice._query_helper'):
        discover.return_value = {'host': cls("123.123.123.123")}
        await async_setup_component(hass, tplink.DOMAIN, {'tplink': {}})
        await hass.async_block_till_done()

    assert len(discover.mock_calls) == 1
    assert len(hass.data[tplink.DOMAIN][platform]) == 1


async def test_is_dimmable(hass):
    """Test that is_dimmable returning switches are correctly added as light."""
    with patch('pyHS100.Discover.discover') as discover, \
            patch('homeassistant.components.tplink.light.async_setup_entry',
                  return_value=mock_coro(True)) as setup, \
            patch('pyHS100.SmartDevice._query_helper'), \
            patch('pyHS100.SmartPlug.is_dimmable', True):
        dimmable_switch = SmartPlug("123.123.123.123")
        discover.return_value = {'host': dimmable_switch}

        await async_setup_component(hass, tplink.DOMAIN, {'tplink': {}})
        await hass.async_block_till_done()

    assert len(discover.mock_calls) == 1
    assert len(setup.mock_calls) == 1
    assert len(hass.data[tplink.DOMAIN]['light']) == 1
    assert len(hass.data[tplink.DOMAIN]['switch']) == 0


async def test_configuring_discovery_disabled(hass):
    """Test that discover does not get called when disabled."""
    with MockDependency('pyHS100'), \
         patch('homeassistant.components.tplink.async_setup_entry',
               return_value=mock_coro(True)) as mock_setup, \
            patch('pyHS100.Discover.discover',
                  return_value=[]) as discover:
        await async_setup_component(hass, tplink.DOMAIN, {
            tplink.DOMAIN: {
                tplink.CONF_DISCOVERY: False
            }
        })
        await hass.async_block_till_done()

    assert len(discover.mock_calls) == 0
    assert len(mock_setup.mock_calls) == 1


async def test_platforms_are_initialized(hass):
    """Test that platforms are initialized per configuration array"""
    config = {'tplink':
                  {'discovery': False,
                   'light': [{"host": "123.123.123.123"}],
                   'switch': [{"host": "321.321.321.321"}],
                   }
              }

    with patch('pyHS100.Discover.discover') as discover, \
            patch('pyHS100.SmartDevice._query_helper'), \
            patch('homeassistant.components.tplink.light.async_setup_entry',
                  return_value=mock_coro(True)) as light_setup, \
            patch('homeassistant.components.tplink.switch.async_setup_entry',
                  return_value=mock_coro(True)) as switch_setup, \
            patch('pyHS100.SmartPlug.is_dimmable', False):
        # patching is_dimmable is necessray to avoid misdetection as light.
        await async_setup_component(hass, tplink.DOMAIN, config)
        await hass.async_block_till_done()

    assert len(discover.mock_calls) == 0
    assert len(light_setup.mock_calls) == 1
    assert len(switch_setup.mock_calls) == 1


async def test_no_config_creates_no_entry(hass):
    """Test for when there is no tplink in config."""
    with patch('homeassistant.components.tplink.async_setup_entry',
               return_value=mock_coro(True)) as mock_setup, \
            MockDependency('pyHS100'):
        await async_setup_component(hass, tplink.DOMAIN, {})
        await hass.async_block_till_done()

    assert len(mock_setup.mock_calls) == 0
