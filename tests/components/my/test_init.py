"""Test the my init."""
from unittest import mock

from homeassistant.components.my import URL_PATH
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


async def test_setup(hass: HomeAssistant) -> None:
    """Test setup."""
    with mock.patch(
        "homeassistant.components.frontend.async_register_built_in_panel"
    ) as mock_register_panel:
        assert await async_setup_component(hass, "my", {"foo": "bar"})
        assert mock_register_panel.call_args == mock.call(
            hass, "my", frontend_url_path=URL_PATH
        )
