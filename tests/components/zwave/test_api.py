"""Test Z-Wave config panel."""
import asyncio
from unittest.mock import MagicMock
from homeassistant.components.zwave import ZWAVE_NETWORK, const
from homeassistant.components.zwave.api import (
    ZWaveNodeGroupView, ZWaveNodeConfigView, ZWaveUserCodeView)
from tests.common import mock_http_component_app
from tests.mock.zwave import MockNode, MockValue


@asyncio.coroutine
def test_get_groups(hass, test_client):
    """Test getting groupdata on node."""
    app = mock_http_component_app(hass)
    ZWaveNodeGroupView().register(app.router)

    network = hass.data[ZWAVE_NETWORK] = MagicMock()
    node = MockNode(node_id=2)
    node.groups.associations = 'assoc'
    node.groups.associations_instances = 'inst'
    node.groups.label = 'the label'
    node.groups.max_associations = 'max'
    node.groups = {1: node.groups}
    network.nodes = {2: node}

    client = yield from test_client(app)

    resp = yield from client.get('/api/zwave/groups/2')

    assert resp.status == 200
    result = yield from resp.json()

    assert result == {
        '1': {
            'association_instances': 'inst',
            'associations': 'assoc',
            'label': 'the label',
            'max_associations': 'max'
        }
    }


@asyncio.coroutine
def test_get_groups_nogroups(hass, test_client):
    """Test getting groupdata on node with no groups."""
    app = mock_http_component_app(hass)
    ZWaveNodeGroupView().register(app.router)

    network = hass.data[ZWAVE_NETWORK] = MagicMock()
    node = MockNode(node_id=2)

    network.nodes = {2: node}

    client = yield from test_client(app)

    resp = yield from client.get('/api/zwave/groups/2')

    assert resp.status == 200
    result = yield from resp.json()

    assert result == {}


@asyncio.coroutine
def test_get_groups_nonode(hass, test_client):
    """Test getting groupdata on nonexisting node."""
    app = mock_http_component_app(hass)
    ZWaveNodeGroupView().register(app.router)

    network = hass.data[ZWAVE_NETWORK] = MagicMock()
    network.nodes = {1: 1, 5: 5}

    client = yield from test_client(app)

    resp = yield from client.get('/api/zwave/groups/2')

    assert resp.status == 404
    result = yield from resp.json()

    assert result == {'message': 'Node not found'}


@asyncio.coroutine
def test_get_config(hass, test_client):
    """Test getting config on node."""
    app = mock_http_component_app(hass)
    ZWaveNodeConfigView().register(app.router)

    network = hass.data[ZWAVE_NETWORK] = MagicMock()
    node = MockNode(node_id=2)
    value = MockValue(
         index=12,
         command_class=const.COMMAND_CLASS_CONFIGURATION)
    value.label = 'label'
    value.help = 'help'
    value.type = 'type'
    value.data = 'data'
    value.data_items = ['item1', 'item2']
    value.max = 'max'
    value.min = 'min'
    node.values = {12: value}
    network.nodes = {2: node}
    node.get_values.return_value = node.values

    client = yield from test_client(app)

    resp = yield from client.get('/api/zwave/config/2')

    assert resp.status == 200
    result = yield from resp.json()

    assert result == {'12': {'data': 'data',
                             'data_items': ['item1', 'item2'],
                             'help': 'help',
                             'label': 'label',
                             'max': 'max',
                             'min': 'min',
                             'type': 'type'}}


@asyncio.coroutine
def test_get_config_noconfig_node(hass, test_client):
    """Test getting config on node without config."""
    app = mock_http_component_app(hass)
    ZWaveNodeConfigView().register(app.router)

    network = hass.data[ZWAVE_NETWORK] = MagicMock()
    node = MockNode(node_id=2)

    network.nodes = {2: node}
    node.get_values.return_value = node.values

    client = yield from test_client(app)

    resp = yield from client.get('/api/zwave/config/2')

    assert resp.status == 200
    result = yield from resp.json()

    assert result == {}


@asyncio.coroutine
def test_get_config_nonode(hass, test_client):
    """Test getting config on nonexisting node."""
    app = mock_http_component_app(hass)
    ZWaveNodeConfigView().register(app.router)

    network = hass.data[ZWAVE_NETWORK] = MagicMock()
    network.nodes = {1: 1, 5: 5}

    client = yield from test_client(app)

    resp = yield from client.get('/api/zwave/config/2')

    assert resp.status == 404
    result = yield from resp.json()

    assert result == {'message': 'Node not found'}


@asyncio.coroutine
def test_get_usercodes_nonode(hass, test_client):
    """Test getting usercodes on nonexisting node."""
    app = mock_http_component_app(hass)
    ZWaveUserCodeView().register(app.router)

    network = hass.data[ZWAVE_NETWORK] = MagicMock()
    network.nodes = {1: 1, 5: 5}

    client = yield from test_client(app)

    resp = yield from client.get('/api/zwave/usercodes/2')

    assert resp.status == 404
    result = yield from resp.json()

    assert result == {'message': 'Node not found'}


@asyncio.coroutine
def test_get_usercodes(hass, test_client):
    """Test getting usercodes on node."""
    app = mock_http_component_app(hass)
    ZWaveUserCodeView().register(app.router)

    network = hass.data[ZWAVE_NETWORK] = MagicMock()
    node = MockNode(node_id=18,
                    command_classes=[const.COMMAND_CLASS_USER_CODE])
    value = MockValue(
         index=0,
         command_class=const.COMMAND_CLASS_USER_CODE)
    value.genre = const.GENRE_USER
    value.label = 'label'
    value.data = '1234'
    node.values = {0: value}
    network.nodes = {18: node}
    node.get_values.return_value = node.values

    client = yield from test_client(app)

    resp = yield from client.get('/api/zwave/usercodes/18')

    assert resp.status == 200
    result = yield from resp.json()

    assert result == {'0': {'code': '1234',
                            'label': 'label',
                            'length': 4}}


@asyncio.coroutine
def test_get_usercode_nousercode_node(hass, test_client):
    """Test getting usercodes on node without usercodes."""
    app = mock_http_component_app(hass)
    ZWaveUserCodeView().register(app.router)

    network = hass.data[ZWAVE_NETWORK] = MagicMock()
    node = MockNode(node_id=18)

    network.nodes = {18: node}
    node.get_values.return_value = node.values

    client = yield from test_client(app)

    resp = yield from client.get('/api/zwave/usercodes/18')

    assert resp.status == 200
    result = yield from resp.json()

    assert result == {}


@asyncio.coroutine
def test_get_usercodes_no_genreuser(hass, test_client):
    """Test getting usercodes on node missing genre user."""
    app = mock_http_component_app(hass)
    ZWaveUserCodeView().register(app.router)

    network = hass.data[ZWAVE_NETWORK] = MagicMock()
    node = MockNode(node_id=18,
                    command_classes=[const.COMMAND_CLASS_USER_CODE])
    value = MockValue(
         index=0,
         command_class=const.COMMAND_CLASS_USER_CODE)
    value.genre = const.GENRE_SYSTEM
    value.label = 'label'
    value.data = '1234'
    node.values = {0: value}
    network.nodes = {18: node}
    node.get_values.return_value = node.values

    client = yield from test_client(app)

    resp = yield from client.get('/api/zwave/usercodes/18')

    assert resp.status == 200
    result = yield from resp.json()

    assert result == {}
