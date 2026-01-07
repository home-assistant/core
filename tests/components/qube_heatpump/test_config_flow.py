"""Test the Qube Heat Pump config flow."""

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant import config_entries
from homeassistant.components.qube_heatpump.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_form(
    hass: HomeAssistant, mock_setup_entry: MagicMock, mock_hub: MagicMock
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert not result["errors"]

    with patch(
        "homeassistant.components.qube_heatpump.config_flow.asyncio.open_connection",
        return_value=(AsyncMock(), MagicMock()),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.2.3.4",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Qube Heat Pump (1.2.3.4)"
    assert result2["data"] == {
        "host": "1.2.3.4",
        "port": 502,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(hass: HomeAssistant, mock_hub: MagicMock) -> None:
    """Test we handle cannot connect error."""
    mock_hub.async_connect.side_effect = OSError

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.qube_heatpump.config_flow.asyncio.open_connection",
        side_effect=OSError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}
