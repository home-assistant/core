"""Test the Bresser config flow."""

from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.bresser.const import DOMAIN
from homeassistant.const import CONF_WEBHOOK_ID
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.setup import async_setup_component


async def test_create_entry(hass: HomeAssistant) -> None:
    """Test we can create a config entry."""
    await async_setup_component(hass, "http", {})

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] is None

    with patch(
        "homeassistant.components.bresser.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Bresser Weather Station"
    assert len(result["data"][CONF_WEBHOOK_ID]) == 8
    assert len(mock_setup_entry.mock_calls) == 1
