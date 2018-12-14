# flake8: noqa pylint: skip-file
"""Tests for the Daikin config flow."""
import asyncio
from unittest.mock import Mock, patch

import pytest

from homeassistant import data_entry_flow
from homeassistant.components.daikin.const import (KEY_HOST, KEY_IP, KEY_MAC)
from homeassistant.components.daikin import config_flow
from tests.common import MockDependency


def init_config_flow(hass, side_effect=None):
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

    result = await flow.async_step_user({KEY_HOST: '127.0.0.1'})
    assert result['type'] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result['title'] == '127.0.0.1'
    assert result['data'][KEY_HOST] == '127.0.0.1'
    assert result['data'][KEY_MAC] == 'AABBCCDDEEFF'


async def test_abort_if_already_setup(hass, mock_daikin):
    """Test we abort if Daikin is already setup."""
    flow = init_config_flow(hass)

    entry = Mock()
    entry.data = {KEY_MAC: 'AABBCCDDEEFF'}
    with patch.object(
            hass.config_entries, 'async_entries', return_value=[entry]):
        result = await flow.async_step_user({KEY_HOST: '127.0.0.1'})

    assert result['type'] == data_entry_flow.RESULT_TYPE_ABORT
    assert result['reason'] == 'already_configured'


async def test_import(hass, mock_daikin):
    """Test import step."""
    flow = init_config_flow(hass)

    result = await flow.async_step_import({})
    assert result['type'] == data_entry_flow.RESULT_TYPE_FORM
    assert result['step_id'] == 'user'

    result = await flow.async_step_import({KEY_HOST: '127.0.0.1'})
    assert result['type'] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result['title'] == '127.0.0.1'
    assert result['data'][KEY_HOST] == '127.0.0.1'
    assert result['data'][KEY_MAC] == 'AABBCCDDEEFF'


async def test_discovery(hass, mock_daikin):
    """Test discovery step."""
    flow = init_config_flow(hass)

    result = await flow.async_step_discovery({
        KEY_IP: '127.0.0.1',
        KEY_MAC: 'AABBCCDDEEFF'
    })
    assert result['type'] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result['title'] == '127.0.0.1'
    assert result['data'][KEY_HOST] == '127.0.0.1'
    assert result['data'][KEY_MAC] == 'AABBCCDDEEFF'


async def test_device_abort(hass, mock_daikin):
    """Test device abort."""
    flow = init_config_flow(hass)

    with patch.object(
            flow.hass, 'async_add_executor_job',
            side_effect=asyncio.TimeoutError):
        result = await flow.async_step_user({KEY_HOST: '127.0.0.1'})
    assert result['type'] == data_entry_flow.RESULT_TYPE_ABORT
    assert result['reason'] == 'device_timeout'

    with patch.object(
            flow.hass, 'async_add_executor_job', side_effect=Exception):
        result = await flow.async_step_user({KEY_HOST: '127.0.0.1'})
    assert result['type'] == data_entry_flow.RESULT_TYPE_ABORT
    assert result['reason'] == 'device_fail'
