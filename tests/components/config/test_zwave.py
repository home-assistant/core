import asyncio
from copy import deepcopy
import json
from unittest.mock import patch, MagicMock

import pytest
import voluptuous as vol

from homeassistant.components import zwave
from homeassistant.bootstrap import async_setup_component
from homeassistant.components import config
from homeassistant.components.config import zwave as zwave_conf
from homeassistant.components.config.zwave import DeviceConfigView
from tests.common import mock_http_component_app, mock_coro, mock_coro_func


import homeassistant.helpers.config_validation as cv


@pytest.fixture(autouse=True)
def patch_schema():
    """Temporary patch while waiting for other PR to get merged."""
    with patch.object(zwave_conf, '_ZWAVE_CUSTOMIZE_SCHEMA_ENTRY', vol.Schema({
        vol.Optional(zwave.CONF_POLLING_INTENSITY): cv.positive_int,
        vol.Optional(zwave.CONF_IGNORED, default=zwave.DEFAULT_CONF_IGNORED):
            cv.boolean,
        vol.Optional(zwave.CONF_REFRESH_VALUE,
                     default=zwave.DEFAULT_CONF_REFRESH_VALUE): cv.boolean,
        vol.Optional(zwave.CONF_REFRESH_DELAY,
                     default=zwave.DEFAULT_CONF_REFRESH_DELAY): cv.positive_int
    })):
        yield


@asyncio.coroutine
def test_get_device_config(hass, test_client):
    """Test getting device config."""
    app = mock_http_component_app(hass)

    with patch.object(config, 'SECTIONS', ['zwave']):
        yield from async_setup_component(hass, 'config', {})

    hass.http.views[DeviceConfigView.name].register(app.router)

    client = yield from test_client(app)

    with patch.object(hass.loop, 'run_in_executor', mock_coro_func({
                   'hello.beer': {
                       'free': 'beer',
                   },
                   'other.entity': {
                       'do': 'something',
                   },
               })):
        resp = yield from client.get(
            '/api/config/zwave/device_config/hello.beer')

    assert resp.status == 200
    result = yield from resp.json()

    assert result == {'free': 'beer'}


@asyncio.coroutine
def test_update_device_config(hass, test_client):
    """Test updating device config."""
    app = mock_http_component_app(hass)

    with patch.object(config, 'SECTIONS', ['zwave']):
        yield from async_setup_component(hass, 'config', {})

    hass.http.views[DeviceConfigView.name].register(app.router)

    client = yield from test_client(app)

    orig_data = {
        'hello.beer': {
            'ignored': True,
        },
        'other.entity': {
            'polling_intensity': 2,
        },
    }
    mock_executor = MagicMock(return_value=mock_coro(deepcopy(orig_data))())

    with patch.object(hass.loop, 'run_in_executor', mock_executor):
        resp = yield from client.post(
            '/api/config/zwave/device_config/hello.beer', data=json.dumps({
                'polling_intensity': 2
            }))

    assert resp.status == 200
    result = yield from resp.json()
    assert result == {'result': 'ok'}

    assert len(mock_executor.mock_calls) == 2
    data = mock_executor.mock_calls[1][1][3]

    orig_data['hello.beer']['polling_intensity'] = 2

    assert orig_data == data
