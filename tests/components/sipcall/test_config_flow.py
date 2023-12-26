"""Test the SIP Call config flow."""
from unittest.mock import AsyncMock

from homeassistant import config_entries
from homeassistant.components.sipcall.const import (
    CONF_SIP_DOMAIN,
    CONF_SIP_SERVER,
    DOMAIN,
)
from homeassistant.const import CONF_NAME, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_SIP_SERVER: "1.1.1.1",
            CONF_SIP_DOMAIN: "sipgate.de",
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "test-username_sipgate.de"
    assert result["data"] == {
        CONF_NAME: "test-username_sipgate.de",
        CONF_SIP_SERVER: "1.1.1.1",
        CONF_SIP_DOMAIN: "sipgate.de",
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "test-password",
    }
    assert len(mock_setup_entry.mock_calls) == 1
