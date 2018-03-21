"""Test Hue bridge."""
import asyncio
from unittest.mock import Mock, patch

import aiohue
import pytest

from homeassistant.components import hue

from tests.common import mock_coro


class MockBridge(hue.HueBridge):
    """Class that sets default for constructor."""

    def __init__(self, hass, host='1.2.3.4', filename='mock-bridge.conf',
                 username=None, **kwargs):
        """Initialize a mock bridge."""
        super().__init__(host, hass, filename, username, **kwargs)


@pytest.fixture
def mock_request():
    """Mock configurator.async_request_config."""
    with patch('homeassistant.components.configurator.'
               'async_request_config') as mock_request:
        yield mock_request


async def test_setup_request_config_button_not_pressed(hass, mock_request):
    """Test we request config if link button has not been pressed."""
    with patch('aiohue.Bridge.create_user',
               side_effect=aiohue.LinkButtonNotPressed):
        await MockBridge(hass).async_setup()

    assert len(mock_request.mock_calls) == 1


async def test_setup_request_config_invalid_username(hass, mock_request):
    """Test we request config if username is no longer whitelisted."""
    with patch('aiohue.Bridge.create_user',
               side_effect=aiohue.Unauthorized):
        await MockBridge(hass).async_setup()

    assert len(mock_request.mock_calls) == 1


async def test_setup_timeout(hass, mock_request):
    """Test we give up when there is a timeout."""
    with patch('aiohue.Bridge.create_user',
               side_effect=asyncio.TimeoutError):
        await MockBridge(hass).async_setup()

    assert len(mock_request.mock_calls) == 0


async def test_only_create_no_username(hass):
    """."""
    with patch('aiohue.Bridge.create_user') as mock_create, \
            patch('aiohue.Bridge.initialize') as mock_init:
        await MockBridge(hass, username='bla').async_setup()

    assert len(mock_create.mock_calls) == 0
    assert len(mock_init.mock_calls) == 1


async def test_configurator_callback(hass, mock_request):
    """."""
    with patch('aiohue.Bridge.create_user',
               side_effect=aiohue.LinkButtonNotPressed):
        await MockBridge(hass).async_setup()

    assert len(mock_request.mock_calls) == 1

    callback = mock_request.mock_calls[0][1][2]

    mock_init = Mock(return_value=mock_coro())
    mock_create = Mock(return_value=mock_coro())

    with patch('aiohue.Bridge') as mock_bridge, \
            patch('homeassistant.helpers.discovery.async_load_platform',
                  return_value=mock_coro()) as mock_load_platform, \
            patch('homeassistant.components.hue.save_json') as mock_save:
        inst = mock_bridge()
        inst.username = 'mock-user'
        inst.create_user = mock_create
        inst.initialize = mock_init
        await callback(None)

    assert len(mock_create.mock_calls) == 1
    assert len(mock_init.mock_calls) == 1
    assert len(mock_save.mock_calls) == 1
    assert mock_save.mock_calls[0][1][1] == {
        '1.2.3.4': {
            'username': 'mock-user'
        }
    }
    assert len(mock_load_platform.mock_calls) == 1
