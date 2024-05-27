"""Test the One-Time Password (OTP) config flow."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant import config_entries
from homeassistant.components.otp.const import DOMAIN
from homeassistant.const import CONF_CODE, CONF_NAME, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

TEST_DATA = {
    CONF_NAME: "OTP Sensor",
    CONF_TOKEN: "TOKEN_A",
}

TEST_DATA_2 = {
    CONF_NAME: "OTP Sensor",
    CONF_TOKEN: "",
}


@pytest.mark.parametrize(
    ("expected_token", "test_user_input"),
    [
        ("TOKEN_A", TEST_DATA),
        ("TOKEN_B", TEST_DATA_2),
    ],
)
async def test_form(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_pyotp: MagicMock,
    mock_qr: MagicMock,
    expected_token: str,
    test_user_input: dict[str, str],
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        test_user_input,
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "confirm"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_CODE: "123456"},
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "OTP Sensor"
    assert result["data"] == {CONF_TOKEN: expected_token}
    assert len(mock_setup_entry.mock_calls) == 1


async def test_errors_and_recover(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_pyotp: MagicMock,
    mock_qr: MagicMock,
) -> None:
    """Test errors and recover."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        TEST_DATA,
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "confirm"
    assert result["errors"] == {}

    mock_pyotp.TOTP().verify.return_value = False
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_CODE: "000000"},
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "confirm"
    assert result["errors"] == {"base": "invalid_code"}

    mock_pyotp.TOTP().verify.side_effect = ValueError
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_CODE: "000000"},
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "confirm"
    assert result["errors"] == {"base": "unknown"}

    mock_pyotp.TOTP().verify.return_value = True
    mock_pyotp.TOTP().verify.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_CODE: "123456"},
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "OTP Sensor"
    assert result["data"] == {CONF_TOKEN: "TOKEN_A"}
    assert len(mock_setup_entry.mock_calls) == 1
