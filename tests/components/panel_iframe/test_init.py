"""The tests for the panel_iframe component."""
import pytest

from homeassistant.components import frontend
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


@pytest.mark.parametrize(
    "config_to_try",
    (
        {"invalid space": {"url": "https://home-assistant.io"}},
        {"router": {"url": "not-a-url"}},
    ),
)
async def test_wrong_config(hass: HomeAssistant, config_to_try) -> None:
    """Test setup with wrong configuration."""
    assert not await async_setup_component(
        hass, "panel_iframe", {"panel_iframe": config_to_try}
    )


async def test_correct_config(hass: HomeAssistant) -> None:
    """Test correct config."""
    assert await async_setup_component(
        hass,
        "panel_iframe",
        {
            "panel_iframe": {
                "router": {
                    "icon": "mdi:network-wireless",
                    "title": "Router",
                    "url": "http://192.168.1.1",
                    "require_admin": True,
                },
                "weather": {
                    "icon": "mdi:weather",
                    "title": "Weather",
                    "url": "https://www.wunderground.com/us/ca/san-diego",
                    "require_admin": True,
                },
                "api": {"icon": "mdi:weather", "title": "Api", "url": "/api"},
                "ftp": {
                    "icon": "mdi:weather",
                    "title": "FTP",
                    "url": "ftp://some/ftp",
                },
            }
        },
    )

    panels = hass.data[frontend.DATA_PANELS]

    assert panels.get("router").to_response() == {
        "component_name": "iframe",
        "config": {"url": "http://192.168.1.1"},
        "icon": "mdi:network-wireless",
        "title": "Router",
        "url_path": "router",
        "require_admin": True,
    }

    assert panels.get("weather").to_response() == {
        "component_name": "iframe",
        "config": {"url": "https://www.wunderground.com/us/ca/san-diego"},
        "icon": "mdi:weather",
        "title": "Weather",
        "url_path": "weather",
        "require_admin": True,
    }

    assert panels.get("api").to_response() == {
        "component_name": "iframe",
        "config": {"url": "/api"},
        "icon": "mdi:weather",
        "title": "Api",
        "url_path": "api",
        "require_admin": False,
    }

    assert panels.get("ftp").to_response() == {
        "component_name": "iframe",
        "config": {"url": "ftp://some/ftp"},
        "icon": "mdi:weather",
        "title": "FTP",
        "url_path": "ftp",
        "require_admin": False,
    }
