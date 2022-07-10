"""Define tests for the GeoNet NZ Volcano config flow."""
from datetime import timedelta
from unittest.mock import patch

from homeassistant import data_entry_flow
from homeassistant.components.geonetnz_volcano import config_flow
from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_RADIUS,
    CONF_SCAN_INTERVAL,
    CONF_UNIT_SYSTEM,
)


async def test_duplicate_error(hass, config_entry):
    """Test that errors are shown when duplicates are added."""
    conf = {CONF_LATITUDE: -41.2, CONF_LONGITUDE: 174.7, CONF_RADIUS: 25}

    config_entry.add_to_hass(hass)
    flow = config_flow.GeonetnzVolcanoFlowHandler()
    flow.hass = hass

    result = await flow.async_step_user(user_input=conf)
    assert result["errors"] == {"base": "already_configured"}


async def test_show_form(hass):
    """Test that the form is served with no input."""
    flow = config_flow.GeonetnzVolcanoFlowHandler()
    flow.hass = hass

    result = await flow.async_step_user(user_input=None)

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_step_import(hass):
    """Test that the import step works."""
    conf = {
        CONF_LATITUDE: -41.2,
        CONF_LONGITUDE: 174.7,
        CONF_RADIUS: 25,
        CONF_UNIT_SYSTEM: "metric",
        CONF_SCAN_INTERVAL: timedelta(minutes=4),
    }

    flow = config_flow.GeonetnzVolcanoFlowHandler()
    flow.hass = hass

    with patch(
        "homeassistant.components.geonetnz_volcano.async_setup_entry", return_value=True
    ), patch(
        "homeassistant.components.geonetnz_volcano.async_setup", return_value=True
    ):
        result = await flow.async_step_import(import_config=conf)
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "-41.2, 174.7"
    assert result["data"] == {
        CONF_LATITUDE: -41.2,
        CONF_LONGITUDE: 174.7,
        CONF_RADIUS: 25,
        CONF_UNIT_SYSTEM: "metric",
        CONF_SCAN_INTERVAL: 240.0,
    }


async def test_step_user(hass):
    """Test that the user step works."""
    hass.config.latitude = -41.2
    hass.config.longitude = 174.7
    conf = {CONF_RADIUS: 25}

    flow = config_flow.GeonetnzVolcanoFlowHandler()
    flow.hass = hass

    with patch(
        "homeassistant.components.geonetnz_volcano.async_setup_entry", return_value=True
    ), patch(
        "homeassistant.components.geonetnz_volcano.async_setup", return_value=True
    ):
        result = await flow.async_step_user(user_input=conf)
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "-41.2, 174.7"
    assert result["data"] == {
        CONF_LATITUDE: -41.2,
        CONF_LONGITUDE: 174.7,
        CONF_RADIUS: 25,
        CONF_UNIT_SYSTEM: "metric",
        CONF_SCAN_INTERVAL: 300.0,
    }
