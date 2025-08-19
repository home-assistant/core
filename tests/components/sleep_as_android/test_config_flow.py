"""Test the Sleep as Android config flow."""

from unittest.mock import AsyncMock, patch

from homeassistant.components.sleep_as_android.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_WEBHOOK_ID
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    with (
        patch(
            "homeassistant.components.webhook.async_generate_id",
            return_value="webhook_id",
        ),
        patch(
            "homeassistant.components.webhook.async_generate_url",
            return_value="http://example.com:8123",
        ),
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Sleep as Android"
    assert result["data"] == {
        "cloudhook": False,
        CONF_WEBHOOK_ID: "webhook_id",
    }
    assert len(mock_setup_entry.mock_calls) == 1
