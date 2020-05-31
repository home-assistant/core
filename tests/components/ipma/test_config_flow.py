"""Tests for IPMA config flow."""

from homeassistant.components.ipma import config_flow
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE

from tests.async_mock import Mock, patch


async def test_show_config_form():
    """Test show configuration form."""
    hass = Mock()
    flow = config_flow.IpmaFlowHandler()
    flow.hass = hass

    result = await flow._show_config_form()

    assert result["type"] == "form"
    assert result["step_id"] == "user"


async def test_show_config_form_default_values():
    """Test show configuration form."""
    hass = Mock()
    flow = config_flow.IpmaFlowHandler()
    flow.hass = hass

    result = await flow._show_config_form(name="test", latitude="0", longitude="0")

    assert result["type"] == "form"
    assert result["step_id"] == "user"


async def test_flow_with_home_location(hass):
    """Test config flow .

    Tests the flow when a default location is configured
    then it should return a form with default values
    """
    flow = config_flow.IpmaFlowHandler()
    flow.hass = hass

    hass.config.location_name = "Home"
    hass.config.latitude = 1
    hass.config.longitude = 1

    result = await flow.async_step_user()
    assert result["type"] == "form"
    assert result["step_id"] == "user"


async def test_flow_show_form():
    """Test show form scenarios first time.

    Test when the form should show when no configurations exists
    """
    hass = Mock()
    flow = config_flow.IpmaFlowHandler()
    flow.hass = hass

    with patch(
        "homeassistant.components.ipma.config_flow.IpmaFlowHandler._show_config_form"
    ) as config_form:
        await flow.async_step_user()
        assert len(config_form.mock_calls) == 1


async def test_flow_entry_created_from_user_input():
    """Test that create data from user input.

    Test when the form should show when no configurations exists
    """
    hass = Mock()
    flow = config_flow.IpmaFlowHandler()
    flow.hass = hass

    test_data = {"name": "home", CONF_LONGITUDE: "0", CONF_LATITUDE: "0"}

    # Test that entry created when user_input name not exists
    with patch(
        "homeassistant.components.ipma.config_flow.IpmaFlowHandler._show_config_form"
    ) as config_form, patch.object(
        flow.hass.config_entries, "async_entries", return_value=[],
    ) as config_entries:

        result = await flow.async_step_user(user_input=test_data)

        assert result["type"] == "create_entry"
        assert result["data"] == test_data
        assert len(config_entries.mock_calls) == 1
        assert not config_form.mock_calls


async def test_flow_entry_config_entry_already_exists():
    """Test that create data from user input and config_entry already exists.

    Test when the form should show when user puts existing name
    in the config gui. Then the form should show with error
    """
    hass = Mock()
    flow = config_flow.IpmaFlowHandler()
    flow.hass = hass

    test_data = {"name": "home", CONF_LONGITUDE: "0", CONF_LATITUDE: "0"}

    # Test that entry created when user_input name not exists
    with patch(
        "homeassistant.components.ipma.config_flow.IpmaFlowHandler._show_config_form"
    ) as config_form, patch.object(
        flow.hass.config_entries, "async_entries", return_value={"home": test_data}
    ) as config_entries:

        await flow.async_step_user(user_input=test_data)

        assert len(config_form.mock_calls) == 1
        assert len(config_entries.mock_calls) == 1
        assert len(flow._errors) == 1
