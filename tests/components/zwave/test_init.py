"""Tests for the Z-Wave init."""
import asyncio
import unittest
from collections import OrderedDict

from homeassistant.bootstrap import async_setup_component
from homeassistant.components.zwave import (
    CONFIG_SCHEMA, CONF_DEVICE_CONFIG_GLOB)


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


class TestZwave(unittest.TestCase):
    """Test zwave init."""

    def test_device_config_glob_is_ordered(self):
        """Test that device_config_glob preserves order."""
        conf = CONFIG_SCHEMA(
            {'zwave': {CONF_DEVICE_CONFIG_GLOB: OrderedDict()}})
        self.assertIsInstance(
            conf['zwave'][CONF_DEVICE_CONFIG_GLOB], OrderedDict)
