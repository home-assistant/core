"""Define tests for the WWLLN config flow."""
from asynctest import patch

from homeassistant import data_entry_flow
from homeassistant.components.wwlln import (
    CONF_WINDOW,
    DATA_CLIENT,
    DOMAIN,
    async_setup_entry,
)
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_RADIUS

from tests.common import MockConfigEntry


async def test_duplicate_error(hass, config_entry):
    """Test that errors are shown when duplicates are added."""
    conf = {CONF_LATITUDE: 39.128712, CONF_LONGITUDE: -104.9812612, CONF_RADIUS: 25}

    MockConfigEntry(
        domain=DOMAIN, unique_id="39.128712, -104.9812612", data=conf
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=conf
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_show_form(hass):
    """Test that the form is served with no input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER},
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"


async def test_step_import(hass):
    """Test that the import step works."""
    conf = {
        CONF_LATITUDE: 39.128712,
        CONF_LONGITUDE: -104.9812612,
        CONF_RADIUS: 25,
    }

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=conf
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "39.128712, -104.9812612"
    assert result["data"] == {
        CONF_LATITUDE: 39.128712,
        CONF_LONGITUDE: -104.9812612,
        CONF_RADIUS: 25,
        CONF_WINDOW: 3600.0,
    }


async def test_step_user(hass):
    """Test that the user step works."""
    conf = {CONF_LATITUDE: 39.128712, CONF_LONGITUDE: -104.9812612, CONF_RADIUS: 25}

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=conf
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "39.128712, -104.9812612"
    assert result["data"] == {
        CONF_LATITUDE: 39.128712,
        CONF_LONGITUDE: -104.9812612,
        CONF_RADIUS: 25,
        CONF_WINDOW: 3600.0,
    }


async def test_different_unit_system(hass):
    """Test that the config flow picks up the HASS unit system."""
    conf = {
        CONF_LATITUDE: 39.128712,
        CONF_LONGITUDE: -104.9812612,
        CONF_RADIUS: 25,
    }

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=conf
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "39.128712, -104.9812612"
    assert result["data"] == {
        CONF_LATITUDE: 39.128712,
        CONF_LONGITUDE: -104.9812612,
        CONF_RADIUS: 25,
        CONF_WINDOW: 3600.0,
    }


async def test_custom_window(hass):
    """Test that a custom window is stored correctly."""
    conf = {
        CONF_LATITUDE: 39.128712,
        CONF_LONGITUDE: -104.9812612,
        CONF_RADIUS: 25,
        CONF_WINDOW: 7200,
    }

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=conf
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "39.128712, -104.9812612"
    assert result["data"] == {
        CONF_LATITUDE: 39.128712,
        CONF_LONGITUDE: -104.9812612,
        CONF_RADIUS: 25,
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
