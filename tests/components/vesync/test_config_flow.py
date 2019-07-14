"""Test for vesync config flow."""
from unittest.mock import patch
from homeassistant import data_entry_flow
from homeassistant.components.vesync import config_flow
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD


async def test_abort_already_setup(hass):
    """Test if we abort because component is already setup."""
    flow = config_flow.VeSyncFlowHandler()
    flow.hass = hass

    with patch(
            "homeassistant.components.vesync.config_flow.configured_instances",
            return_value=[{CONF_USERNAME: 'test'}]):
        result = await flow.async_step_user()

    assert result['type'] == data_entry_flow.RESULT_TYPE_ABORT
    assert result['reason'] == 'already_setup'


async def test_config_flow_configuration_yaml(hass):
    """Test config flow with configuration.yaml user input."""
    test_dict = {CONF_USERNAME: 'user', CONF_PASSWORD: 'pass'}
    flow = config_flow.VeSyncFlowHandler()
    flow.hass = hass
    result = await flow.async_step_import(test_dict)

    assert result['data'].get(CONF_USERNAME) == test_dict[CONF_USERNAME]
    assert result['data'].get(CONF_PASSWORD) == test_dict[CONF_PASSWORD]


async def test_config_flow_user_input(hass):
    """Test config flow with user input."""
    flow = config_flow.VeSyncFlowHandler()
    flow.hass = hass
    result = await flow.async_step_user()
    assert result['type'] == data_entry_flow.RESULT_TYPE_FORM

    result = await flow.async_step_user(
        {CONF_USERNAME: 'user', CONF_PASSWORD: 'pass'})
    assert result['type'] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result['data'][CONF_USERNAME] == 'user'
    assert result['data'][CONF_PASSWORD] == 'pass'
