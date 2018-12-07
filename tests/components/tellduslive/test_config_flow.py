"""Tests for the TelldusLive config flow."""
import asyncio
from unittest.mock import Mock, patch

import pytest

from homeassistant import data_entry_flow
from homeassistant.components.tellduslive import (
    APPLICATION_NAME, DOMAIN, KEY_SCAN_INTERVAL, KEY_HOST, config_flow)

from tests.common import MockDependency, mock_coro


def init_config_flow(hass, side_effect=None):
    """Init a configuration flow."""
    # config_flow.register_flow_implementation(hass, DOMAIN, 'id', 'secret')
    flow = config_flow.FlowHandler()
    flow.hass = hass
    flow._get_auth_url = Mock(  # pylint: disable=W0212
        return_value=mock_coro('https://example.com'),
        side_effect=side_effect)

    return flow


@pytest.fixture
def supports_local_api():
    """Set TelldusLive supports_local_api."""
    return True


@pytest.fixture
def authorize():
    """Set TelldusLive authorize."""
    return True


@pytest.fixture
def mock_tellduslive(supports_local_api, authorize):  # pylint: disable=W0621
    """Mock tellduslive."""
    with MockDependency('tellduslive') as mock_tellduslive_:
        mock_tellduslive_.supports_local_api.return_value = supports_local_api
        mock_tellduslive_.Session().authorize.return_value = authorize
        mock_tellduslive_.Session().access_token = 'token'
        mock_tellduslive_.Session().access_token_secret = 'token_secret'
        yield mock_tellduslive_


async def test_abort_if_already_setup(hass):
    """Test we abort if TelldusLive is already setup."""
    flow = init_config_flow(hass)

    with patch.object(hass.config_entries, 'async_entries', return_value=[{}]):
        result = await flow.async_step_user()
    assert result['type'] == data_entry_flow.RESULT_TYPE_ABORT
    assert result['reason'] == 'already_setup'

    with patch.object(hass.config_entries, 'async_entries', return_value=[{}]):
        result = await flow.async_step_import(None)
    assert result['type'] == data_entry_flow.RESULT_TYPE_ABORT
    assert result['reason'] == 'already_setup'


async def test_full_flow_implementation(hass, mock_tellduslive):  # noqa pylint: disable=W0621
    """Test registering an implementation and finishing flow works."""
    flow = init_config_flow(hass)
    result = await flow.async_step_discovery(['localhost', 'tellstick'])
    assert result['type'] == data_entry_flow.RESULT_TYPE_FORM
    assert result['step_id'] == 'user'

    result = await flow.async_step_user()
    assert result['type'] == data_entry_flow.RESULT_TYPE_FORM
    assert result['step_id'] == 'user'

    result = await flow.async_step_user({'host': 'localhost'})
    assert result['type'] == data_entry_flow.RESULT_TYPE_FORM
    assert result['step_id'] == 'auth'
    assert result['description_placeholders'] == {
        'auth_url': 'https://example.com',
        'app_name': APPLICATION_NAME,
    }

    result = await flow.async_step_auth('')
    assert result['type'] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result['title'] == 'localhost'
    assert result['data']['host'] == 'localhost'
    assert result['data']['scan_interval'] == 60
    assert result['data']['session'] == {
        'token': 'token',
        'host': 'localhost'
    }


async def test_step_import(hass, mock_tellduslive):  # pylint: disable=W0621
    """Test that we trigger import when configuring with client."""
    flow = init_config_flow(hass)

    result = await flow.async_step_import({
        KEY_HOST: DOMAIN,
        KEY_SCAN_INTERVAL: 0,
    })
    assert result['type'] == data_entry_flow.RESULT_TYPE_FORM
    assert result['step_id'] == 'auth'


@pytest.mark.parametrize('authorize', [False])
async def test_wrong_auth_flow_implementation(hass, mock_tellduslive):  # noqa pylint: disable=W0621
    """Test wrong code."""
    flow = init_config_flow(hass)

    await flow.async_step_user()
    result = await flow.async_step_auth('')
    assert result['type'] == data_entry_flow.RESULT_TYPE_FORM
    assert result['step_id'] == 'auth'


async def test_not_pick_host_if_only_one(hass):
    """Test we allow picking host if we have one."""
    flow = init_config_flow(hass)

    result = await flow.async_step_user()
    assert result['type'] == data_entry_flow.RESULT_TYPE_FORM
    assert result['step_id'] == 'auth'


async def test_abort_if_timeout_generating_auth_url(hass):
    """Test we abort if generating authorize url fails."""
    flow = init_config_flow(hass, side_effect=asyncio.TimeoutError)

    result = await flow.async_step_user()
    assert result['type'] == data_entry_flow.RESULT_TYPE_ABORT
    assert result['reason'] == 'authorize_url_timeout'


async def test_abort_if_exception_generating_auth_url(hass):
    """Test we abort if generating authorize url blows up."""
    flow = init_config_flow(hass, side_effect=ValueError)

    result = await flow.async_step_user()
    assert result['type'] == data_entry_flow.RESULT_TYPE_ABORT
    assert result['reason'] == 'authorize_url_fail'


# async def test_abort_no_code(hass):
#     """Test if no code is given to step_code."""
#     flow = init_config_flow(hass)

#     result = await flow.async_step_code()
#     assert result['type'] == data_entry_flow.RESULT_TYPE_ABORT
#     assert result['reason'] == 'no_code'
