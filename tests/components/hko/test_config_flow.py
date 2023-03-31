"""Test the Hong Kong Observatory config flow."""
from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.hko.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.hko.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "location": "Hong Kong Observatory",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Hong Kong Observatory"
    assert result2["data"] == {
        "location": "Hong Kong Observatory",
    }
    assert len(mock_setup_entry.mock_calls) == 1
