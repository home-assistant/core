"""Tests for the NASweb integration."""

from unittest.mock import MagicMock, patch

import pytest
from webio_api.api_client import AuthError

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers.network import NoURLAvailableError

from .conftest import BASE_NASWEB_DATA

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("mock_attr", "mock_value", "expected_translation_key"),
    [
        (
            "refresh_device_info",
            False,
            "config_entry_error_internal_error",
        ),
        (
            "get_serial_number",
            None,
            "config_entry_error_internal_error",
        ),
        (
            "get_serial_number",
            "different_serial",
            "config_entry_error_serial_mismatch",
        ),
        (
            "status_subscription",
            False,
            "config_entry_error_internal_error",
        ),
    ],
)
async def test_setup_entry_config_entry_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webio_api: MagicMock,
    mock_attr: str,
    mock_value: object,
    expected_translation_key: str,
) -> None:
    """Test setup entry raises ConfigEntryError with correct translation key."""
    getattr(mock_webio_api, mock_attr).return_value = mock_value
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert mock_config_entry.error_reason_translation_key == expected_translation_key


async def test_setup_entry_auth_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webio_api: MagicMock,
) -> None:
    """Test setup entry raises ConfigEntryError on authentication failure."""
    mock_webio_api.check_connection.side_effect = AuthError
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert (
        mock_config_entry.error_reason_translation_key
        == "config_entry_error_invalid_authentication"
    )


async def test_setup_entry_no_status_update(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webio_api: MagicMock,
) -> None:
    """Test setup entry raises ConfigEntryError when no status update received."""
    with patch(
        BASE_NASWEB_DATA + "NotificationCoordinator.check_connection",
        return_value=False,
    ):
        mock_config_entry.add_to_hass(hass)

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert (
        mock_config_entry.error_reason_translation_key
        == "config_entry_error_no_status_update"
    )


async def test_setup_entry_missing_internal_url(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webio_api: MagicMock,
) -> None:
    """Test setup entry raises ConfigEntryError when internal URL is missing."""
    with patch(
        BASE_NASWEB_DATA + "NASwebData.get_webhook_url",
        side_effect=NoURLAvailableError,
    ):
        mock_config_entry.add_to_hass(hass)

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert (
        mock_config_entry.error_reason_translation_key
        == "config_entry_error_missing_internal_url"
    )
