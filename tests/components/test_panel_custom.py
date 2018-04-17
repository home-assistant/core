"""The tests for the panel_custom component."""
import asyncio
from unittest.mock import Mock, patch

import pytest

from homeassistant import setup
from homeassistant.components import frontend

from tests.common import mock_component


@pytest.fixture(autouse=True)
def mock_frontend_loaded(hass):
    """Mock frontend is loaded."""
    mock_component(hass, 'frontend')


@asyncio.coroutine
def test_webcomponent_custom_path_not_found(hass):
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
        assert len(hass.data.get(frontend.DATA_PANELS, {})) == 0


@asyncio.coroutine
def test_webcomponent_custom_path(hass):
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

            panels = hass.data.get(frontend.DATA_PANELS, [])

            assert len(panels) == 1
            assert 'nice_url' in panels

            panel = panels['nice_url']

            assert panel.config == 5
            assert panel.frontend_url_path == 'nice_url'
            assert panel.sidebar_icon == 'mdi:iconicon'
            assert panel.sidebar_title == 'Sidebar Title'
            assert panel.path == filename
