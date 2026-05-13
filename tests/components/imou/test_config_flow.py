"""Tests for the Imou config flow."""

from unittest.mock import AsyncMock

from pyimouapi.exceptions import (
    ConnectFailedException,
    ImouException,
    InvalidAppIdOrSecretException,
    RequestFailedException,
)
import pytest

from homeassistant.components.imou.const import (
    CONF_API_URL,
    CONF_APP_ID,
    CONF_APP_SECRET,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .util import TEST_APP_ID, TEST_APP_SECRET, USER_INPUT

from tests.common import MockConfigEntry


async def test_user_flow_success(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_api_client: AsyncMock,
) -> None:
    """Test successful user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=USER_INPUT,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == DOMAIN
    assert result["data"] == USER_INPUT
    assert result["result"].unique_id == USER_INPUT[CONF_APP_ID]
    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_flow_duplicate_entry(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_api_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test duplicate entry is aborted."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=USER_INPUT,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (ConnectFailedException("fail"), "cannot_connect"),
        (RequestFailedException("fail"), "cannot_connect"),
        (InvalidAppIdOrSecretException("fail"), "invalid_auth"),
        (ImouException("fail"), "unknown"),
    ],
)
async def test_user_flow_exception_then_recover(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_api_client: AsyncMock,
    side_effect: Exception,
    expected_error: str,
) -> None:
    """Errors map to stable keys; clearing the failure allows completing the flow."""
    mock_api_client.async_get_token.side_effect = side_effect

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=USER_INPUT,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert "errors" in result
    assert result["errors"]["base"] == expected_error

    mock_api_client.async_get_token.reset_mock(side_effect=True)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=USER_INPUT,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == DOMAIN
    assert result["data"] == USER_INPUT
    assert result["result"].unique_id == USER_INPUT[CONF_APP_ID]
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize("region", ["sg", "eu", "na", "cn"])
async def test_user_flow_success_per_region(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_api_client: AsyncMock,
    region: str,
) -> None:
    """Each supported API region can complete the config flow."""
    user_input = {
        CONF_APP_ID: f"{TEST_APP_ID}_{region}",
        CONF_APP_SECRET: TEST_APP_SECRET,
        CONF_API_URL: region,
    }

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=user_input,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == DOMAIN
    assert result["data"] == user_input
    assert result["result"].unique_id == user_input[CONF_APP_ID]
