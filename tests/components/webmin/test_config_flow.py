"""Test the Webmin config flow."""
from __future__ import annotations

from http import HTTPStatus
from typing import Any
from unittest.mock import AsyncMock, patch
from xmlrpc.client import Fault

from aiohttp.client_exceptions import ClientConnectionError, ClientResponseError
import pytest

from homeassistant import config_entries
from homeassistant.components.webmin.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import TEST_USER_INPUT_FULL, TEST_USER_INPUT_REQUIRED

from tests.common import load_json_object_fixture

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


@pytest.fixture
async def user_flow(hass):
    """Return a user-initiated flow after filling in host info."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None
    return result["flow_id"]


async def test_show_form_user(hass: HomeAssistant) -> None:
    """Test showing the form to select the authentication type."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] is None


@pytest.mark.parametrize(
    ("test_config", "expected_title"),
    [
        (TEST_USER_INPUT_FULL, TEST_USER_INPUT_FULL[CONF_NAME]),
        (TEST_USER_INPUT_REQUIRED, TEST_USER_INPUT_REQUIRED[CONF_HOST]),
    ],
)
async def test_form_user(
    hass: HomeAssistant,
    user_flow,
    test_config: dict[str, Any],
    expected_title: str,
    mock_setup_entry: AsyncMock,
):
    """Test a successful user initiated flow."""
    with patch(
        "homeassistant.components.webmin.config_flow.WebminInstance.update",
        return_value=load_json_object_fixture("webmin_update.json", DOMAIN),
    ):
        result = await hass.config_entries.flow.async_configure(user_flow, test_config)
        await hass.async_block_till_done()
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == expected_title
    assert result["options"] == test_config

    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("exception", "error_type"),
    [
        (
            ClientResponseError(
                request_info=None, history=None, status=HTTPStatus.UNAUTHORIZED
            ),
            "invalid_auth",
        ),
        (
            ClientResponseError(
                request_info=None, history=None, status=HTTPStatus.BAD_REQUEST
            ),
            "cannot_connect",
        ),
        (ClientConnectionError, "cannot_connect"),
        (Exception, "unknown"),
        (Fault, "unknown"),
    ],
)
async def test_form_user_errors(
    hass: HomeAssistant, user_flow, exception: Exception, error_type: str
) -> None:
    """Test we handle errors."""
    with patch(
        "homeassistant.components.webmin.config_flow.WebminInstance.update",
        side_effect=exception,
    ):
        result = await hass.config_entries.flow.async_configure(
            user_flow, TEST_USER_INPUT_FULL
        )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": error_type}

    with patch(
        "homeassistant.components.webmin.config_flow.WebminInstance.update",
        return_value=load_json_object_fixture("webmin_update.json", DOMAIN),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], TEST_USER_INPUT_FULL
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_USER_INPUT_FULL[CONF_NAME]
    assert result["options"] == TEST_USER_INPUT_FULL
