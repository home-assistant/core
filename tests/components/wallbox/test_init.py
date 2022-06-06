"""Test Wallbox Init Component."""
from http import HTTPStatus
from unittest.mock import Mock, patch

from requests.exceptions import HTTPError

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import (
    DOMAIN,
    entry,
    setup_integration,
    setup_integration_charger_status_connection_error,
    setup_integration_connection_error,
    setup_integration_invalidauth_error,
    setup_integration_read_only,
)


async def test_wallbox_setup_unload_entry(hass: HomeAssistant) -> None:
    """Test Wallbox Unload."""

    await setup_integration(hass)
    assert entry.state == ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state == ConfigEntryState.NOT_LOADED


async def test_wallbox_unload_entry_connection_error(hass: HomeAssistant) -> None:
    """Test Wallbox Unload Connection Error."""

    await setup_integration_connection_error(hass)
    assert entry.state == ConfigEntryState.SETUP_ERROR

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state == ConfigEntryState.NOT_LOADED


async def test_wallbox_refresh_failed_invalid_auth(hass: HomeAssistant) -> None:
    """Test Wallbox setup with authentication error."""

    await setup_integration(hass)
    assert entry.state == ConfigEntryState.LOADED

    with patch(
        "wallbox.Wallbox.authenticate",
        return_value=None,
        side_effect=HTTPError(
            Mock(status=HTTPStatus.FORBIDDEN),
            response=Mock(status_code=HTTPStatus.FORBIDDEN),
        ),
    ), patch(
        "wallbox.Wallbox.setMaxChargingCurrent",
        return_value=None,
        side_effect=HTTPError(
            Mock(status=HTTPStatus.FORBIDDEN),
            response=Mock(status_code=HTTPStatus.FORBIDDEN),
        ),
    ):
        wallbox = hass.data[DOMAIN][entry.entry_id]

        await wallbox.async_refresh()

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state == ConfigEntryState.NOT_LOADED


async def test_wallbox_refresh_failed_connection_error(hass: HomeAssistant) -> None:
    """Test Wallbox setup with connection error."""

    await setup_integration(hass)
    assert entry.state == ConfigEntryState.LOADED

    with patch("wallbox.Wallbox.authenticate", return_value=None,), patch(
        "wallbox.Wallbox.setMaxChargingCurrent",
        return_value=None,
        side_effect=HTTPError(
            Mock(status=HTTPStatus.FORBIDDEN),
            response=Mock(status_code=HTTPStatus.FORBIDDEN),
        ),
    ):

        wallbox = hass.data[DOMAIN][entry.entry_id]

        await wallbox.async_refresh()

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state == ConfigEntryState.NOT_LOADED


async def test_wallbox_refresh_failed_read_only(hass: HomeAssistant) -> None:
    """Test Wallbox setup for read-only user."""

    await setup_integration_read_only(hass)
    assert entry.state == ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state == ConfigEntryState.NOT_LOADED


async def test_wallbox_refresh_invalid_auth(hass: HomeAssistant) -> None:
    """Test Wallbox setup for read-only user."""

    await setup_integration_invalidauth_error(hass)

    assert entry.state == ConfigEntryState.SETUP_ERROR

    assert await hass.config_entries.async_unload(entry.entry_id)

    assert entry.state == ConfigEntryState.NOT_LOADED


async def test_wallbox_refresh_charger_data_connection_error(
    hass: HomeAssistant,
) -> None:
    """Test Wallbox setup for connection error on charger status."""

    await setup_integration_charger_status_connection_error(hass)

    assert entry.state == ConfigEntryState.SETUP_RETRY

    assert await hass.config_entries.async_unload(entry.entry_id)

    assert entry.state == ConfigEntryState.NOT_LOADED
