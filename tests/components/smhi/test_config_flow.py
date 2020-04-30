"""Tests for SMHI config flow."""
from smhi.smhi_lib import Smhi as SmhiApi, SmhiForecastException

from homeassistant.components.smhi import config_flow
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE

from tests.async_mock import Mock, patch


# pylint: disable=protected-access
async def test_homeassistant_location_exists() -> None:
    """Test if Home Assistant location exists it should return True."""
    hass = Mock()
    flow = config_flow.SmhiFlowHandler()
    flow.hass = hass
    with patch.object(flow, "_check_location", return_value=True):
        # Test exists
        hass.config.location_name = "Home"
        hass.config.latitude = 17.8419
        hass.config.longitude = 59.3262

        assert await flow._homeassistant_location_exists() is True

        # Test not exists
        hass.config.location_name = None
        hass.config.latitude = 0
        hass.config.longitude = 0

        assert await flow._homeassistant_location_exists() is False


async def test_name_in_configuration_exists() -> None:
    """Test if home location exists in configuration."""
    hass = Mock()
    flow = config_flow.SmhiFlowHandler()
    flow.hass = hass

    # Test exists
    hass.config.location_name = "Home"
    hass.config.latitude = 17.8419
    hass.config.longitude = 59.3262

    # Check not exists
    with patch.object(
        config_flow,
        "smhi_locations",
        return_value={"test": "something", "test2": "something else"},
    ):

        assert flow._name_in_configuration_exists("no_exist_name") is False

    # Check exists
    with patch.object(
        config_flow,
        "smhi_locations",
        return_value={"test": "something", "name_exist": "config"},
    ):

        assert flow._name_in_configuration_exists("name_exist") is True


def test_smhi_locations(hass) -> None:
    """Test return empty set."""
    locations = config_flow.smhi_locations(hass)
    assert not locations


async def test_show_config_form() -> None:
    """Test show configuration form."""
    hass = Mock()
    flow = config_flow.SmhiFlowHandler()
    flow.hass = hass

    result = await flow._show_config_form()

    assert result["type"] == "form"
    assert result["step_id"] == "user"


async def test_show_config_form_default_values() -> None:
    """Test show configuration form."""
    hass = Mock()
    flow = config_flow.SmhiFlowHandler()
    flow.hass = hass

    result = await flow._show_config_form(name="test", latitude="65", longitude="17")

    assert result["type"] == "form"
    assert result["step_id"] == "user"


async def test_flow_with_home_location(hass) -> None:
    """Test config flow .

    Tests the flow when a default location is configured
    then it should return a form with default values
    """
    flow = config_flow.SmhiFlowHandler()
    flow.hass = hass

    with patch.object(flow, "_check_location", return_value=True):
        hass.config.location_name = "Home"
        hass.config.latitude = 17.8419
        hass.config.longitude = 59.3262

        result = await flow.async_step_user()
        assert result["type"] == "form"
        assert result["step_id"] == "user"


async def test_flow_show_form() -> None:
    """Test show form scenarios first time.

    Test when the form should show when no configurations exists
    """
    hass = Mock()
    flow = config_flow.SmhiFlowHandler()
    flow.hass = hass

    # Test show form when Home Assistant config exists and
    # home is already configured, then new config is allowed
    with patch.object(
        flow, "_show_config_form", return_value=None
    ) as config_form, patch.object(
        flow, "_homeassistant_location_exists", return_value=True
    ), patch.object(
        config_flow,
        "smhi_locations",
        return_value={"test": "something", "name_exist": "config"},
    ):
        await flow.async_step_user()
        assert len(config_form.mock_calls) == 1

    # Test show form when Home Assistant config not and
    # home is not configured
    with patch.object(
        flow, "_show_config_form", return_value=None
    ) as config_form, patch.object(
        flow, "_homeassistant_location_exists", return_value=False
    ), patch.object(
        config_flow,
        "smhi_locations",
        return_value={"test": "something", "name_exist": "config"},
    ):

        await flow.async_step_user()
        assert len(config_form.mock_calls) == 1


