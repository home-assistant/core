"""Test the One-Time Password (OTP) config flow."""

from unittest.mock import AsyncMock

from homeassistant import config_entries
from homeassistant.components.otp.const import DOMAIN
from homeassistant.const import CONF_NAME, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_form(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "OTP Sensor",
            CONF_TOKEN: "TOKEN_A",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "OTP Sensor"
    assert result["data"] == {
        CONF_NAME: "OTP Sensor",
        CONF_TOKEN: "TOKEN_A",
    }
    assert len(mock_setup_entry.mock_calls) == 1
