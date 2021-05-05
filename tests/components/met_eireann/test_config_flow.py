"""Tests for Met Éireann config flow."""
from unittest.mock import patch

import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.met_eireann.const import DOMAIN, HOME_LOCATION_NAME
from homeassistant.const import CONF_ELEVATION, CONF_LATITUDE, CONF_LONGITUDE


@pytest.fixture(name="met_eireann_setup", autouse=True)
def met_setup_fixture():
    """Patch Met Éireann setup entry."""
    with patch(
        "homeassistant.components.met_eireann.async_setup_entry", return_value=True
    ):
        yield


async def test_show_config_form(hass):
    """Test show configuration form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == config_entries.SOURCE_USER


async def test_flow_with_home_location(hass):
    """Test config flow.

    Test the flow when a default location is configured.
    Then it should return a form with default values.
    """
    hass.config.latitude = 1
    hass.config.longitude = 2
    hass.config.elevation = 3

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == config_entries.SOURCE_USER

    default_data = result["data_schema"]({})
    assert default_data["name"] == HOME_LOCATION_NAME
    assert default_data["latitude"] == 1
    assert default_data["longitude"] == 2
    assert default_data["elevation"] == 3


async def test_create_entry(hass):
    """Test create entry from user input."""
    test_data = {
        "name": "test",
        CONF_LONGITUDE: 0,
        CONF_LATITUDE: 0,
        CONF_ELEVATION: 0,
    }

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}, data=test_data
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == test_data.get("name")
    assert result["data"] == test_data


async def test_flow_entry_already_exists(hass):
    """Test user input for config_entry that already exists.

    Test to ensure the config form does not allow duplicate entries.
    """
    test_data = {
        "name": "test",
        CONF_LONGITUDE: 0,
        CONF_LATITUDE: 0,
        CONF_ELEVATION: 0,
    }

    # Create the first entry and assert that it is created successfully
    result1 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}, data=test_data
    )
    assert result1["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY

    # Create the second entry and assert that it is aborted
    result2 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}, data=test_data
    )
    assert result2["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result2["reason"] == "already_configured"
