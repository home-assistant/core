"""Define tests for the WWLLN config flow."""
from datetime import timedelta

from asynctest import patch

from homeassistant import data_entry_flow
from homeassistant.components.wwlln import (
    CONF_WINDOW,
    DATA_CLIENT,
    DOMAIN,
    async_setup_entry,
    config_flow,
)
from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_RADIUS,
    CONF_UNIT_SYSTEM,
)


async def test_duplicate_error(hass, config_entry):
    """Test that errors are shown when duplicates are added."""
    conf = {CONF_LATITUDE: 39.128712, CONF_LONGITUDE: -104.9812612, CONF_RADIUS: 25}

    config_entry.add_to_hass(hass)
    flow = config_flow.WWLLNFlowHandler()
    flow.hass = hass

    result = await flow.async_step_user(user_input=conf)
    assert result["errors"] == {"base": "identifier_exists"}


async def test_show_form(hass):
    """Test that the form is served with no input."""
    flow = config_flow.WWLLNFlowHandler()
    flow.hass = hass

    result = await flow.async_step_user(user_input=None)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"


async def test_step_import(hass):
    """Test that the import step works."""
    # `configuration.yaml` will always return a timedelta for the `window`
    # parameter, FYI:
    conf = {
        CONF_LATITUDE: 39.128712,
        CONF_LONGITUDE: -104.9812612,
        CONF_RADIUS: 25,
        CONF_UNIT_SYSTEM: "metric",
        CONF_WINDOW: timedelta(minutes=10),
    }

    flow = config_flow.WWLLNFlowHandler()
    flow.hass = hass

    result = await flow.async_step_import(import_config=conf)
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "39.128712, -104.9812612"
    assert result["data"] == {
        CONF_LATITUDE: 39.128712,
        CONF_LONGITUDE: -104.9812612,
        CONF_RADIUS: 25,
        CONF_UNIT_SYSTEM: "metric",
        CONF_WINDOW: 600.0,
    }


async def test_step_user(hass):
    """Test that the user step works."""
    conf = {CONF_LATITUDE: 39.128712, CONF_LONGITUDE: -104.9812612, CONF_RADIUS: 25}

    flow = config_flow.WWLLNFlowHandler()
    flow.hass = hass

    result = await flow.async_step_user(user_input=conf)
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "39.128712, -104.9812612"
    assert result["data"] == {
        CONF_LATITUDE: 39.128712,
        CONF_LONGITUDE: -104.9812612,
        CONF_RADIUS: 25,
        CONF_UNIT_SYSTEM: "metric",
        CONF_WINDOW: 3600.0,
    }


async def test_custom_window(hass):
    """Test that a custom window is stored correctly."""
    conf = {
        CONF_LATITUDE: 39.128712,
        CONF_LONGITUDE: -104.9812612,
        CONF_RADIUS: 25,
        CONF_WINDOW: timedelta(hours=2),
    }

    flow = config_flow.WWLLNFlowHandler()
    flow.hass = hass

    result = await flow.async_step_user(user_input=conf)
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "39.128712, -104.9812612"
    assert result["data"] == {
        CONF_LATITUDE: 39.128712,
        CONF_LONGITUDE: -104.9812612,
        CONF_RADIUS: 25,
        CONF_UNIT_SYSTEM: "metric",
        CONF_WINDOW: 7200,
    }


async def test_component_load_config_entry(hass, config_entry):
    """Test that loading an existing config entry yields a client."""
    config_entry.add_to_hass(hass)
    with patch.object(hass.config_entries, "async_forward_entry_setup") as forward_mock:
        assert await async_setup_entry(hass, config_entry)

        await hass.async_block_till_done()
        assert forward_mock.call_count == 1
        assert len(hass.data[DOMAIN][DATA_CLIENT]) == 1
