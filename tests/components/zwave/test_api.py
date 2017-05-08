"""Test Z-Wave config panel."""
import asyncio
from unittest.mock import MagicMock
from homeassistant.components.zwave import ZWAVE_NETWORK
from homeassistant.components.zwave.api import (
    ZWaveNodeGroupView, ZWaveNodeConfigView, ZWaveUserCodeView)
from tests.common import mock_http_component_app


@asyncio.coroutine
def test_get_groups_nogroups_node(hass, test_client, mock_openzwave):
    """Test getting groupdata on node without groups."""
    hass.data[ZWAVE_NETWORK] = MagicMock()
    app = mock_http_component_app(hass)
    ZWaveGroup = mock_openzwave.group.ZWaveGroup
    group = MagicMock()
    ZWaveGroup.return_value = group
    ZWaveNodeGroupView().register(app.router)

    client = yield from test_client(app)

    resp = yield from client.get('/api/zwave/groups/2')

    assert resp.status == 200
    result = yield from resp.json()

    assert result == {}


@asyncio.coroutine
def test_get_config_noconfig_node(hass, test_client):
    """Test getting config on node without config."""
    hass.data[ZWAVE_NETWORK] = MagicMock()
    app = mock_http_component_app(hass)

    ZWaveNodeConfigView().register(app.router)

    client = yield from test_client(app)

    resp = yield from client.get('/api/zwave/config/2')

    assert resp.status == 200
    result = yield from resp.json()

    assert result == {}


@asyncio.coroutine
def test_get_usercodes_nousercode_node(hass, test_client):
    """Test getting usercodes on node without usercodes."""
    hass.data[ZWAVE_NETWORK] = MagicMock()
    app = mock_http_component_app(hass)

    ZWaveUserCodeView().register(app.router)

    client = yield from test_client(app)

    resp = yield from client.get('/api/zwave/usercodes/18')

    assert resp.status == 200
    result = yield from resp.json()

    assert result == {}
