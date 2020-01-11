"""Tests for Met.no config flow."""
from unittest.mock import Mock, patch

from homeassistant.components.met import config_flow
from homeassistant.components.met.const import DOMAIN, HOME_LOCATION_NAME
from homeassistant.const import CONF_ELEVATION, CONF_LATITUDE, CONF_LONGITUDE

from tests.common import MockConfigEntry, mock_coro


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
    Then it should return a form with default values
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

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=default_data
    )

    assert result["type"] == "create_entry"
    assert result["data"] == default_data


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
    assert result["data"] == test_data


async def test_flow_entry_config_entry_already_exists():
    """Test that create data from user input and config_entry already exists.

    Test when the form should show when user puts existing location
    in the config gui. Then the form should show with error
    """
    hass = Mock()

    flow = config_flow.MetFlowHandler()
    flow.hass = hass

    first_entry = MockConfigEntry(domain="met")
    first_entry.data["name"] = "home"
    first_entry.data[CONF_LONGITUDE] = "0"
    first_entry.data[CONF_LATITUDE] = "0"
    first_entry.add_to_hass(hass)

    test_data = {
        "name": "home",
        CONF_LONGITUDE: "0",
        CONF_LATITUDE: "0",
        CONF_ELEVATION: "0",
    }

    with patch.object(
        flow, "_show_config_form", return_value=mock_coro()
    ) as config_form, patch.object(
        flow.hass.config_entries, "async_entries", return_value=[first_entry]
    ) as config_entries:

        await flow.async_step_user(user_input=test_data)

        assert len(config_form.mock_calls) == 1
        assert len(config_entries.mock_calls) == 1
        assert len(flow._errors) == 1


async def test_onboarding_step(hass, mock_weather):
    """Test initializing via onboarding step."""
    hass = Mock()

    flow = config_flow.MetFlowHandler()
    flow.hass = hass

    result = await flow.async_step_onboarding({})

    assert result["type"] == "create_entry"
    assert result["title"] == "Home"
    assert result["data"] == {"track_home": True}
