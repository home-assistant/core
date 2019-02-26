from datetime import datetime

from asynctest import patch, MagicMock
import pytest
import asyncio
import os
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import (
    CONF_PASSWORD, CONF_PLATFORM)
from homeassistant.setup import async_setup_component, async_when_setup
import homeassistant.components.http as http
import homeassistant.components.api as api
import homeassistant.components.configurator as configurator
import nokia
import callee
from aiohttp.web_request import BaseRequest
import homeassistant.components.sensor.withings as withings


PLATFORM_NAME = 'withings'


async def test_async_setup_platform(hass):
    profile = 'person 1'
    slug = 'person_1'

    config = {
        http.DOMAIN: {},
        api.DOMAIN: {
            'base_url': 'http://localhost/'
        },
        SENSOR_DOMAIN: [
            {
                CONF_PLATFORM: PLATFORM_NAME,
                withings.CONF_CLIENT_ID: 'my_client_id',
                withings.CONF_SECRET: 'my_secret',
                withings.CONF_PROFILE: profile
            }
        ]
    }

    credentials_file_path = hass.config.path(withings.WITHINGS_CONFIG_FILE.format(
        'my_client_id',
        slug
    ))

    if os.path.isfile(credentials_file_path):
        os.remove(credentials_file_path)

    result = await async_setup_component(hass, 'http', config)
    assert result

    result = await async_setup_component(hass, 'api', config)
    assert result

    with patch.object(hass.http, 'register_view', wraps=hass.http.register_view) as register_view_spy,\
            patch('homeassistant.components.configurator.async_request_config', wraps=configurator.async_request_config) as async_request_config_spy, \
            patch('homeassistant.components.configurator.async_request_done', wraps=configurator.async_request_done) as async_request_done_spy, \
            patch('homeassistant.components.sensor.withings.async_initialize') as async_initialize_mock:

        # Simulate an initial setup.
        result = await async_setup_component(hass, SENSOR_DOMAIN, config)
        assert result
        assert withings.DATA_CONFIGURING in hass.data
        assert 'person_1' in hass.data[withings.DATA_CONFIGURING]
        configuring: withings.WithingsConfiguring = hass.data[withings.DATA_CONFIGURING][slug]
        assert isinstance(configuring, withings.WithingsConfiguring)
        assert callable(configuring.oauth_initialize_callback)
        register_view_spy.assert_called_with(withings.WithingsAuthCallbackView(slug))
        async_request_config_spy.assert_called_with(
            hass,
            'Withings',
            description=(
                "Authorization is required to get access to Withings data. After clicking the button below, be sure to choose the profile that maps to '{}'.".format(profile)
            ),
            link_name="Click here to authorize Home Assistant.",
            link_url=callee.StartsWith('https://account.withings.com/oauth2_user/authorize2?response_type=code&client_id=my_client_id&redirect_uri=http%3A%2F%2F127.0.0.1%3A8123%2Fapi%2Fwithings%2Fcallback&scope=user.info%2Cuser.metrics%2Cuser.activity&state=')
        )

        # Get the instance of WithingsAuthCallbackView used when registering.
        args = register_view_spy.call_args_list
        callback_view = args[0][0][0]

        get_credentials_mock = patch.object(configuring.auth_client, 'get_credentials', return_value=nokia.NokiaCredentials)
        get_credentials_mock.start()

        # Simulate a request to the callback view.
        request = MagicMock(spec=BaseRequest)
        request.app = {
            'hass': hass
        }
        request.query = {
            'state': 'my_state',
            'code': 'my_code'
        }

        callback_view.get(request)
        await hass.async_block_till_done()

        configuring.auth_client.get_credentials.assert_called_with('my_code')
        async_initialize_mock.assert_called()
        async_request_done_spy.assert_called()


async def test_async_setup_platform_from_saved_credentials(hass):
    profile = 'person 1'
    slug = 'person_1'

    config = {
        http.DOMAIN: {},
        api.DOMAIN: {
            'base_url': 'http://localhost/'
        },
        SENSOR_DOMAIN: [
            {
                CONF_PLATFORM: PLATFORM_NAME,
                withings.CONF_CLIENT_ID: 'my_client_id',
                withings.CONF_SECRET: 'my_secret',
                withings.CONF_PROFILE: profile
            }
        ]
    }

    withings._write_credentials_to_file(
        hass,
        withings.WITHINGS_CONFIG_FILE.format(
            'my_client_id',
            slug
        ),
        nokia.NokiaCredentials()
    )

    with patch('homeassistant.components.sensor.withings.async_initialize') as async_initialize_mock:
        result = await async_setup_component(hass, 'http', config)
        assert result

        result = await async_setup_component(hass, 'api', config)
        assert result

        result = await async_setup_component(hass, SENSOR_DOMAIN, config)
        assert result

        async_initialize_mock.assert_called()


async def test_initialize_new_credentials(hass):
    profile = 'person 1'
    slug = 'person_1'

    config = {
        CONF_PLATFORM: PLATFORM_NAME,
        withings.CONF_CLIENT_ID: 'my_client_id',
        withings.CONF_SECRET: 'my_secret',
        withings.CONF_PROFILE: profile,
        withings.CONF_MEASUREMENTS: list(withings.CONF_SENSORS.keys())
    }

    add_entities_mock = MagicMock()

    configuring = withings.WithingsConfiguring(
        hass,
        config,
        add_entities_mock,
        slug,
        '/tmp/testfile',
        None,
        None,
    )

    creds = nokia.NokiaCredentials(
        None,
        9999999999
    )

    await withings.async_initialize(configuring, creds)

    sensors = add_entities_mock.call_args_list[0][0][0]
    measurements = []
    for sensor in sensors:
        measurements.append(sensor._attribute.measurement)

    assert set(measurements) == set(withings.WITHINGS_MEASUREMENTS_MAP.keys())


async def test_initialize_credentials_refreshed(hass):
    profile = 'person 1'
    slug = 'person_1'

    config = {
        CONF_PLATFORM: PLATFORM_NAME,
        withings.CONF_CLIENT_ID: 'my_client_id',
        withings.CONF_SECRET: 'my_secret',
        withings.CONF_PROFILE: profile,
        withings.CONF_MEASUREMENTS: list(withings.CONF_SENSORS.keys())
    }

    add_entities_mock = MagicMock()

    configuring = withings.WithingsConfiguring(
        hass,
        config,
        add_entities_mock,
        slug,
        '/tmp/testfile',
        None,
        None,
    )

    creds = nokia.NokiaCredentials(
        None,
        9999999999
    )

    data_manager = await withings.async_initialize(configuring, creds)

    with patch('homeassistant.components.sensor.withings.credentials_refreshed', wraps=withings.credentials_refreshed) as credentials_refreshed_spy:
        data_manager._api.set_token({
            'expires_in': 22222,
            'access_token': 'ACCESS_TOKEN',
            'refresh_token': 'REFRESH_TOKEN'
        })

        credentials_refreshed_spy.assert_called()

