"""Test the One-Time Password (OTP) config flow."""

import binascii
from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.components.otp.const import CONF_NEW_TOKEN, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_CODE, CONF_NAME, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

TEST_DATA = {
    CONF_NAME: "OTP Sensor",
    CONF_TOKEN: "2FX5 FBSY RE6V EC2F SHBQ CRKO 2GND VZ52",
}
TEST_DATA_RESULT = {
    CONF_NAME: "OTP Sensor",
    CONF_TOKEN: "2FX5FBSYRE6VEC2FSHBQCRKO2GNDVZ52",
}

TEST_DATA_2 = {
    CONF_NAME: "OTP Sensor",
    CONF_NEW_TOKEN: True,
}

TEST_DATA_3 = {
    CONF_NAME: "OTP Sensor",
    CONF_TOKEN: "",
}


@pytest.mark.usefixtures("mock_pyotp")
async def test_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        TEST_DATA,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "OTP Sensor"
    assert result["data"] == TEST_DATA_RESULT
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (binascii.Error, "invalid_token"),
        (IndexError, "unknown"),
    ],
)
async def test_errors_and_recover(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_pyotp: MagicMock,
    exception: Exception,
    error: str,
) -> None:
    """Test errors and recover."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    mock_pyotp.TOTP().now.side_effect = exception
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=TEST_DATA,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_pyotp.TOTP().now.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=TEST_DATA,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "OTP Sensor"
    assert result["data"] == TEST_DATA_RESULT
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_pyotp")
async def test_generate_new_token(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test form generate new token."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        TEST_DATA_2,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}
    assert result["step_id"] == "confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_CODE: "123456"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "OTP Sensor"
    assert result["data"] == TEST_DATA_RESULT
    assert len(mock_setup_entry.mock_calls) == 1


async def test_generate_new_token_errors(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_pyotp
) -> None:
    """Test input validation errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        TEST_DATA_3,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_token"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        TEST_DATA_2,
    )
    mock_pyotp.TOTP().verify.return_value = False
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_CODE: "123456"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_code"}

    mock_pyotp.TOTP().verify.return_value = True
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_CODE: "123456"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "OTP Sensor"
    assert result["data"] == TEST_DATA_RESULT
    assert len(mock_setup_entry.mock_calls) == 1
