"""Tests for the Z-Wave init."""
import asyncio
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.bootstrap import async_setup_component


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
def test_valid_device_config(hass):
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
def test_invalid_device_config(hass):
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
