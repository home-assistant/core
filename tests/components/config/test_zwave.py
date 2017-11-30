"""Test Z-Wave config panel."""
import asyncio
import json
from unittest.mock import MagicMock, patch

from homeassistant.bootstrap import async_setup_component
from homeassistant.components import config

from homeassistant.components.zwave import DATA_NETWORK, const
from homeassistant.components.config.zwave import (
    ZWaveNodeValueView, ZWaveNodeGroupView, ZWaveNodeConfigView,
    ZWaveUserCodeView, ZWaveConfigWriteView)
from tests.common import mock_http_component_app
from tests.mock.zwave import MockNode, MockValue, MockEntityValues


VIEW_NAME = 'api:config:zwave:device_config'


@asyncio.coroutine
def test_get_device_config(hass, test_client):
    """Test getting device config."""
    with patch.object(config, 'SECTIONS', ['zwave']):
        yield from async_setup_component(hass, 'config', {})

    client = yield from test_client(hass.http.app)

    def mock_read(path):
        """Mock reading data."""
        return {
            'hello.beer': {
                'free': 'beer',
            },
            'other.entity': {
                'do': 'something',
            },
        }

    with patch('homeassistant.components.config._read', mock_read):
        resp = yield from client.get(
            '/api/config/zwave/device_config/hello.beer')

    assert resp.status == 200
    result = yield from resp.json()

    assert result == {'free': 'beer'}


@asyncio.coroutine
def test_update_device_config(hass, test_client):
    """Test updating device config."""
    with patch.object(config, 'SECTIONS', ['zwave']):
        yield from async_setup_component(hass, 'config', {})

    client = yield from test_client(hass.http.app)

    orig_data = {
        'hello.beer': {
            'ignored': True,
        },
        'other.entity': {
            'polling_intensity': 2,
        },
    }

    def mock_read(path):
        """Mock reading data."""
        return orig_data

    written = []

    def mock_write(path, data):
        """Mock writing data."""
        written.append(data)

    with patch('homeassistant.components.config._read', mock_read), \
            patch('homeassistant.components.config._write', mock_write):
        resp = yield from client.post(
            '/api/config/zwave/device_config/hello.beer', data=json.dumps({
                'polling_intensity': 2
            }))

    assert resp.status == 200
    result = yield from resp.json()
    assert result == {'result': 'ok'}

    orig_data['hello.beer']['polling_intensity'] = 2

    assert written[0] == orig_data


@asyncio.coroutine
def test_update_device_config_invalid_key(hass, test_client):
    """Test updating device config."""
    with patch.object(config, 'SECTIONS', ['zwave']):
        yield from async_setup_component(hass, 'config', {})

    client = yield from test_client(hass.http.app)

    resp = yield from client.post(
        '/api/config/zwave/device_config/invalid_entity', data=json.dumps({
            'polling_intensity': 2
        }))

    assert resp.status == 400


@asyncio.coroutine
def test_update_device_config_invalid_data(hass, test_client):
    """Test updating device config."""
    with patch.object(config, 'SECTIONS', ['zwave']):
        yield from async_setup_component(hass, 'config', {})

    client = yield from test_client(hass.http.app)

    resp = yield from client.post(
        '/api/config/zwave/device_config/hello.beer', data=json.dumps({
            'invalid_option': 2
        }))

    assert resp.status == 400


@asyncio.coroutine
def test_update_device_config_invalid_json(hass, test_client):
    """Test updating device config."""
    with patch.object(config, 'SECTIONS', ['zwave']):
        yield from async_setup_component(hass, 'config', {})

    client = yield from test_client(hass.http.app)

    resp = yield from client.post(
        '/api/config/zwave/device_config/hello.beer', data='not json')

    assert resp.status == 400


@asyncio.coroutine
def test_get_values(hass, test_client):
    """Test getting values on node."""
    app = mock_http_component_app(hass)
    ZWaveNodeValueView().register(app.router)

    node = MockNode(node_id=1)
    value = MockValue(value_id=123456, node=node, label='Test Label',
                      instance=1, index=2, poll_intensity=4)
    values = MockEntityValues(primary=value)
    node2 = MockNode(node_id=2)
    value2 = MockValue(value_id=234567, node=node2, label='Test Label 2')
    values2 = MockEntityValues(primary=value2)
    hass.data[const.DATA_ENTITY_VALUES] = [values, values2]

    client = yield from test_client(app)

    resp = yield from client.get('/api/zwave/values/1')

    assert resp.status == 200
    result = yield from resp.json()

    assert result == {
        '123456': {
            'label': 'Test Label',
            'instance': 1,
            'index': 2,
            'poll_intensity': 4,
        }
    }


@asyncio.coroutine
def test_get_groups(hass, test_client):
    """Test getting groupdata on node."""
    app = mock_http_component_app(hass)
    ZWaveNodeGroupView().register(app.router)

    network = hass.data[DATA_NETWORK] = MagicMock()
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

    network = hass.data[DATA_NETWORK] = MagicMock()
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

    network = hass.data[DATA_NETWORK] = MagicMock()
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

    network = hass.data[DATA_NETWORK] = MagicMock()
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

    network = hass.data[DATA_NETWORK] = MagicMock()
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

    network = hass.data[DATA_NETWORK] = MagicMock()
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

    network = hass.data[DATA_NETWORK] = MagicMock()
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

    network = hass.data[DATA_NETWORK] = MagicMock()
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

    network = hass.data[DATA_NETWORK] = MagicMock()
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

    network = hass.data[DATA_NETWORK] = MagicMock()
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


@asyncio.coroutine
def test_save_config_no_network(hass, test_client):
    """Test saving configuration without network data."""
    app = mock_http_component_app(hass)
    ZWaveConfigWriteView().register(app.router)

    client = yield from test_client(app)

    resp = yield from client.post('/api/zwave/saveconfig')

    assert resp.status == 404
    result = yield from resp.json()
    assert result == {'message': 'No Z-Wave network data found'}


@asyncio.coroutine
def test_save_config(hass, test_client):
    """Test saving configuration."""
    app = mock_http_component_app(hass)
    ZWaveConfigWriteView().register(app.router)

    network = hass.data[DATA_NETWORK] = MagicMock()

    client = yield from test_client(app)

    resp = yield from client.post('/api/zwave/saveconfig')

    assert resp.status == 200
    result = yield from resp.json()
    assert network.write_config.called
    assert result == {'message': 'Z-Wave configuration saved to file.'}
