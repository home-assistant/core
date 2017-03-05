"""Test config init."""
import asyncio
from unittest.mock import patch

import pytest

from homeassistant.const import EVENT_COMPONENT_LOADED
from homeassistant.setup import async_setup_component, ATTR_COMPONENT
from homeassistant.components import config

from tests.common import mock_http_component, mock_coro, mock_component


@pytest.fixture(autouse=True)
def stub_http(hass):
    """Stub the HTTP component."""
    mock_http_component(hass)


@asyncio.coroutine
def test_config_setup(hass, loop):
    """Test it sets up hassbian."""
    yield from async_setup_component(hass, 'config', {})
    assert 'config' in hass.config.components


@asyncio.coroutine
def test_load_on_demand_already_loaded(hass, test_client):
    """Test getting suites."""
    mock_component(hass, 'zwave')

    with patch.object(config, 'SECTIONS', []), \
            patch.object(config, 'ON_DEMAND', ['zwave']), \
            patch('homeassistant.components.config.zwave.async_setup') as stp:
        stp.return_value = mock_coro(True)

        yield from async_setup_component(hass, 'config', {})

    yield from hass.async_block_till_done()
    assert 'config.zwave' in hass.config.components
    assert stp.called


@asyncio.coroutine
def test_load_on_demand_on_load(hass, test_client):
    """Test getting suites."""
    with patch.object(config, 'SECTIONS', []), \
            patch.object(config, 'ON_DEMAND', ['zwave']):
        yield from async_setup_component(hass, 'config', {})

    assert 'config.zwave' not in hass.config.components

    with patch('homeassistant.components.config.zwave.async_setup') as stp:
        stp.return_value = mock_coro(True)
        hass.bus.async_fire(EVENT_COMPONENT_LOADED, {ATTR_COMPONENT: 'zwave'})
        yield from hass.async_block_till_done()

    assert 'config.zwave' in hass.config.components
    assert stp.called
