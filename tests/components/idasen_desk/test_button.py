"""Test the IKEA Idasen Desk connection buttons."""

from unittest.mock import MagicMock

from homeassistant.core import HomeAssistant

from . import init_integration


async def test_connect_button(
    hass: HomeAssistant,
    mock_desk_api: MagicMock,
) -> None:
    """Test pressing the connect button."""
    await init_integration(hass)

    await hass.services.async_call(
        "button", "press", {"entity_id": "button.test_connect"}, blocking=True
    )
    assert mock_desk_api.connect.call_count == 2


async def test_disconnect_button(
    hass: HomeAssistant,
    mock_desk_api: MagicMock,
) -> None:
    """Test pressing the disconnect button."""
    await init_integration(hass)
    mock_desk_api.is_connected = True

    await hass.services.async_call(
        "button", "press", {"entity_id": "button.test_disconnect"}, blocking=True
    )
    mock_desk_api.disconnect.assert_called_once()
