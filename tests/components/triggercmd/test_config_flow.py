"""Define tests for the triggercmd config flow."""

from unittest.mock import MagicMock, patch

import pytest

from homeassistant import data_entry_flow
from homeassistant.components.triggercmd.config_flow import (
    ConfigFlow,
    InvalidToken,
    validate_input,
)
from homeassistant.core import HomeAssistant

valid_token_with_length_100_or_more = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6IjEyMzQ1Njc4OTBxd2VydHl1aW9wYXNkZiIsImlhdCI6MTcxOTg4MTU4M30.E4T2S4RQfuI2ww74sUkkT-wyTGrV5_VDkgUdae5yo4E"


@pytest.fixture
def mock_hub():
    """Create a mock hub."""
    with patch("homeassistant.components.triggercmd.hub.Hub") as mock_hub_class:
        mock_hub_instance = mock_hub_class.return_value
        mock_hub_instance.test_connection = MagicMock(return_value=True)
        yield mock_hub_instance


async def test_validate_input_invalid_token_length(hass: HomeAssistant) -> None:
    """Test validate_input with token length less than 100."""
    data = {"token": "short_token"}
    with pytest.raises(InvalidToken):
        await validate_input(hass, data)


async def test_validate_input_invalid_token_decode(hass: HomeAssistant) -> None:
    """Test validate_input with invalid token decode."""
    with patch("jwt.decode", return_value={"id": ""}):
        data = {"token": valid_token_with_length_100_or_more}
        with pytest.raises(InvalidToken):
            await validate_input(hass, data)


async def test_config_flow_user_init(hass: HomeAssistant) -> None:
    """Test the initial step of the config flow."""
    flow = ConfigFlow()
    flow.hass = hass

    result = await flow.async_step_user(user_input=None)
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}


async def test_config_flow_user_invalid_token(hass: HomeAssistant) -> None:
    """Test config flow with invalid token."""
    flow = ConfigFlow()
    flow.hass = hass

    user_input = {"token": "short_token"}

    result = await flow.async_step_user(user_input=user_input)
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {"token": "invalid_token"}


async def test_config_flow_user_unknown_error(hass: HomeAssistant) -> None:
    """Test config flow with an unknown error."""
    flow = ConfigFlow()
    flow.hass = hass

    user_input = {"token": valid_token_with_length_100_or_more}

    with patch("jwt.decode", side_effect=Exception):
        result = await flow.async_step_user(user_input=user_input)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {"base": "unknown"}
