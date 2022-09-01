"""Test the Ecowitt Weather Station config flow."""
from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.ecowitt.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.setup import async_setup_component


async def test_create_entry(hass: HomeAssistant) -> None:
    """Test we can create a config entry."""
    await async_setup_component(hass, "http", {})

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.ecowitt.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Ecowitt"
    assert result2["data"] == {
        "webhook_id": result2["description_placeholders"]["path"].split("/")[-1],
    }
    assert len(mock_setup_entry.mock_calls) == 1
