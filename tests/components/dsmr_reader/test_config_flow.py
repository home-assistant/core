"""Tests for the config flow."""
from homeassistant.components.dsmr_reader.const import DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import (
    RESULT_TYPE_ABORT,
    RESULT_TYPE_CREATE_ENTRY,
    RESULT_TYPE_FORM,
)


async def test_import_step(hass: HomeAssistant):
    """Test the import step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
    )
    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "DSMR Reader"

    second_result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
    )
    assert second_result["type"] == RESULT_TYPE_ABORT
    assert second_result["reason"] == "single_instance_allowed"


async def test_user_step_with_mqtt(hass: HomeAssistant):
    """Test the user step call with mqtt available."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "confirm"
    assert result["errors"] is None

    config_result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert config_result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert config_result["title"] == "DSMR Reader"

    duplicate_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert duplicate_result["type"] == RESULT_TYPE_ABORT
    assert duplicate_result["reason"] == "single_instance_allowed"
