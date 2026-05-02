"""Tests Config flow for the Redgtech integration."""

from unittest.mock import MagicMock

import pytest
from redgtech_api.api import RedgtechAuthError, RedgtechConnectionError

from homeassistant.components.redgtech.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

TEST_EMAIL = "test@example.com"
TEST_PASSWORD = "123456"
FAKE_TOKEN = "fake_token"


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (RedgtechAuthError, "invalid_auth"),
        (RedgtechConnectionError, "cannot_connect"),
        (Exception("Generic error"), "unknown"),
    ],
)
async def test_user_step_errors(
    hass: HomeAssistant,
    mock_redgtech_api: MagicMock,
    side_effect: type[Exception],
    expected_error: str,
) -> None:
    """Test user step with various errors."""
    user_input = {CONF_EMAIL: TEST_EMAIL, CONF_PASSWORD: TEST_PASSWORD}
    mock_redgtech_api.login.side_effect = side_effect
    mock_redgtech_api.login.return_value = None

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=user_input
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == expected_error
    mock_redgtech_api.login.assert_called_once_with(TEST_EMAIL, TEST_PASSWORD)


async def test_user_step_creates_entry(
    hass: HomeAssistant,
    mock_redgtech_api: MagicMock,
) -> None:
    """Tests the correct creation of the entry in the configuration."""
    user_input = {CONF_EMAIL: TEST_EMAIL, CONF_PASSWORD: TEST_PASSWORD}
    mock_redgtech_api.login.reset_mock()
    mock_redgtech_api.login.return_value = FAKE_TOKEN
    mock_redgtech_api.login.side_effect = None

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=user_input
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_EMAIL
    assert result["data"] == user_input
    # Verify login was called at least once with correct parameters
    mock_redgtech_api.login.assert_any_call(TEST_EMAIL, TEST_PASSWORD)


async def test_user_step_duplicate_entry(
    hass: HomeAssistant,
    mock_redgtech_api: MagicMock,
) -> None:
    """Test attempt to add duplicate entry."""
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_EMAIL,
        data={CONF_EMAIL: TEST_EMAIL},
    )
    existing_entry.add_to_hass(hass)

    user_input = {CONF_EMAIL: TEST_EMAIL, CONF_PASSWORD: TEST_PASSWORD}

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=user_input
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    mock_redgtech_api.login.assert_not_called()


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (RedgtechAuthError, "invalid_auth"),
        (RedgtechConnectionError, "cannot_connect"),
        (Exception("Generic error"), "unknown"),
    ],
)
async def test_user_step_error_recovery(
    hass: HomeAssistant,
    mock_redgtech_api: MagicMock,
    side_effect: Exception,
    expected_error: str,
) -> None:
    """Test that the flow can recover from errors and complete successfully."""
    user_input = {CONF_EMAIL: TEST_EMAIL, CONF_PASSWORD: TEST_PASSWORD}

    # Reset mock to start fresh
    mock_redgtech_api.login.reset_mock()
    mock_redgtech_api.login.return_value = None
    mock_redgtech_api.login.side_effect = None

    # First attempt fails with error
    mock_redgtech_api.login.side_effect = side_effect
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=user_input
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == expected_error
    # Verify login was called at least once for the first attempt
    assert mock_redgtech_api.login.call_count >= 1
    first_call_count = mock_redgtech_api.login.call_count

    # Second attempt succeeds - flow recovers
    mock_redgtech_api.login.side_effect = None
    mock_redgtech_api.login.return_value = FAKE_TOKEN
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=user_input
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_EMAIL
    assert result["data"] == user_input
    # Verify login was called again for the second attempt (recovery)
    assert mock_redgtech_api.login.call_count > first_call_count
