"""Tests for the DVLA config flow."""

from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.dvla.const import CONF_CALENDARS, CONF_REG_NUMBER, DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_form(hass: HomeAssistant) -> None:
    """Test that the form is served."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_create_entry(hass: HomeAssistant) -> None:
    """Test creating an entry from user input."""
    with (
        patch(
            "homeassistant.components.dvla.config_flow.validate_input",
            return_value={"title": "AB12CDE"},
        ),
        patch(
            "homeassistant.components.dvla.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={
                CONF_REG_NUMBER: "AB12CDE",
                CONF_CALENDARS: ["None"],
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "AB12CDE"
    assert result["data"][CONF_REG_NUMBER] == "AB12CDE"

    await hass.async_block_till_done()
    assert len(mock_setup_entry.mock_calls) == 1
