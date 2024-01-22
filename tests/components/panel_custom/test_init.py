"""The tests for the panel_custom component."""
from unittest.mock import Mock, patch

from homeassistant import setup
from homeassistant.components import frontend, panel_custom
from homeassistant.core import HomeAssistant


async def test_webcomponent_custom_path_not_found(hass: HomeAssistant) -> None:
    """Test if a web component is found in config panels dir."""
    filename = "mock.file"

    config = {
        "panel_custom": {
            "name": "todomvc",
            "webcomponent_path": filename,
            "sidebar_title": "Sidebar Title",
            "sidebar_icon": "mdi:iconicon",
            "url_path": "nice_url",
            "config": 5,
        }
    }

    with patch("os.path.isfile", Mock(return_value=False)):
        result = await setup.async_setup_component(hass, "panel_custom", config)
        assert not result

        panels = hass.data.get(frontend.DATA_PANELS, [])

        assert panels
        assert "nice_url" not in panels


async def test_js_webcomponent(hass: HomeAssistant) -> None:
    """Test if a web component is found in config panels dir."""
    config = {
        "panel_custom": {
            "name": "todo-mvc",
            "js_url": "/local/bla.js",
            "sidebar_title": "Sidebar Title",
            "sidebar_icon": "mdi:iconicon",
            "url_path": "nice_url",
            "config": {"hello": "world"},
            "embed_iframe": True,
            "trust_external_script": True,
        }
    }

    result = await setup.async_setup_component(hass, "panel_custom", config)
    assert result

    panels = hass.data.get(frontend.DATA_PANELS, [])

    assert panels
    assert "nice_url" in panels

    panel = panels["nice_url"]

    assert panel.config == {
        "hello": "world",
        "_panel_custom": {
            "js_url": "/local/bla.js",
            "name": "todo-mvc",
            "embed_iframe": True,
            "trust_external": True,
        },
    }
    assert panel.frontend_url_path == "nice_url"
    assert panel.sidebar_icon == "mdi:iconicon"
    assert panel.sidebar_title == "Sidebar Title"


async def test_module_webcomponent(hass: HomeAssistant) -> None:
    """Test if a js module is found in config panels dir."""
    config = {
        "panel_custom": {
            "name": "todo-mvc",
            "module_url": "/local/bla.js",
            "sidebar_title": "Sidebar Title",
            "sidebar_icon": "mdi:iconicon",
            "url_path": "nice_url",
            "config": {"hello": "world"},
            "embed_iframe": True,
            "trust_external_script": True,
            "require_admin": True,
        }
    }

    result = await setup.async_setup_component(hass, "panel_custom", config)
    assert result

    panels = hass.data.get(frontend.DATA_PANELS, [])

    assert panels
    assert "nice_url" in panels

    panel = panels["nice_url"]

    assert panel.require_admin
    assert panel.config == {
        "hello": "world",
        "_panel_custom": {
            "module_url": "/local/bla.js",
            "name": "todo-mvc",
            "embed_iframe": True,
            "trust_external": True,
        },
    }
    assert panel.frontend_url_path == "nice_url"
    assert panel.sidebar_icon == "mdi:iconicon"
    assert panel.sidebar_title == "Sidebar Title"


async def test_latest_and_es5_build(hass: HomeAssistant) -> None:
    """Test specifying an es5 and latest build."""
    config = {
        "panel_custom": {
            "name": "todo-mvc",
            "js_url": "/local/es5.js",
            "module_url": "/local/latest.js",
            "url_path": "nice_url",
        }
    }

    assert await setup.async_setup_component(hass, "panel_custom", config)

    panels = hass.data.get(frontend.DATA_PANELS, {})

    assert panels
    assert "nice_url" in panels

    panel = panels["nice_url"]

    assert panel.config == {
        "_panel_custom": {
            "name": "todo-mvc",
            "js_url": "/local/es5.js",
            "module_url": "/local/latest.js",
            "embed_iframe": False,
            "trust_external": False,
        },
    }
    assert panel.frontend_url_path == "nice_url"


async def test_url_path_conflict(hass: HomeAssistant) -> None:
    """Test config with overlapping url path."""
    assert await setup.async_setup_component(
        hass,
        "panel_custom",
        {
            "panel_custom": [
                {"name": "todo-mvc", "js_url": "/local/bla.js"},
                {"name": "todo-mvc", "js_url": "/local/bla.js"},
            ]
        },
    )


async def test_register_config_panel(hass: HomeAssistant) -> None:
    """Test setting up a custom config panel for an integration."""
    result = await setup.async_setup_component(hass, "panel_custom", {})
    assert result

    # Register a custom panel
    await panel_custom.async_register_panel(
        hass=hass,
        frontend_url_path="config_panel",
        webcomponent_name="custom-frontend",
        module_url="custom-frontend",
        embed_iframe=True,
        require_admin=True,
        config_panel_domain="test",
    )

    panels = hass.data.get(frontend.DATA_PANELS, [])
    assert panels
    assert "config_panel" in panels

    panel = panels["config_panel"]

    assert panel.config == {
        "_panel_custom": {
            "module_url": "custom-frontend",
            "name": "custom-frontend",
            "embed_iframe": True,
            "trust_external": False,
        },
    }
    assert panel.frontend_url_path == "config_panel"
    assert panel.config_panel_domain == "test"
