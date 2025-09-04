"""Test the Immich config flow."""

from unittest.mock import AsyncMock, Mock

from aiohttp import ClientError
from aioimmich.exceptions import ImmichUnauthorizedError
import pytest

from homeassistant.components.immich.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_KEY, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import MOCK_CONFIG_ENTRY_DATA, MOCK_USER_DATA

from tests.common import MockConfigEntry


async def test_step_user(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_immich: Mock
) -> None:
    """Test a user initiated config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_USER_DATA,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "user"
    assert result["data"] == MOCK_CONFIG_ENTRY_DATA
    assert result["result"].unique_id == "e7ef5713-9dab-4bd4-b899-715b0ca4379e"
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (
            ImmichUnauthorizedError(
                {
                    "message": "Invalid API key",
                    "error": "Unauthenticated",
                    "statusCode": 401,
                    "correlationId": "abcdefg",
                }
            ),
            "invalid_auth",
        ),
        (ClientError, "cannot_connect"),
        (Exception, "unknown"),
    ],
)
async def test_step_user_error_handling(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_immich: Mock,
    exception: Exception,
    error: str,
) -> None:
    """Test a user initiated config flow with errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    mock_immich.users.async_get_my_user.side_effect = exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_USER_DATA,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": error}

    mock_immich.users.async_get_my_user.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_USER_DATA,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_step_user_invalid_url(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_immich: Mock
) -> None:
    """Test a user initiated config flow with errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {**MOCK_USER_DATA, CONF_URL: "hts://invalid"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {CONF_URL: "invalid_url"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_USER_DATA,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_already_configured(
    hass: HomeAssistant, mock_immich: Mock, mock_config_entry: MockConfigEntry
) -> None:
    """Test starting a flow by user when already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_USER_DATA,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth_flow(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_immich: Mock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reauthentication flow."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_API_KEY: "other_fake_api_key",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_API_KEY] == "other_fake_api_key"


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (
            ImmichUnauthorizedError(
                {
                    "message": "Invalid API key",
                    "error": "Unauthenticated",
                    "statusCode": 401,
                    "correlationId": "abcdefg",
                }
            ),
            "invalid_auth",
        ),
        (ClientError, "cannot_connect"),
        (Exception, "unknown"),
    ],
)
async def test_reauth_flow_error_handling(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_immich: Mock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    error: str,
) -> None:
    """Test reauthentication flow with errors."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    mock_immich.users.async_get_my_user.side_effect = exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_API_KEY: "other_fake_api_key",
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": error}

    mock_immich.users.async_get_my_user.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_API_KEY: "other_fake_api_key",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_API_KEY] == "other_fake_api_key"
    assert len(mock_setup_entry.mock_calls) == 1


async def test_reauth_flow_mismatch(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_immich: Mock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reauthentication flow with mis-matching unique id."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    mock_immich.users.async_get_my_user.return_value.user_id = "other_user_id"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_API_KEY: "other_fake_api_key",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"
