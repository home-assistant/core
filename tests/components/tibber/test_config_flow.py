"""Tests for Tibber config flow."""
from asyncio import TimeoutError
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

from aiohttp import ClientError
import pytest
from tibber import FatalHttpException, InvalidLogin, RetryableHttpException

from homeassistant import config_entries
from homeassistant.components.recorder import Recorder
from homeassistant.components.tibber.config_flow import (
    ERR_CLIENT,
    ERR_TIMEOUT,
    ERR_TOKEN,
)
from homeassistant.components.tibber.const import DOMAIN
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


@pytest.fixture(name="tibber_setup", autouse=True)
def tibber_setup_fixture():
    """Patch tibber setup entry."""
    with patch("homeassistant.components.tibber.async_setup_entry", return_value=True):
        yield


async def test_show_config_form(recorder_mock: Recorder, hass: HomeAssistant) -> None:
    """Test show configuration form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_create_entry(recorder_mock: Recorder, hass: HomeAssistant) -> None:
    """Test create entry from user input."""
    test_data = {
        CONF_ACCESS_TOKEN: "valid",
    }

    unique_user_id = "unique_user_id"
    title = "title"

    tibber_mock = MagicMock()
    type(tibber_mock).update_info = AsyncMock(return_value=True)
    type(tibber_mock).user_id = PropertyMock(return_value=unique_user_id)
    type(tibber_mock).name = PropertyMock(return_value=title)

    with patch("tibber.Tibber", return_value=tibber_mock):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=test_data
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == title
    assert result["data"] == test_data


@pytest.mark.parametrize(
    ("exception", "expected_error"),
    [
        (TimeoutError, ERR_TIMEOUT),
        (ClientError, ERR_CLIENT),
        (InvalidLogin(401), ERR_TOKEN),
        (RetryableHttpException(503), ERR_CLIENT),
        (FatalHttpException(404), ERR_CLIENT),
    ],
)
async def test_create_entry_exceptions(recorder_mock, hass, exception, expected_error):
    """Test create entry from user input."""
    test_data = {
        CONF_ACCESS_TOKEN: "valid",
    }

    unique_user_id = "unique_user_id"
    title = "title"

    tibber_mock = MagicMock()
    type(tibber_mock).update_info = AsyncMock(side_effect=exception)
    type(tibber_mock).user_id = PropertyMock(return_value=unique_user_id)
    type(tibber_mock).name = PropertyMock(return_value=title)

    with patch("tibber.Tibber", return_value=tibber_mock):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=test_data
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"][CONF_ACCESS_TOKEN] == expected_error


async def test_flow_entry_already_exists(recorder_mock, hass, config_entry):
    """Test user input for config_entry that already exists."""
    test_data = {
        CONF_ACCESS_TOKEN: "valid",
    }

    with patch("tibber.Tibber.update_info", return_value=None):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=test_data
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"
