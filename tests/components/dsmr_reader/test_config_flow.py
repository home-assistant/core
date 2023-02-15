"""Tests for the config flow."""
from homeassistant.components.dsmr_reader.const import DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_import_step(hass: HomeAssistant) -> None:
    """Test the import step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "DSMR Reader"

    second_result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
    )
    assert second_result["type"] == FlowResultType.ABORT
    assert second_result["reason"] == "single_instance_allowed"


async def test_user_step(hass: HomeAssistant) -> None:
    """Test the user step call."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "confirm"
    assert result["errors"] is None

    config_result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert config_result["type"] == FlowResultType.CREATE_ENTRY
    assert config_result["title"] == "DSMR Reader"

    duplicate_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert duplicate_result["type"] == FlowResultType.ABORT
    assert duplicate_result["reason"] == "single_instance_allowed"
