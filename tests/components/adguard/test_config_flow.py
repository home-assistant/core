"""Tests for the AdGuard Home config flow."""
import aiohttp

from homeassistant import data_entry_flow
from homeassistant.components.adguard import config_flow
from homeassistant.components.adguard.const import DOMAIN
from homeassistant.const import (
    CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_SSL, CONF_USERNAME,
    CONF_VERIFY_SSL)

from tests.common import MockConfigEntry

FIXTURE_USER_INPUT = {
    CONF_HOST: '127.0.0.1',
    CONF_PORT: 3000,
    CONF_USERNAME: 'user',
    CONF_PASSWORD: 'pass',
    CONF_SSL: True,
    CONF_VERIFY_SSL: True,
}


async def test_show_authenticate_form(hass):
    """Test that the setup form is served."""
    flow = config_flow.AdGuardHomeFlowHandler()
    flow.hass = hass
    result = await flow.async_step_user(user_input=None)

    assert result['type'] == data_entry_flow.RESULT_TYPE_FORM
    assert result['step_id'] == 'user'


async def test_connection_error(hass, aioclient_mock):
    """Test we show user form on AdGuard Home connection error."""
    aioclient_mock.get(
        "{}://{}:{}/control/status".format(
            'https' if FIXTURE_USER_INPUT[CONF_SSL] else 'http',
            FIXTURE_USER_INPUT[CONF_HOST],
            FIXTURE_USER_INPUT[CONF_PORT],
        ),
        exc=aiohttp.ClientError,
    )

    flow = config_flow.AdGuardHomeFlowHandler()
    flow.hass = hass
    result = await flow.async_step_user(user_input=FIXTURE_USER_INPUT)

    assert result['type'] == data_entry_flow.RESULT_TYPE_FORM
    assert result['step_id'] == 'user'
    assert result['errors'] == {'base': 'connection_error'}


async def test_full_flow_implementation(hass, aioclient_mock):
    """Test registering an integration and finishing flow works."""
    aioclient_mock.get(
        "{}://{}:{}/control/status".format(
            'https' if FIXTURE_USER_INPUT[CONF_SSL] else 'http',
            FIXTURE_USER_INPUT[CONF_HOST],
            FIXTURE_USER_INPUT[CONF_PORT],
        ),
        json={'version': '1.0'},
        headers={'Content-Type': 'application/json'},
    )

    flow = config_flow.AdGuardHomeFlowHandler()
    flow.hass = hass
    result = await flow.async_step_user(user_input=None)
    assert result['type'] == data_entry_flow.RESULT_TYPE_FORM
    assert result['step_id'] == 'user'

    result = await flow.async_step_user(user_input=FIXTURE_USER_INPUT)
    assert result['type'] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result['title'] == FIXTURE_USER_INPUT[CONF_HOST]
    assert result['data'][CONF_HOST] == FIXTURE_USER_INPUT[CONF_HOST]
    assert result['data'][CONF_PASSWORD] == FIXTURE_USER_INPUT[CONF_PASSWORD]
    assert result['data'][CONF_PORT] == FIXTURE_USER_INPUT[CONF_PORT]
    assert result['data'][CONF_SSL] == FIXTURE_USER_INPUT[CONF_SSL]
    assert result['data'][CONF_USERNAME] == FIXTURE_USER_INPUT[CONF_USERNAME]
    assert (
        result['data'][CONF_VERIFY_SSL] == FIXTURE_USER_INPUT[CONF_VERIFY_SSL]
    )


async def test_integration_already_exists(hass):
    """Test we only allow a single config flow."""
    MockConfigEntry(domain=DOMAIN).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={'source': 'user'}
    )
    assert result['type'] == 'abort'
    assert result['reason'] == 'single_instance_allowed'


async def test_hassio_single_instance(hass):
    """Test we only allow a single config flow."""
    MockConfigEntry(domain='adguard', data={'host': '1.2.3.4'}).add_to_hass(
        hass
    )

    result = await hass.config_entries.flow.async_init(
        'adguard', context={'source': 'hassio'}
    )
    assert result['type'] == data_entry_flow.RESULT_TYPE_ABORT
    assert result['reason'] == 'single_instance_allowed'


async def test_hassio_confirm(hass, aioclient_mock):
    """Test we can finish a config flow."""
    aioclient_mock.get(
        "http://mock-adguard:3000/control/status",
        json={'version': '1.0'},
        headers={'Content-Type': 'application/json'},
    )

    result = await hass.config_entries.flow.async_init(
        'adguard',
        data={
            'addon': 'AdGuard Home Addon',
            'host': 'mock-adguard',
            'port': 3000,
        },
        context={'source': 'hassio'},
    )
    assert result['type'] == data_entry_flow.RESULT_TYPE_FORM
    assert result['step_id'] == 'hassio_confirm'
    assert result['description_placeholders'] == {
        'addon': 'AdGuard Home Addon'
    }

    result = await hass.config_entries.flow.async_configure(
        result['flow_id'], {}
    )
    assert result['type'] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result['title'] == 'AdGuard Home Addon'
    assert result['data'][CONF_HOST] == 'mock-adguard'
    assert result['data'][CONF_PASSWORD] is None
    assert result['data'][CONF_PORT] == 3000
    assert result['data'][CONF_SSL] is False
    assert result['data'][CONF_USERNAME] is None
    assert result['data'][CONF_VERIFY_SSL]


async def test_hassio_connection_error(hass, aioclient_mock):
    """Test we show hassio confirm form on AdGuard Home connection error."""
    aioclient_mock.get(
        "http://mock-adguard:3000/control/status",
        exc=aiohttp.ClientError,
    )

    result = await hass.config_entries.flow.async_init(
        'adguard',
        data={
            'addon': 'AdGuard Home Addon',
            'host': 'mock-adguard',
            'port': 3000,
        },
        context={'source': 'hassio'},
    )

    result = await hass.config_entries.flow.async_configure(
        result['flow_id'], {}
    )

    assert result['type'] == data_entry_flow.RESULT_TYPE_FORM
    assert result['step_id'] == 'hassio_confirm'
    assert result['errors'] == {'base': 'connection_error'}
