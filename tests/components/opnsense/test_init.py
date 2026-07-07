"""Tests for the opnsense integration setup."""

from unittest import mock

from aiopnsense import (
    OPNsenseBelowMinFirmware,
    OPNsenseConnectionError,
    OPNsenseInvalidAuth,
    OPNsenseInvalidURL,
    OPNsensePrivilegeMissing,
    OPNsenseSSLError,
    OPNsenseTimeoutError,
    OPNsenseUnknownFirmware,
)
import pytest

from homeassistant.components.opnsense.const import (
    CONF_API_SECRET,
    CONF_TRACKER_INTERFACES,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_API_KEY, CONF_URL, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("exc", "expected_state", "expected_translation_key"),
    [
        (OPNsenseUnknownFirmware, ConfigEntryState.SETUP_ERROR, "unknown_firmware"),
        (OPNsenseBelowMinFirmware, ConfigEntryState.SETUP_ERROR, "firmware_too_old"),
        (OPNsenseInvalidURL, ConfigEntryState.SETUP_ERROR, "invalid_url"),
        (OPNsenseTimeoutError, ConfigEntryState.SETUP_RETRY, "timeout_connecting"),
        (OPNsenseSSLError, ConfigEntryState.SETUP_ERROR, "ssl_error"),
        (OPNsenseInvalidAuth, ConfigEntryState.SETUP_ERROR, "invalid_auth"),
        (OPNsensePrivilegeMissing, ConfigEntryState.SETUP_ERROR, "privilege_missing"),
        (OPNsenseConnectionError, ConfigEntryState.SETUP_RETRY, "cannot_connect"),
    ],
)
async def test_setup_entry_exceptions(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_opnsense_client: mock.AsyncMock,
    exc: type[Exception],
    expected_state: ConfigEntryState,
    expected_translation_key: str,
) -> None:
    """Test async_setup_entry surfaces translation-keyed errors."""
    mock_opnsense_client.validate.side_effect = exc

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is expected_state
    assert mock_config_entry.error_reason_translation_key == expected_translation_key
    assert mock_config_entry.error_reason_translation_placeholders == {
        "url": mock_config_entry.data[CONF_URL]
    }


async def test_setup_entry_tracker_interface_not_found(
    hass: HomeAssistant,
    mock_opnsense_client: mock.AsyncMock,
) -> None:
    """Test async_setup_entry rejects unknown tracker interfaces."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_URL: "http://router.lan/api",
            CONF_API_KEY: "key",
            CONF_API_SECRET: "secret",
            CONF_VERIFY_SSL: False,
            CONF_TRACKER_INTERFACES: ["NOPE"],
        },
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert entry.error_reason_translation_key == "tracker_interface_not_found"
    assert entry.error_reason_translation_placeholders == {
        "interface": "NOPE",
        "known": "WAN, LAN",
    }
