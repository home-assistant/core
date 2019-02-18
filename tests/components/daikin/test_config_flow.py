# pylint: disable=W0621
"""Tests for the Daikin config flow."""
import asyncio

import pytest

from homeassistant import data_entry_flow
from homeassistant.components.daikin import config_flow
from homeassistant.components.daikin.const import KEY_HOST, KEY_IP, KEY_MAC

from tests.common import MockConfigEntry, MockDependency

MAC = 'AABBCCDDEEFF'
HOST = '127.0.0.1'


def init_config_flow(hass):
    """Init a configuration flow."""
    flow = config_flow.FlowHandler()
    flow.hass = hass
    return flow


@pytest.fixture
def mock_daikin():
    """Mock tellduslive."""
    with MockDependency('pydaikin.appliance') as mock_daikin_:
        mock_daikin_.Appliance().values.get.return_value = 'AABBCCDDEEFF'
        yield mock_daikin_


async def test_user(hass, mock_daikin):
    """Test user config."""
    flow = init_config_flow(hass)

    result = await flow.async_step_user()
    assert result['type'] == data_entry_flow.RESULT_TYPE_FORM
    assert result['step_id'] == 'user'

    result = await flow.async_step_user({KEY_HOST: HOST})
    assert result['type'] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result['title'] == HOST
    assert result['data'][KEY_HOST] == HOST
    assert result['data'][KEY_MAC] == MAC


async def test_abort_if_already_setup(hass, mock_daikin):
    """Test we abort if Daikin is already setup."""
    flow = init_config_flow(hass)
    MockConfigEntry(domain='daikin', data={KEY_MAC: MAC}).add_to_hass(hass)

    result = await flow.async_step_user({KEY_HOST: HOST})
    assert result['type'] == data_entry_flow.RESULT_TYPE_ABORT
    assert result['reason'] == 'already_configured'


async def test_import(hass, mock_daikin):
    """Test import step."""
    flow = init_config_flow(hass)

    result = await flow.async_step_import({})
    assert result['type'] == data_entry_flow.RESULT_TYPE_FORM
    assert result['step_id'] == 'user'

    result = await flow.async_step_import({KEY_HOST: HOST})
    assert result['type'] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result['title'] == HOST
    assert result['data'][KEY_HOST] == HOST
    assert result['data'][KEY_MAC] == MAC


async def test_discovery(hass, mock_daikin):
    """Test discovery step."""
    flow = init_config_flow(hass)

    result = await flow.async_step_discovery({KEY_IP: HOST, KEY_MAC: MAC})
    assert result['type'] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result['title'] == HOST
    assert result['data'][KEY_HOST] == HOST
    assert result['data'][KEY_MAC] == MAC


@pytest.mark.parametrize('s_effect,reason',
                         [(asyncio.TimeoutError, 'device_timeout'),
                          (Exception, 'device_fail')])
async def test_device_abort(hass, mock_daikin, s_effect, reason):
    """Test device abort."""
    flow = init_config_flow(hass)
    mock_daikin.Appliance.side_effect = s_effect

    result = await flow.async_step_user({KEY_HOST: HOST})
    assert result['type'] == data_entry_flow.RESULT_TYPE_ABORT
    assert result['reason'] == reason
