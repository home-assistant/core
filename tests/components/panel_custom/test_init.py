"""The tests for the panel_custom component."""
from unittest.mock import Mock, patch

from homeassistant import setup
from homeassistant.components import frontend


async def test_webcomponent_custom_path_not_found(hass):
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
        result = await setup.async_setup_component(
            hass, 'panel_custom', config
        )
        assert not result
        assert len(hass.data.get(frontend.DATA_PANELS, {})) == 0


async def test_webcomponent_custom_path(hass):
    """Test if a web component is found in config panels dir."""
    filename = 'mock.file'

    config = {
        'panel_custom': {
            'name': 'todo-mvc',
            'webcomponent_path': filename,
            'sidebar_title': 'Sidebar Title',
            'sidebar_icon': 'mdi:iconicon',
            'url_path': 'nice_url',
            'config': {
                'hello': 'world',
            }
        }
    }

    with patch('os.path.isfile', Mock(return_value=True)):
        with patch('os.access', Mock(return_value=True)):
            result = await setup.async_setup_component(
                hass, 'panel_custom', config
            )
            assert result

            panels = hass.data.get(frontend.DATA_PANELS, [])

            assert panels
            assert 'nice_url' in panels

            panel = panels['nice_url']

            assert panel.config == {
                'hello': 'world',
                '_panel_custom': {
                    'html_url': '/api/panel_custom/todo-mvc',
                    'name': 'todo-mvc',
                    'embed_iframe': False,
                    'trust_external': False,
                },
            }
            assert panel.frontend_url_path == 'nice_url'
            assert panel.sidebar_icon == 'mdi:iconicon'
            assert panel.sidebar_title == 'Sidebar Title'


async def test_js_webcomponent(hass):
    """Test if a web component is found in config panels dir."""
    config = {
        'panel_custom': {
            'name': 'todo-mvc',
            'js_url': '/local/bla.js',
            'sidebar_title': 'Sidebar Title',
            'sidebar_icon': 'mdi:iconicon',
            'url_path': 'nice_url',
            'config': {
                'hello': 'world',
            },
            'embed_iframe': True,
            'trust_external_script': True,
        }
    }

    result = await setup.async_setup_component(
        hass, 'panel_custom', config
    )
    assert result

    panels = hass.data.get(frontend.DATA_PANELS, [])

    assert panels
    assert 'nice_url' in panels

    panel = panels['nice_url']

    assert panel.config == {
        'hello': 'world',
        '_panel_custom': {
            'js_url': '/local/bla.js',
            'name': 'todo-mvc',
            'embed_iframe': True,
            'trust_external': True,
        }
    }
    assert panel.frontend_url_path == 'nice_url'
    assert panel.sidebar_icon == 'mdi:iconicon'
    assert panel.sidebar_title == 'Sidebar Title'


async def test_module_webcomponent(hass):
    """Test if a js module is found in config panels dir."""
    config = {
        'panel_custom': {
            'name': 'todo-mvc',
            'module_url': '/local/bla.js',
            'sidebar_title': 'Sidebar Title',
            'sidebar_icon': 'mdi:iconicon',
            'url_path': 'nice_url',
            'config': {
                'hello': 'world',
            },
            'embed_iframe': True,
            'trust_external_script': True,
            'require_admin': True,
        }
    }

    result = await setup.async_setup_component(
        hass, 'panel_custom', config
    )
    assert result

    panels = hass.data.get(frontend.DATA_PANELS, [])

    assert panels
    assert 'nice_url' in panels

    panel = panels['nice_url']

    assert panel.require_admin
    assert panel.config == {
        'hello': 'world',
        '_panel_custom': {
            'module_url': '/local/bla.js',
            'name': 'todo-mvc',
            'embed_iframe': True,
            'trust_external': True,
        }
    }
    assert panel.frontend_url_path == 'nice_url'
    assert panel.sidebar_icon == 'mdi:iconicon'
    assert panel.sidebar_title == 'Sidebar Title'


async def test_url_option_conflict(hass):
    """Test config with multiple url options."""
    to_try = [
        {'panel_custom': {
            'name': 'todo-mvc',
            'module_url': '/local/bla.js',
            'js_url': '/local/bla.js',
        }
        }, {'panel_custom': {
            'name': 'todo-mvc',
            'webcomponent_path': '/local/bla.html',
            'js_url': '/local/bla.js',
        }}, {'panel_custom': {
            'name': 'todo-mvc',
            'webcomponent_path': '/local/bla.html',
            'module_url': '/local/bla.js',
            'js_url': '/local/bla.js',
        }}
    ]

    for config in to_try:
        result = await setup.async_setup_component(
            hass, 'panel_custom', config
        )
        assert not result
