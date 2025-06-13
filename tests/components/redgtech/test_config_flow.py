"""Tests Config flow for the Redgtech integration."""

import pytest
from unittest.mock import AsyncMock, patch
from tests.common import MockConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.components.redgtech.const import DOMAIN
from redgtech_api.api import RedgtechAuthError, RedgtechConnectionError


TEST_EMAIL = "test@example.com"
TEST_PASSWORD = "123456"
FAKE_TOKEN = "fake_token"


@pytest.fixture
def mock_redgtech_api():
    """Mock RedgtechAPI class."""
    with patch("homeassistant.components.redgtech.config_flow.RedgtechAPI") as mock_api_class:
        mock_api = AsyncMock()
        mock_api.login.return_value = FAKE_TOKEN
        mock_api_class.return_value = mock_api
        yield mock_api


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (RedgtechAuthError, "invalid_auth"),
        (RedgtechConnectionError, "cannot_connect"),
        (Exception("Generic error"), "unknown"),
    ],
)
async def test_user_step_errors(hass: HomeAssistant, side_effect, expected_error):
    """Tests error handling at the user's step."""
    user_input = {CONF_EMAIL: TEST_EMAIL, CONF_PASSWORD: TEST_PASSWORD}

    with patch("homeassistant.components.redgtech.config_flow.RedgtechAPI") as mock_api_class:
        mock_api = AsyncMock()
        mock_api.login.side_effect = side_effect
        mock_api_class.return_value = mock_api

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}, data=user_input
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == expected_error
    mock_api.login.assert_called_once_with(TEST_EMAIL, TEST_PASSWORD)


async def test_user_step_creates_entry(hass: HomeAssistant, mock_redgtech_api):
    """Tests the correct creation of the entry in the configuration."""
    user_input = {CONF_EMAIL: TEST_EMAIL, CONF_PASSWORD: TEST_PASSWORD}

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}, data=user_input
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_EMAIL
    assert result["data"] == user_input
    mock_redgtech_api.login.assert_called_once_with(TEST_EMAIL, TEST_PASSWORD)


async def test_user_step_duplicate_entry(hass: HomeAssistant, mock_redgtech_api):
    """Test attempt to add duplicate entry."""
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_EMAIL,
        data={CONF_EMAIL: TEST_EMAIL},
    )
    existing_entry.add_to_hass(hass)

    user_input = {CONF_EMAIL: TEST_EMAIL, CONF_PASSWORD: TEST_PASSWORD}

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}, data=user_input
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    # Login should not be called if already configured
    mock_redgtech_api.login.assert_not_called()