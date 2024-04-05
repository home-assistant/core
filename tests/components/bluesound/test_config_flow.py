"""Test the Bluesound config flow."""

from unittest.mock import AsyncMock

from homeassistant import config_entries
from homeassistant.components.bluesound.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "1.1.1.1",
            CONF_NAME: "test-name",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "test-name"
    assert result["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_PORT: 11000,
        CONF_NAME: "test-name",
    }
    assert len(mock_setup_entry.mock_calls) == 1
