"""Test Z-Wave config panel."""
import asyncio
from unittest.mock import MagicMock
from homeassistant.components.zwave import ZWAVE_NETWORK, const
from homeassistant.components.zwave.api import (
    ZWaveNodeGroupView, ZWaveNodeConfigView, ZWaveUserCodeView)
from tests.common import mock_http_component_app
from tests.mock.zwave import MockNode, MockValue


@asyncio.coroutine
def test_get_groups(hass, test_client, mock_openzwave):
    """Test getting groupdata on node."""
    app = mock_http_component_app(hass)
    ZWaveNodeGroupView().register(app.router)

    network = hass.data[ZWAVE_NETWORK] = MagicMock()
    network.nodes.get().groups_to_dict.return_value = {'1': None}
    group = MagicMock()
    group.associations = 'assoc'
    group.associations_instances = 'inst'
    group.label = 'the label'
    group.max_associations = 'max'
    mock_openzwave.group.ZWaveGroup.return_value = group

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
def test_get_groups_nogroups(hass, test_client, mock_openzwave):
    """Test getting groupdata on node without groups."""
    app = mock_http_component_app(hass)
    ZWaveNodeGroupView().register(app.router)

    network = hass.data[ZWAVE_NETWORK] = MagicMock()
    network.nodes.get().groups_to_dict.return_value = {}
    group = MagicMock()
    group.associations = None
    group.associations_instances = None
    group.label = None
    group.max_associations = None
    mock_openzwave.group.ZWaveGroup.return_value = group

    client = yield from test_client(app)

    resp = yield from client.get('/api/zwave/groups/2')

    assert resp.status == 200
    result = yield from resp.json()

    assert result == {}


@asyncio.coroutine
def test_get_groups_nonode(hass, test_client, mock_openzwave):
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
def test_get_config_noconfig_node(hass, test_client):
    """Test getting config on node without config."""
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
    network.nodes = node
    node.get_values.return_value = node.value

    client = yield from test_client(app)

    resp = yield from client.get('/api/zwave/config/2')

    assert resp.status == 200
    result = yield from resp.json()

    assert result == {'label': 'label'}


@asyncio.coroutine
def test_get_config_nonode(hass, test_client):
    """Test getting groupdata on nonexisting node."""
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


@asyncio.coroutine
def test_get_usercodes_nonode(hass, test_client):
    """Test getting groupdata on nonexisting node."""
    app = mock_http_component_app(hass)
    ZWaveUserCodeView().register(app.router)

    network = hass.data[ZWAVE_NETWORK] = MagicMock()
    network.nodes = {1: 1, 5: 5}

    client = yield from test_client(app)

    resp = yield from client.get('/api/zwave/usercodes/2')

    assert resp.status == 404
    result = yield from resp.json()

    assert result == {'message': 'Node not found'}
