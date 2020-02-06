"""Tests for Met.no config flow."""
from unittest.mock import Mock, patch

from homeassistant.components.met import config_flow
from homeassistant.const import CONF_ELEVATION, CONF_LATITUDE, CONF_LONGITUDE

from tests.common import MockConfigEntry, mock_coro


async def test_show_config_form():
    """Test show configuration form."""
    hass = Mock()
    flow = config_flow.MetFlowHandler()
    flow.hass = hass

    result = await flow._show_config_form()

    assert result["type"] == "form"
    assert result["step_id"] == "user"


async def test_show_config_form_default_values():
    """Test show configuration form."""
    hass = Mock()
    flow = config_flow.MetFlowHandler()
    flow.hass = hass

    result = await flow._show_config_form(
        name="test", latitude="0", longitude="0", elevation="0"
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"


async def test_flow_with_home_location(hass):
    """Test config flow .

    Tests the flow when a default location is configured
    then it should return a form with default values
    """
    flow = config_flow.MetFlowHandler()
    flow.hass = hass

    hass.config.location_name = "Home"
    hass.config.latitude = 1
    hass.config.longitude = 1
    hass.config.elevation = 1

    result = await flow.async_step_user()
    assert result["type"] == "form"
    assert result["step_id"] == "user"


async def test_flow_show_form():
    """Test show form scenarios first time.

    Test when the form should show when no configurations exists
    """
    hass = Mock()
    flow = config_flow.MetFlowHandler()
    flow.hass = hass

    with patch.object(
        flow, "_show_config_form", return_value=mock_coro()
    ) as config_form:
        await flow.async_step_user()
        assert len(config_form.mock_calls) == 1


async def test_flow_entry_created_from_user_input():
    """Test that create data from user input.

    Test when the form should show when no configurations exists
    """
    hass = Mock()
    flow = config_flow.MetFlowHandler()
    flow.hass = hass

    test_data = {
        "name": "home",
        CONF_LONGITUDE: "0",
        CONF_LATITUDE: "0",
        CONF_ELEVATION: "0",
    }

    # Test that entry created when user_input name not exists
    with patch.object(
        flow, "_show_config_form", return_value=mock_coro()
    ) as config_form, patch.object(
        flow.hass.config_entries, "async_entries", return_value=mock_coro()
    ) as config_entries:

        result = await flow.async_step_user(user_input=test_data)

        assert result["type"] == "create_entry"
        assert result["data"] == test_data
        assert len(config_entries.mock_calls) == 1
        assert not config_form.mock_calls


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
