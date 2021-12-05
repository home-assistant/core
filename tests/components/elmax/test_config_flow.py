"""Tests for the Abode config flow."""
from unittest.mock import patch

from elmax_api.exceptions import ElmaxBadLoginError, ElmaxBadPinError, ElmaxNetworkError

from homeassistant import data_entry_flow
from homeassistant.components.elmax import config_flow
from homeassistant.components.elmax.const import (
    CONF_ELMAX_PANEL_ID,
    CONF_ELMAX_PANEL_NAME,
    CONF_ELMAX_PANEL_PIN,
    CONF_ELMAX_PASSWORD,
    CONF_ELMAX_USERNAME,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_REAUTH

from tests.common import MockConfigEntry
from tests.components.elmax import (
    MOCK_PANEL_ID,
    MOCK_PANEL_NAME,
    MOCK_PANEL_PIN,
    MOCK_USERNAME,
)

CONF_POLLING = "polling"


async def test_show_form(hass):
    """Test that the form is served with no input."""
    flow = config_flow.ConfigFlow()
    flow.hass = hass

    result = await flow.async_step_user(user_input=None)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"


async def test_one_config_allowed(hass):
    """Test that only one Elmax configuration is allowed per panel ID Panel."""
    flow = config_flow.ConfigFlow()
    flow.hass = hass

    # Mock an existing config entry
    MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ELMAX_PANEL_ID: MOCK_PANEL_ID,
            CONF_ELMAX_PANEL_PIN: MOCK_PANEL_PIN,
            CONF_ELMAX_USERNAME: MOCK_USERNAME,
            CONF_ELMAX_PASSWORD: "password",
        },
    ).add_to_hass(hass)

    # Try to add another instance of the integration for the very same panel.
    user_input = {CONF_ELMAX_USERNAME: MOCK_USERNAME, CONF_ELMAX_PASSWORD: "password"}
    step_user_result = await flow.async_step_user(user_input=user_input)
    assert step_user_result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert step_user_result["step_id"] == "panels"

    user_input = {
        CONF_ELMAX_PANEL_NAME: MOCK_PANEL_NAME,
        CONF_ELMAX_PANEL_PIN: MOCK_PANEL_PIN,
    }
    step_panels_result = await flow.async_step_panels(user_input=user_input)
    assert step_panels_result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert step_panels_result["reason"] == "single_instance_allowed"


async def test_invalid_credentials(hass):
    """Test that invalid credentials throws an error."""
    conf = {
        CONF_ELMAX_USERNAME: "wrong_user_name@email.com",
        CONF_ELMAX_PASSWORD: "incorrect_password",
    }

    flow = config_flow.ConfigFlow()
    flow.hass = hass

    with patch(
        "elmax_api.http.Elmax.login",
        side_effect=ElmaxBadLoginError(),
    ):
        result = await flow.async_step_user(user_input=conf)
        assert result["errors"] == {"base": "bad_auth"}


async def test_connection_error(hass):
    """Test other than invalid credentials throws an error."""
    conf = {CONF_ELMAX_USERNAME: MOCK_USERNAME, CONF_ELMAX_PASSWORD: "password"}

    flow = config_flow.ConfigFlow()
    flow.hass = hass

    with patch(
        "elmax_api.http.Elmax.login",
        side_effect=ElmaxNetworkError(),
    ):
        result = await flow.async_step_user(user_input=conf)
        assert result["errors"] == {"base": "network_error"}


async def test_unhandled_error(hass):
    """Test unhandled exceptions."""
    conf = {
        CONF_ELMAX_PANEL_NAME: MOCK_PANEL_NAME,
        CONF_ELMAX_PANEL_PIN: MOCK_PANEL_PIN,
    }

    flow = config_flow.ConfigFlow()
    flow.hass = hass

    # Perform first step (user) to set up ConfigFlow internal state objects.
    user_input = {CONF_ELMAX_USERNAME: MOCK_USERNAME, CONF_ELMAX_PASSWORD: "password"}
    await flow.async_step_user(user_input=user_input)

    with patch(
        "elmax_api.http.Elmax.get_panel_status",
        side_effect=Exception(),
    ):
        result = await flow.async_step_panels(user_input=conf)
        assert result["errors"] == {"base": "unknown_error"}


async def test_invalid_pin(hass):
    """Test error is thrown when a wrong pin is used to pair a panel."""
    flow = config_flow.ConfigFlow()
    flow.hass = hass

    # Perform first step (user) to setup ConfigFlow internal state objects.
    user_input = {CONF_ELMAX_USERNAME: MOCK_USERNAME, CONF_ELMAX_PASSWORD: "password"}
    await flow.async_step_user(user_input=user_input)

    # Simulate bad pin response.
    with patch(
        "elmax_api.http.Elmax.get_panel_status",
        side_effect=ElmaxBadPinError(),
    ):
        user_input = {
            CONF_ELMAX_PANEL_NAME: MOCK_PANEL_NAME,
            CONF_ELMAX_PANEL_PIN: "111111",
        }
        step_panels_result = await flow.async_step_panels(user_input=user_input)
        assert step_panels_result["errors"] == {"base": "invalid_pin"}


async def test_no_online_panel(hass):
    """Test no-online panel is available."""
    flow = config_flow.ConfigFlow()
    flow.hass = hass

    # Simulate low-level api returns no panels.
    with patch(
        "elmax_api.http.Elmax.list_control_panels",
        return_value=[],
    ):
        # Perform first step (user) to setup ConfigFlow internal state objects.
        user_input = {
            CONF_ELMAX_USERNAME: MOCK_USERNAME,
            CONF_ELMAX_PASSWORD: "password",
        }
        result = await flow.async_step_user(user_input=user_input)
        assert result["errors"] == {"base": "no_panel_online"}


async def test_step_user(hass):
    """Test that the user step works."""
    flow = config_flow.ConfigFlow()
    flow.hass = hass

    # Try to add another instance of the integration for the very same panel.
    user_input = {CONF_ELMAX_USERNAME: MOCK_USERNAME, CONF_ELMAX_PASSWORD: "password"}
    step_user_result = await flow.async_step_user(user_input=user_input)
    assert step_user_result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert step_user_result["step_id"] == "panels"

    user_input = {
        CONF_ELMAX_PANEL_NAME: MOCK_PANEL_NAME,
        CONF_ELMAX_PANEL_PIN: MOCK_PANEL_PIN,
    }
    step_panels_result = await flow.async_step_panels(user_input=user_input)
    assert step_panels_result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert step_panels_result["data"] == {
        CONF_ELMAX_PANEL_ID: MOCK_PANEL_ID,
        CONF_ELMAX_PANEL_PIN: MOCK_PANEL_PIN,
        CONF_ELMAX_USERNAME: MOCK_USERNAME,
        CONF_ELMAX_PASSWORD: "password",
    }


async def test_step_panels_missing_input(hass):
    """Test that the user step works."""
    flow = config_flow.ConfigFlow()
    flow.hass = hass

    step_panels_result = await flow.async_step_panels(user_input=None)
    assert step_panels_result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert step_panels_result["step_id"] == "user"


async def test_step_reauth(hass):
    """Test the reauth flow."""
    conf = {
        CONF_ELMAX_USERNAME: MOCK_USERNAME,
        CONF_ELMAX_PASSWORD: "password",
    }

    MockConfigEntry(
        domain=DOMAIN,
        data=conf,
    ).add_to_hass(hass)

    with patch("homeassistant.components.elmax.config_flow.ConfigFlow"):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_REAUTH}, data=conf
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "user"
