"""Test the Matter config flow."""
from unittest.mock import patch

from matter_server.client.exceptions import CannotConnect

from homeassistant import config_entries
from homeassistant.components.matter.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_user_create_entry(hass: HomeAssistant) -> None:
    """Test user step create entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None

    with patch("homeassistant.components.matter.config_flow.Client.connect",), patch(
        "homeassistant.components.matter.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "url": "http://172.30.32.1:5580/chip_ws",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "http://172.30.32.1:5580/chip_ws"
    assert result2["data"] == {
        "url": "http://172.30.32.1:5580/chip_ws",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_cannot_connect(hass: HomeAssistant) -> None:
    """Test user step cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.matter.config_flow.Client.connect",
        side_effect=CannotConnect(Exception("Boom")),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "url": "http://172.30.32.1:5580/chip_ws",
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}