async def test_flow_show_form_name_exists() -> None:
    """Test show form if name already exists.

    Test when the form should show when no configurations exists
    """
    hass = Mock()
    flow = config_flow.SmhiFlowHandler()
    flow.hass = hass
    test_data = {"name": "home", CONF_LONGITUDE: "0", CONF_LATITUDE: "0"}
    # Test show form when Home Assistant config exists and
    # home is already configured, then new config is allowed
    with patch.object(
        flow, "_show_config_form", return_value=None
    ) as config_form, patch.object(
        flow, "_name_in_configuration_exists", return_value=True
    ), patch.object(
        config_flow,
        "smhi_locations",
        return_value={"test": "something", "name_exist": "config"},
    ), patch.object(
        flow, "_check_location", return_value=True
    ):

        await flow.async_step_user(user_input=test_data)

        assert len(config_form.mock_calls) == 1
        assert len(flow._errors) == 1


async def test_flow_entry_created_from_user_input() -> None:
    """Test that create data from user input.

    Test when the form should show when no configurations exists
    """
    hass = Mock()
    flow = config_flow.SmhiFlowHandler()
    flow.hass = hass

    test_data = {"name": "home", CONF_LONGITUDE: "0", CONF_LATITUDE: "0"}

    # Test that entry created when user_input name not exists
    with patch.object(
        flow, "_show_config_form", return_value=None
    ) as config_form, patch.object(
        flow, "_name_in_configuration_exists", return_value=False
    ), patch.object(
        flow, "_homeassistant_location_exists", return_value=False
    ), patch.object(
        config_flow,
        "smhi_locations",
        return_value={"test": "something", "name_exist": "config"},
    ), patch.object(
        flow, "_check_location", return_value=True
    ):

        result = await flow.async_step_user(user_input=test_data)

        assert result["type"] == "create_entry"
        assert result["data"] == test_data
        assert not config_form.mock_calls


async def test_flow_entry_created_user_input_faulty() -> None:
    """Test that create data from user input and are faulty.

    Test when the form should show when user puts faulty location
    in the config gui. Then the form should show with error
    """
    hass = Mock()
    flow = config_flow.SmhiFlowHandler()
    flow.hass = hass

    test_data = {"name": "home", CONF_LONGITUDE: "0", CONF_LATITUDE: "0"}

    # Test that entry created when user_input name not exists
    with patch.object(flow, "_check_location", return_value=True), patch.object(
        flow, "_show_config_form", return_value=None
    ) as config_form, patch.object(
        flow, "_name_in_configuration_exists", return_value=False
    ), patch.object(
        flow, "_homeassistant_location_exists", return_value=False
    ), patch.object(
        config_flow,
        "smhi_locations",
        return_value={"test": "something", "name_exist": "config"},
    ), patch.object(
        flow, "_check_location", return_value=False
    ):

        await flow.async_step_user(user_input=test_data)

        assert len(config_form.mock_calls) == 1
        assert len(flow._errors) == 1


async def test_check_location_correct() -> None:
    """Test check location when correct input."""
    hass = Mock()
    flow = config_flow.SmhiFlowHandler()
    flow.hass = hass

    with patch.object(
        config_flow.aiohttp_client, "async_get_clientsession"
    ), patch.object(SmhiApi, "async_get_forecast", return_value=None):

        assert await flow._check_location("58", "17") is True


async def test_check_location_faulty() -> None:
    """Test check location when faulty input."""
    hass = Mock()
    flow = config_flow.SmhiFlowHandler()
    flow.hass = hass

    with patch.object(
        config_flow.aiohttp_client, "async_get_clientsession"
    ), patch.object(SmhiApi, "async_get_forecast", side_effect=SmhiForecastException()):

        assert await flow._check_location("58", "17") is False
