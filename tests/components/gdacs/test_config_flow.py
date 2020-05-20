"""Define tests for the GDACS config flow."""
from datetime import timedelta

from asynctest import patch
import pytest

from homeassistant import data_entry_flow
from homeassistant.components.gdacs import CONF_CATEGORIES, DOMAIN
from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_RADIUS,
    CONF_SCAN_INTERVAL,
)


@pytest.fixture(name="gdacs_setup", autouse=True)
def gdacs_setup_fixture():
    """Mock gdacs entry setup."""
    with patch("homeassistant.components.gdacs.async_setup_entry", return_value=True):
        yield


async def test_duplicate_error(hass, config_entry):
    """Test that errors are shown when duplicates are added."""
    conf = {CONF_LATITUDE: -41.2, CONF_LONGITUDE: 174.7, CONF_RADIUS: 25}
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}, data=conf
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_show_form(hass):
    """Test that the form is served with no input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"


async def test_step_import(hass):
    """Test that the import step works."""
    conf = {
        CONF_LATITUDE: -41.2,
        CONF_LONGITUDE: 174.7,
        CONF_RADIUS: 25,
        CONF_SCAN_INTERVAL: timedelta(minutes=4),
        CONF_CATEGORIES: ["Drought", "Earthquake"],
    }

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "import"}, data=conf
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "-41.2, 174.7"
    assert result["data"] == {
        CONF_LATITUDE: -41.2,
        CONF_LONGITUDE: 174.7,
        CONF_RADIUS: 25,
        CONF_SCAN_INTERVAL: 240.0,
        CONF_CATEGORIES: ["Drought", "Earthquake"],
    }


async def test_step_user(hass):
    """Test that the user step works."""
    hass.config.latitude = -41.2
    hass.config.longitude = 174.7
    conf = {CONF_RADIUS: 25}

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}, data=conf
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "-41.2, 174.7"
    assert result["data"] == {
        CONF_LATITUDE: -41.2,
        CONF_LONGITUDE: 174.7,
        CONF_RADIUS: 25,
        CONF_SCAN_INTERVAL: 300.0,
        CONF_CATEGORIES: [],
    }
