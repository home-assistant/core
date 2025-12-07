"""Test the Anglian Water config flow."""

from unittest.mock import AsyncMock

from pyanglianwater.exceptions import (
    InvalidAccountIdError,
    SelfAssertedError,
    SmartMeterUnavailableError,
)
import pytest

from homeassistant import config_entries
from homeassistant.components.anglian_water.const import CONF_ACCOUNT_NUMBER, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import ACCESS_TOKEN, ACCOUNT_NUMBER, PASSWORD, USERNAME

from tests.common import MockConfigEntry


async def test_full_flow(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_anglian_water_authenticator: AsyncMock,
    mock_anglian_water_client: AsyncMock,
) -> None:
    """Test a full and successful config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result is not None
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_USERNAME: USERNAME,
            CONF_PASSWORD: PASSWORD,
            CONF_ACCOUNT_NUMBER: ACCOUNT_NUMBER,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == ACCOUNT_NUMBER
    assert result["data"][CONF_USERNAME] == USERNAME
    assert result["data"][CONF_PASSWORD] == PASSWORD
    assert result["data"][CONF_ACCESS_TOKEN] == ACCESS_TOKEN
    assert result["data"][CONF_ACCOUNT_NUMBER] == ACCOUNT_NUMBER
    assert result["result"].unique_id == ACCOUNT_NUMBER


async def test_already_configured(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_anglian_water_authenticator: AsyncMock,
    mock_anglian_water_client: AsyncMock,
) -> None:
    """Test that the flow aborts when the entry is already added."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result is not None
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_USERNAME: USERNAME,
            CONF_PASSWORD: PASSWORD,
            CONF_ACCOUNT_NUMBER: ACCOUNT_NUMBER,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("exception_type", "expected_error"),
    [(SelfAssertedError, "invalid_auth"), (ValueError, "unknown")],
)
async def test_auth_recover_exception(
    hass: HomeAssistant,
    mock_anglian_water_authenticator: AsyncMock,
    mock_anglian_water_client: AsyncMock,
    exception_type,
    expected_error,
) -> None:
    """Test that the flow can recover from an auth exception."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result is not None
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    mock_anglian_water_authenticator.send_login_request.side_effect = exception_type

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_USERNAME: USERNAME,
            CONF_PASSWORD: PASSWORD,
            CONF_ACCOUNT_NUMBER: ACCOUNT_NUMBER,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": expected_error}

    # Now test we can recover

    mock_anglian_water_authenticator.send_login_request.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_USERNAME: USERNAME,
            CONF_PASSWORD: PASSWORD,
            CONF_ACCOUNT_NUMBER: ACCOUNT_NUMBER,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == ACCOUNT_NUMBER
    assert result["data"][CONF_USERNAME] == USERNAME
    assert result["data"][CONF_PASSWORD] == PASSWORD
    assert result["data"][CONF_ACCESS_TOKEN] == ACCESS_TOKEN
    assert result["data"][CONF_ACCOUNT_NUMBER] == ACCOUNT_NUMBER
    assert result["result"].unique_id == ACCOUNT_NUMBER


@pytest.mark.parametrize(
    ("exception_type", "expected_error"),
    [
        (SmartMeterUnavailableError, "smart_meter_unavailable"),
        (InvalidAccountIdError, "smart_meter_unavailable"),
    ],
)
async def test_account_recover_exception(
    hass: HomeAssistant,
    mock_anglian_water_authenticator: AsyncMock,
    mock_anglian_water_client: AsyncMock,
    exception_type,
    expected_error,
) -> None:
    """Test that the flow can recover from an account related exception."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result is not None
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    mock_anglian_water_client.validate_smart_meter.side_effect = exception_type

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_USERNAME: USERNAME,
            CONF_PASSWORD: PASSWORD,
            CONF_ACCOUNT_NUMBER: ACCOUNT_NUMBER,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": expected_error}

    # Now test we can recover

    mock_anglian_water_client.validate_smart_meter.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_USERNAME: USERNAME,
            CONF_PASSWORD: PASSWORD,
            CONF_ACCOUNT_NUMBER: ACCOUNT_NUMBER,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == ACCOUNT_NUMBER
    assert result["data"][CONF_USERNAME] == USERNAME
    assert result["data"][CONF_PASSWORD] == PASSWORD
    assert result["data"][CONF_ACCESS_TOKEN] == ACCESS_TOKEN
    assert result["data"][CONF_ACCOUNT_NUMBER] == ACCOUNT_NUMBER
    assert result["result"].unique_id == ACCOUNT_NUMBER
