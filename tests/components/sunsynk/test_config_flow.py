"""Test the Sunsynk config flow."""
from unittest.mock import patch

from sunsynk.inverter import Inverter

from homeassistant import config_entries
from homeassistant.components.sunsynk.config_flow import CannotConnect, InvalidAuth
from homeassistant.components.sunsynk.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

SUNSYNK_HUB_AUTHENTICATE = (
    "homeassistant.components.sunsynk.config_flow.SunsynkHub.authenticate"
)
SUNSYNK_HUB_GET_INVERTERS = (
    "homeassistant.components.sunsynk.config_flow.SunsynkHub.get_inverters"
)


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None

    with patch(SUNSYNK_HUB_AUTHENTICATE, return_value=True), patch(
        SUNSYNK_HUB_GET_INVERTERS, return_value=[Inverter({"sn": "INV123"})]
    ), patch(
        "homeassistant.components.sunsynk.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Inverter INV123"
    assert result2["data"] == {
        "username": "test-username",
        "password": "test-password",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(SUNSYNK_HUB_AUTHENTICATE, side_effect=InvalidAuth):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(SUNSYNK_HUB_AUTHENTICATE, side_effect=CannotConnect):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}
