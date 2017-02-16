"""Tests for the Z-Wave init."""
import asyncio
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.bootstrap import async_setup_component
from homeassistant.components.zwave import (
    DATA_DEVICE_CONFIG, DEVICE_CONFIG_SCHEMA_ENTRY)


@pytest.fixture(autouse=True)
def mock_openzwave():
    """Mock out Open Z-Wave."""
    libopenzwave = MagicMock()
    libopenzwave.__file__ = 'test'
    with patch.dict('sys.modules', {
        'libopenzwave': libopenzwave,
        'openzwave.option': MagicMock(),
        'openzwave.network': MagicMock(),
        'openzwave.group': MagicMock(),
    }):
        yield


@asyncio.coroutine
def test_device_config(hass):
    """Test device config stored in hass."""
    device_config = {
        'light.kitchen': {
            'ignored': 'true'
        }
    }
    yield from async_setup_component(hass, 'zwave', {
        'zwave': {
            'device_config': device_config
        }})

    assert DATA_DEVICE_CONFIG in hass.data

    test_data = {
        key: DEVICE_CONFIG_SCHEMA_ENTRY(value)
        for key, value in device_config.items()
    }

    assert hass.data[DATA_DEVICE_CONFIG].get('light.kitchen') == \
        test_data.get('light.kitchen')
