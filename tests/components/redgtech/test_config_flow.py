"""Test the Redgtech config flow."""

import pytest
from unittest.mock import AsyncMock, patch
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.components.redgtech.config_flow import RedgtechConfigFlow
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, CONF_ACCESS_TOKEN
from redgtech_api.api import RedgtechAuthError, RedgtechConnectionError

TEST_EMAIL = "test@test.com"
TEST_PASSWORD = "123456"
FAKE_TOKEN = "fake_token"


@pytest.fixture
def mock_redgtech_login():
    """Mock the RedgtechAPI login method."""
    with patch("homeassistant.components.redgtech.config_flow.RedgtechAPI.login", return_value=FAKE_TOKEN) as mock:
        yield mock


@pytest.fixture
def mock_redgtech_invalid_auth():
    """Mock the RedgtechAPI login method to raise an authentication error."""
    with patch("homeassistant.components.redgtech.config_flow.RedgtechAPI.login", side_effect=RedgtechAuthError) as mock:
        yield mock


@pytest.fixture
def mock_redgtech_cannot_connect():
    """Mock the RedgtechAPI login method to raise a connection error."""
    with patch("homeassistant.components.redgtech.config_flow.RedgtechAPI.login", side_effect=RedgtechConnectionError) as mock:
        yield mock


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (RedgtechAuthError, "invalid_auth"),
        (RedgtechConnectionError, "cannot_connect"),
        (Exception("generic error"), "unknown"),
    ],
)
async def test_user_step_errors(
    hass: HomeAssistant, side_effect, expected_error
) -> None:
    """Test handling errors during user step."""
    mock_flow = RedgtechConfigFlow()
    mock_flow.hass = hass

    user_input = {
        CONF_EMAIL: TEST_EMAIL,
        CONF_PASSWORD: TEST_PASSWORD,
    }

    with patch(
        "homeassistant.components.redgtech.config_flow.RedgtechAPI.login",
        side_effect=side_effect,
    ):
        result = await mock_flow.async_step_user(user_input)

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == expected_error


async def test_user_step_creates_entry(hass: HomeAssistant, mock_redgtech_login):
    """Test if the configuration flow creates an entry correctly."""
    mock_flow = RedgtechConfigFlow()
    mock_flow.hass = hass

    user_input = {
        CONF_EMAIL: TEST_EMAIL,
        CONF_PASSWORD: TEST_PASSWORD,
    }

    result = await mock_flow.async_step_user(user_input)

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == user_input[CONF_EMAIL]
    assert result["data"] == {
        CONF_EMAIL: TEST_EMAIL,
        CONF_PASSWORD: TEST_PASSWORD,
    }

