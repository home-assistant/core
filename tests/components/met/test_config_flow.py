"""Tests for Met.no config flow."""
import pytest

from homeassistant.components.met.const import DOMAIN, HOME_LOCATION_NAME
from homeassistant.const import CONF_ELEVATION, CONF_LATITUDE, CONF_LONGITUDE

from tests.async_mock import patch
from tests.common import MockConfigEntry


@pytest.fixture(name="met_setup", autouse=True)
def met_setup_fixture():
    """Patch met setup entry."""
    with patch("homeassistant.components.met.async_setup_entry", return_value=True):
        yield


async def test_show_config_form(hass):
    """Test show configuration form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"


async def test_flow_with_home_location(hass):
    """Test config flow.

    Test the flow when a default location is configured.
    Then it should return a form with default values.
    """
    hass.config.latitude = 1
    hass.config.longitude = 2
    hass.config.elevation = 3

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"

    default_data = result["data_schema"]({})
    assert default_data["name"] == HOME_LOCATION_NAME
    assert default_data["latitude"] == 1
    assert default_data["longitude"] == 2
    assert default_data["elevation"] == 3


async def test_create_entry(hass):
    """Test create entry from user input."""
    test_data = {
        "name": "home",
        CONF_LONGITUDE: 0,
        CONF_LATITUDE: 0,
        CONF_ELEVATION: 0,
    }

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}, data=test_data
    )

    assert result["type"] == "create_entry"
    assert result["title"] == "home"
    assert result["data"] == test_data


async def test_flow_entry_already_exists(hass):
    """Test user input for config_entry that already exists.

    Test when the form should show when user puts existing location
    in the config gui. Then the form should show with error.
    """
    first_entry = MockConfigEntry(
        domain="met",
        data={"name": "home", CONF_LATITUDE: 0, CONF_LONGITUDE: 0, CONF_ELEVATION: 0},
    )
    first_entry.add_to_hass(hass)

    test_data = {
        "name": "home",
        CONF_LONGITUDE: 0,
        CONF_LATITUDE: 0,
        CONF_ELEVATION: 0,
    }

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}, data=test_data
    )

    assert result["type"] == "form"
    assert result["errors"]["name"] == "name_exists"


async def test_onboarding_step(hass):
    """Test initializing via onboarding step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "onboarding"}, data={}
    )

    assert result["type"] == "create_entry"
    assert result["title"] == HOME_LOCATION_NAME
    assert result["data"] == {"track_home": True}


async def test_import_step(hass):
    """Test initializing via import step."""
    test_data = {
        "name": "home",
        CONF_LONGITUDE: None,
        CONF_LATITUDE: None,
        CONF_ELEVATION: 0,
        "track_home": True,
    }
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "import"}, data=test_data
    )

    assert result["type"] == "create_entry"
    assert result["title"] == "home"
    assert result["data"] == test_data
