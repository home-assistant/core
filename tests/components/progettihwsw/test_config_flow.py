"""Test the ProgettiHWSW Automation config flow."""
from homeassistant import config_entries, setup
from homeassistant.components.progettihwsw.config_flow import UnexistingBoard
from homeassistant.components.progettihwsw.const import DOMAIN

from tests.async_mock import patch


async def test_form(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"host": "2.238.194.163", "port": 8085},
    )

    assert result2["type"] == "form"
    assert result2["errors"] == {}


async def test_form_unexisting_board(hass):
    """Test we handle unexisting board."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.progettihwsw.config_flow.EntryValidator.check_board_validity",
        side_effect=UnexistingBoard,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "1.1.1.1", "port": 80},
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "unexisting_board"}
