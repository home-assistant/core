"""Test the Green Planet Energy config flow."""

from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.green_planet_energy.config_flow import CannotConnect
from homeassistant.components.green_planet_energy.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_form(hass: HomeAssistant, mock_api) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.green_planet_energy.config_flow.prepare_config_entry",
        return_value={"title": "Green Planet Energy"},
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
        await hass.async_block_till_done()

        assert result2["type"] is FlowResultType.CREATE_ENTRY
        assert result2["title"] == "Green Planet Energy"
        assert result2["data"] == {}


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    with patch(
        "homeassistant.components.green_planet_energy.config_flow.prepare_config_entry",
        side_effect=CannotConnect,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )

        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "cannot_connect"}


async def test_form_unexpected_exception(hass: HomeAssistant) -> None:
    """Test we handle unexpected exception."""
    with patch(
        "homeassistant.components.green_planet_energy.config_flow.prepare_config_entry",
        side_effect=Exception,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )

        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "unknown"}
