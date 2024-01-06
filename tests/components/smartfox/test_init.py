"""Smartfox init tests."""

from unittest.mock import patch

from homeassistant.components.smartfox import DOMAIN
from homeassistant.core import HomeAssistant

from . import MOCK_HOST, setup_fronius_integration


async def test_setup_fronius_integration(hass: HomeAssistant, caplog):
    """Test the setup of the Fronius integration."""
    with patch(
        "homeassistant.components.smartfox.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        entry = await setup_fronius_integration(hass)
        assert entry.domain == DOMAIN
        assert entry.data == {
            "host": MOCK_HOST,
            "is_logger": True,
        }
        assert mock_setup_entry.called

        mock_setup_entry.reset_mock()

        entry = await setup_fronius_integration(hass, is_logger=False)
        assert entry.data == {
            "host": MOCK_HOST,
            "is_logger": False,
        }
        assert mock_setup_entry.called
