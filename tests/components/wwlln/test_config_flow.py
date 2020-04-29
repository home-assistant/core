"""Define tests for the WWLLN config flow."""
from asynctest import patch

from homeassistant import data_entry_flow
from homeassistant.components.wwlln import CONF_WINDOW, DOMAIN
from homeassistant.config_entries import SOURCE_USER
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


async def test_step_user(hass):
    """Test that the user step works."""
    conf = {CONF_LATITUDE: 39.128712, CONF_LONGITUDE: -104.9812612, CONF_RADIUS: 25}

    with patch("homeassistant.components.wwlln.async_setup_entry", return_value=True):
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

    with patch("homeassistant.components.wwlln.async_setup_entry", return_value=True):
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
        CONF_WINDOW: 3600,
    }

    with patch("homeassistant.components.wwlln.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=conf
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "39.128712, -104.9812612"
    assert result["data"] == {
        CONF_LATITUDE: 39.128712,
        CONF_LONGITUDE: -104.9812612,
        CONF_RADIUS: 25,
        CONF_WINDOW: 3600,
    }


async def test_options_flow(hass):
    """Test config flow options."""
    conf = {
        CONF_LATITUDE: 39.128712,
        CONF_LONGITUDE: -104.9812612,
    }

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="39.128712, -104.9812612",
        data=conf,
        options={CONF_RADIUS: 25, CONF_WINDOW: 3600},
    )
    config_entry.add_to_hass(hass)

    with patch("homeassistant.components.wwlln.async_setup_entry", return_value=True):
        result = await hass.config_entries.options.async_init(config_entry.entry_id)

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "init"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={CONF_RADIUS: 50}
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert config_entry.options == {CONF_RADIUS: 50, CONF_WINDOW: 3600}
