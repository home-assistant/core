"""Test the my init."""

from unittest import mock

from spencerassistant.components.my import URL_PATH
from spencerassistant.setup import async_setup_component


async def test_setup(hass):
    """Test setup."""
    with mock.patch(
        "spencerassistant.components.frontend.async_register_built_in_panel"
    ) as mock_register_panel:
        assert await async_setup_component(hass, "my", {"foo": "bar"})
        assert mock_register_panel.call_args == mock.call(
            hass, "my", frontend_url_path=URL_PATH
        )
