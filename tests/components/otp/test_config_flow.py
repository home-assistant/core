"""Test the One-Time Password (OTP) config flow."""

import binascii
from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.components.otp.const import DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_NAME, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

TEST_DATA = {
    CONF_NAME: "OTP Sensor",
    CONF_TOKEN: "TOKEN_A",
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
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "OTP Sensor"
    assert result["data"] == TEST_DATA
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (binascii.Error, "invalid_code"),
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
    assert result["data"] == TEST_DATA
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_pyotp", "mock_setup_entry")
async def test_flow_import(hass: HomeAssistant) -> None:
    """Test that we can import a YAML config."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=TEST_DATA,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "OTP Sensor"
    assert result["data"] == TEST_DATA
