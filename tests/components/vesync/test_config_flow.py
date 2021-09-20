"""Test for vesync config flow."""
from unittest.mock import patch

from homeassistant import data_entry_flow
from homeassistant.components.vesync import DOMAIN, config_flow
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from tests.common import MockConfigEntry


async def test_abort_already_setup(hass):
    """Test if we abort because component is already setup."""
    flow = config_flow.VeSyncFlowHandler()
    flow.hass = hass
    MockConfigEntry(domain=DOMAIN, title="user", data={"user": "pass"}).add_to_hass(
        hass
    )
    result = await flow.async_step_user()

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_invalid_login_error(hass):
    """Test if we return error for invalid username and password."""
    test_dict = {CONF_USERNAME: "user", CONF_PASSWORD: "pass"}
    flow = config_flow.VeSyncFlowHandler()
    flow.hass = hass
    with patch("pyvesync.vesync.VeSync.login", return_value=False):
        result = await flow.async_step_user(user_input=test_dict)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_config_flow_configuration_yaml(hass):
    """Test config flow with configuration.yaml user input."""
    test_dict = {CONF_USERNAME: "user", CONF_PASSWORD: "pass"}
    flow = config_flow.VeSyncFlowHandler()
    flow.hass = hass
    with patch("pyvesync.vesync.VeSync.login", return_value=True):
        result = await flow.async_step_import(test_dict)

    assert result["data"].get(CONF_USERNAME) == test_dict[CONF_USERNAME]
    assert result["data"].get(CONF_PASSWORD) == test_dict[CONF_PASSWORD]


async def test_config_flow_user_input(hass):
    """Test config flow with user input."""
    flow = config_flow.VeSyncFlowHandler()
    flow.hass = hass
    result = await flow.async_step_user()
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    with patch("pyvesync.vesync.VeSync.login", return_value=True):
        result = await flow.async_step_user(
            {CONF_USERNAME: "user", CONF_PASSWORD: "pass"}
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["data"][CONF_USERNAME] == "user"
        assert result["data"][CONF_PASSWORD] == "pass"
