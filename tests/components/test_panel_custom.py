"""The tests for the panel_custom component."""
import asyncio
from unittest.mock import Mock, patch

import pytest

from homeassistant import setup

from tests.common import mock_coro, mock_component


@pytest.fixture
def mock_register(hass):
    """Mock the frontend component being loaded and yield register method."""
    mock_component(hass, 'frontend')
    with patch('homeassistant.components.frontend.async_register_panel',
               return_value=mock_coro()) as mock_register:
        yield mock_register


@asyncio.coroutine
def test_webcomponent_custom_path_not_found(hass, mock_register):
    """Test if a web component is found in config panels dir."""
    filename = 'mock.file'

    config = {
        'panel_custom': {
            'name': 'todomvc',
            'webcomponent_path': filename,
            'sidebar_title': 'Sidebar Title',
            'sidebar_icon': 'mdi:iconicon',
            'url_path': 'nice_url',
            'config': 5,
        }
    }

    with patch('os.path.isfile', Mock(return_value=False)):
        result = yield from setup.async_setup_component(
            hass, 'panel_custom', config
        )
        assert not result
        assert not mock_register.called


@asyncio.coroutine
def test_webcomponent_custom_path(hass, mock_register):
    """Test if a web component is found in config panels dir."""
    filename = 'mock.file'

    config = {
        'panel_custom': {
            'name': 'todomvc',
            'webcomponent_path': filename,
            'sidebar_title': 'Sidebar Title',
            'sidebar_icon': 'mdi:iconicon',
            'url_path': 'nice_url',
            'config': 5,
        }
    }

    with patch('os.path.isfile', Mock(return_value=True)):
        with patch('os.access', Mock(return_value=True)):
            result = yield from setup.async_setup_component(
                hass, 'panel_custom', config
            )
            assert result

            assert mock_register.called

            args = mock_register.mock_calls[0][1]
            assert args == (hass, 'todomvc', filename)

            kwargs = mock_register.mock_calls[0][2]
            assert kwargs == {
                'config': 5,
                'url_path': 'nice_url',
                'sidebar_icon': 'mdi:iconicon',
                'sidebar_title': 'Sidebar Title'
            }
