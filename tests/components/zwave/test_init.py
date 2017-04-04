"""Tests for the Z-Wave init."""
import asyncio

from homeassistant.bootstrap import async_setup_component
from homeassistant.const import EVENT_HOMEASSISTANT_START
from homeassistant.components import zwave
from homeassistant.setup import setup_component

import pytest
import unittest

from tests.common import get_test_home_assistant
from tests.mock.zwave import MockNetwork


@asyncio.coroutine
def test_valid_device_config(hass, mock_openzwave):
    """Test valid device config."""
    device_config = {
        'light.kitchen': {
            'ignored': 'true'
        }
    }
    result = yield from async_setup_component(hass, 'zwave', {
        'zwave': {
            'device_config': device_config
        }})

    assert result


@asyncio.coroutine
def test_invalid_device_config(hass, mock_openzwave):
    """Test invalid device config."""
    device_config = {
        'light.kitchen': {
            'some_ignored': 'true'
        }
    }
    result = yield from async_setup_component(hass, 'zwave', {
        'zwave': {
            'device_config': device_config
        }})

    assert not result


@pytest.mark.usefixtures('mock_openzwave')
class TestZWaveServices(unittest.TestCase):
    """Tests for zwave services."""

    def setUp(self):
        """Initialize values for this testcase class."""
        self.hass = get_test_home_assistant()
        self.hass.start()

        # Initialize zwave
        setup_component(self.hass, 'zwave', {'zwave': {}})
        self.hass.block_till_done()
        zwave.NETWORK.state = MockNetwork.STATE_READY
        self.hass.bus.fire(EVENT_HOMEASSISTANT_START)
        self.hass.block_till_done()

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        self.hass.stop()

    def test_add_node(self):
        """Test zwave add_node service."""
        self.hass.services.call('zwave', 'add_node', {})
        self.hass.block_till_done()

        assert zwave.NETWORK.controller.add_node.called
        assert len(zwave.NETWORK.controller.add_node.mock_calls) == 1
        assert len(zwave.NETWORK.controller.add_node.mock_calls[0][1]) == 0

    def test_add_node_secure(self):
        """Test zwave add_node_secure service."""
        self.hass.services.call('zwave', 'add_node_secure', {})
        self.hass.block_till_done()

        assert zwave.NETWORK.controller.add_node.called
        assert len(zwave.NETWORK.controller.add_node.mock_calls) == 1
        assert zwave.NETWORK.controller.add_node.mock_calls[0][1][0] is True

    def test_remove_node(self):
        """Test zwave remove_node service."""
        self.hass.services.call('zwave', 'remove_node', {})
        self.hass.block_till_done()

        assert zwave.NETWORK.controller.remove_node.called
        assert len(zwave.NETWORK.controller.remove_node.mock_calls) == 1

    def test_cancel_command(self):
        """Test zwave cancel_command service."""
        self.hass.services.call('zwave', 'cancel_command', {})
        self.hass.block_till_done()

        assert zwave.NETWORK.controller.cancel_command.called
        assert len(zwave.NETWORK.controller.cancel_command.mock_calls) == 1

    def test_heal_network(self):
        """Test zwave heal_network service."""
        self.hass.services.call('zwave', 'heal_network', {})
        self.hass.block_till_done()

        assert zwave.NETWORK.heal.called
        assert len(zwave.NETWORK.heal.mock_calls) == 1

    def test_soft_reset(self):
        """Test zwave soft_reset service."""
        self.hass.services.call('zwave', 'soft_reset', {})
        self.hass.block_till_done()

        assert zwave.NETWORK.controller.soft_reset.called
        assert len(zwave.NETWORK.controller.soft_reset.mock_calls) == 1

    def test_test_network(self):
        """Test zwave test_network service."""
        self.hass.services.call('zwave', 'test_network', {})
        self.hass.block_till_done()

        assert zwave.NETWORK.test.called
        assert len(zwave.NETWORK.test.mock_calls) == 1

    def test_stop_network(self):
        """Test zwave stop_network service."""
        self.hass.services.call('zwave', 'stop_network', {})
        self.hass.block_till_done()

        assert zwave.NETWORK.stop.called
        assert len(zwave.NETWORK.stop.mock_calls) == 1
