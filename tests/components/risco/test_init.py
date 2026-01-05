"""Tests for the Risco integration."""

from unittest.mock import patch

import pytest

from homeassistant.core import HomeAssistant


@pytest.fixture
def mock_error_handler():
    """Create a mock for add_error_handler."""
    with patch("homeassistant.components.risco.RiscoLocal.add_error_handler") as mock:
        yield mock


async def test_connection_reset(
    hass: HomeAssistant, two_zone_local, mock_error_handler, setup_risco_local
) -> None:
    """Test config entry reload on connection reset."""

    callback = mock_error_handler.call_args.args[0]
    assert callback is not None

    with patch.object(hass.config_entries, "async_reload") as reload_mock:
        await callback(Exception())
        reload_mock.assert_not_awaited()

        await callback(ConnectionResetError())
        reload_mock.assert_awaited_once()
