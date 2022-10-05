"""Test the Flexit Nordic (BACnet) config flow."""
from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.flexit_bacnet.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None

    with patch("flexit_bacnet.device.FlexitBACnet.is_valid", return_value=True,), patch(
        "flexit_bacnet.device.FlexitBACnet.serial_number",
        property(lambda _: "0000-0001"),
    ), patch(
        "homeassistant.components.flexit_bacnet.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "address": "1.1.1.1",
                "device_id": 2,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Flexit Nordic: 0000-0001"
    assert result2["data"] == {
        "address": "1.1.1.1",
        "device_id": 2,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "flexit_bacnet.device.FlexitBACnet.is_valid",
        return_value=False,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "address": "1.1.1.1",
                "device_id": 2,
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_unexpected_error(hass: HomeAssistant) -> None:
    """Test we handle unexpected errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "flexit_bacnet.device.FlexitBACnet.is_valid",
        side_effect=ConnectionError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "address": "1.1.1.1",
                "device_id": 2,
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}
