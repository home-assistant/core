"""Test the my init."""

from homeassistant.components.frontend import DATA_PANELS
from homeassistant.components.my import URL_PATH
from homeassistant.setup import async_setup_component


async def test_setup(hass):
    """Test setup."""
    assert await async_setup_component(hass, "my", {"foo": "bar"})
    panel = hass.data[DATA_PANELS][URL_PATH]
    assert panel.component_name == "my"
    assert panel.sidebar_title is None
    assert not panel.require_admin
