"""Test hassbian config."""
import asyncio
from unittest.mock import patch

from homeassistant.bootstrap import async_setup_component
from homeassistant.components import config
from homeassistant.components.config.core import CheckConfigView
from tests.common import mock_http_component_app, mock_coro


@asyncio.coroutine
def test_validate_config_ok(hass, test_client):
    """Test checking config."""
    app = mock_http_component_app(hass)
    with patch.object(config, 'SECTIONS', ['core']):
        yield from async_setup_component(hass, 'config', {})

    # yield from hass.async_block_till_done()
    yield from asyncio.sleep(0.1, loop=hass.loop)

    hass.http.views[CheckConfigView.name].register(app.router)
    client = yield from test_client(app)

    with patch(
        'homeassistant.components.config.core.async_check_ha_config_file',
            return_value=mock_coro()):
        resp = yield from client.post('/api/config/core/check_config')

    assert resp.status == 200
    result = yield from resp.json()
    assert result['result'] == 'valid'
    assert result['errors'] is None

    with patch(
        'homeassistant.components.config.core.async_check_ha_config_file',
            return_value=mock_coro('beer')):
        resp = yield from client.post('/api/config/core/check_config')

    assert resp.status == 200
    result = yield from resp.json()
    assert result['result'] == 'invalid'
    assert result['errors'] == 'beer'
