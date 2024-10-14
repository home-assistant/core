"""Test the AWS Data config flow."""

from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.aws_data.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import USER_DATA


async def test_show_user_form(hass: HomeAssistant) -> None:
    """Test that the setup form is served."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    with patch(
        "homeassistant.components.aws_data.config_flow.AWSDataClient.serviceCall",
        return_value={
            "Error": {"Code": "UnauthorizedOperation", "Message": "Unauthorized"}
        },
    ):
        user_form = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            USER_DATA,
        )
        await hass.async_block_till_done()

    assert user_form["type"] is FlowResultType.FORM
    assert user_form["step_id"] == "user"
    assert user_form["errors"] == {
        "base": "UnauthorizedOperation",
        "message": "Unauthorized",
    }


async def test_service_show_form(hass: HomeAssistant) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    with patch(
        "homeassistant.components.aws_data.config_flow.AWSDataClient.serviceCall",
        return_value={},
    ):
        user_form = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            USER_DATA,
        )
        await hass.async_block_till_done()

    assert user_form["type"] is FlowResultType.FORM
    assert user_form["step_id"] == "service"
    assert user_form["errors"] == {}
