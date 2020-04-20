"""Test Z-Wave config panel."""
import json
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.bootstrap import async_setup_component
from homeassistant.components import config
from homeassistant.components.zwave import DATA_NETWORK, const
from homeassistant.const import HTTP_NOT_FOUND

from tests.mock.zwave import MockEntityValues, MockNode, MockValue

VIEW_NAME = "api:config:zwave:device_config"


@pytest.fixture
def client(loop, hass, hass_client):
    """Client to communicate with Z-Wave config views."""
    with patch.object(config, "SECTIONS", ["zwave"]):
        loop.run_until_complete(async_setup_component(hass, "config", {}))

    return loop.run_until_complete(hass_client())


async def test_get_device_config(client):
    """Test getting device config."""

    def mock_read(path):
        """Mock reading data."""
        return {"hello.beer": {"free": "beer"}, "other.entity": {"do": "something"}}

    with patch("homeassistant.components.config._read", mock_read):
        resp = await client.get("/api/config/zwave/device_config/hello.beer")

    assert resp.status == 200
    result = await resp.json()

    assert result == {"free": "beer"}


async def test_update_device_config(client):
    """Test updating device config."""
    orig_data = {
        "hello.beer": {"ignored": True},
        "other.entity": {"polling_intensity": 2},
    }

    def mock_read(path):
        """Mock reading data."""
        return orig_data

    written = []

    def mock_write(path, data):
        """Mock writing data."""
        written.append(data)

    with patch("homeassistant.components.config._read", mock_read), patch(
        "homeassistant.components.config._write", mock_write
    ):
        resp = await client.post(
            "/api/config/zwave/device_config/hello.beer",
            data=json.dumps({"polling_intensity": 2}),
        )

    assert resp.status == 200
    result = await resp.json()
    assert result == {"result": "ok"}

    orig_data["hello.beer"]["polling_intensity"] = 2

    assert written[0] == orig_data


async def test_update_device_config_invalid_key(client):
    """Test updating device config."""
    resp = await client.post(
        "/api/config/zwave/device_config/invalid_entity",
        data=json.dumps({"polling_intensity": 2}),
    )

    assert resp.status == 400


async def test_update_device_config_invalid_data(client):
    """Test updating device config."""
    resp = await client.post(
        "/api/config/zwave/device_config/hello.beer",
        data=json.dumps({"invalid_option": 2}),
    )

    assert resp.status == 400


async def test_update_device_config_invalid_json(client):
    """Test updating device config."""
    resp = await client.post(
        "/api/config/zwave/device_config/hello.beer", data="not json"
    )

    assert resp.status == 400


async def test_get_values(hass, client):
    """Test getting values on node."""
    node = MockNode(node_id=1)
    value = MockValue(
        value_id=123456,
        node=node,
        label="Test Label",
        instance=1,
        index=2,
        poll_intensity=4,
    )
    values = MockEntityValues(primary=value)
    node2 = MockNode(node_id=2)
    value2 = MockValue(value_id=234567, node=node2, label="Test Label 2")
    values2 = MockEntityValues(primary=value2)
    hass.data[const.DATA_ENTITY_VALUES] = [values, values2]

    resp = await client.get("/api/zwave/values/1")

    assert resp.status == 200
    result = await resp.json()

    assert result == {
        "123456": {
            "label": "Test Label",
            "instance": 1,
            "index": 2,
            "poll_intensity": 4,
        }
    }


async def test_get_groups(hass, client):
    """Test getting groupdata on node."""
    network = hass.data[DATA_NETWORK] = MagicMock()
    node = MockNode(node_id=2)
    node.groups.associations = "assoc"
    node.groups.associations_instances = "inst"
    node.groups.label = "the label"
    node.groups.max_associations = "max"
    node.groups = {1: node.groups}
    network.nodes = {2: node}

    resp = await client.get("/api/zwave/groups/2")

    assert resp.status == 200
    result = await resp.json()

    assert result == {
        "1": {
            "association_instances": "inst",
            "associations": "assoc",
            "label": "the label",
            "max_associations": "max",
        }
    }


async def test_get_groups_nogroups(hass, client):
    """Test getting groupdata on node with no groups."""
    network = hass.data[DATA_NETWORK] = MagicMock()
    node = MockNode(node_id=2)

    network.nodes = {2: node}

    resp = await client.get("/api/zwave/groups/2")

    assert resp.status == 200
    result = await resp.json()

    assert result == {}


async def test_get_groups_nonode(hass, client):
    """Test getting groupdata on nonexisting node."""
    network = hass.data[DATA_NETWORK] = MagicMock()
    network.nodes = {1: 1, 5: 5}

    resp = await client.get("/api/zwave/groups/2")

    assert resp.status == HTTP_NOT_FOUND
    result = await resp.json()

    assert result == {"message": "Node not found"}


async def test_get_config(hass, client):
    """Test getting config on node."""
    network = hass.data[DATA_NETWORK] = MagicMock()
    node = MockNode(node_id=2)
    value = MockValue(index=12, command_class=const.COMMAND_CLASS_CONFIGURATION)
    value.label = "label"
    value.help = "help"
    value.type = "type"
    value.data = "data"
    value.data_items = ["item1", "item2"]
    value.max = "max"
    value.min = "min"
    node.values = {12: value}
    network.nodes = {2: node}
    node.get_values.return_value = node.values

    resp = await client.get("/api/zwave/config/2")

    assert resp.status == 200
    result = await resp.json()

    assert result == {
        "12": {
            "data": "data",
            "data_items": ["item1", "item2"],
            "help": "help",
            "label": "label",
            "max": "max",
            "min": "min",
            "type": "type",
        }
    }


async def test_get_config_noconfig_node(hass, client):
    """Test getting config on node without config."""
    network = hass.data[DATA_NETWORK] = MagicMock()
    node = MockNode(node_id=2)

    network.nodes = {2: node}
    node.get_values.return_value = node.values

    resp = await client.get("/api/zwave/config/2")

    assert resp.status == 200
    result = await resp.json()

    assert result == {}


async def test_get_config_nonode(hass, client):
    """Test getting config on nonexisting node."""
    network = hass.data[DATA_NETWORK] = MagicMock()
    network.nodes = {1: 1, 5: 5}

    resp = await client.get("/api/zwave/config/2")

    assert resp.status == HTTP_NOT_FOUND
    result = await resp.json()

    assert result == {"message": "Node not found"}


async def test_get_usercodes_nonode(hass, client):
    """Test getting usercodes on nonexisting node."""
    network = hass.data[DATA_NETWORK] = MagicMock()
    network.nodes = {1: 1, 5: 5}

    resp = await client.get("/api/zwave/usercodes/2")

    assert resp.status == HTTP_NOT_FOUND
    result = await resp.json()

    assert result == {"message": "Node not found"}


async def test_get_usercodes(hass, client):
    """Test getting usercodes on node."""
    network = hass.data[DATA_NETWORK] = MagicMock()
    node = MockNode(node_id=18, command_classes=[const.COMMAND_CLASS_USER_CODE])
    value = MockValue(index=0, command_class=const.COMMAND_CLASS_USER_CODE)
    value.genre = const.GENRE_USER
    value.label = "label"
    value.data = "1234"
    node.values = {0: value}
    network.nodes = {18: node}
    node.get_values.return_value = node.values

    resp = await client.get("/api/zwave/usercodes/18")

    assert resp.status == 200
    result = await resp.json()

    assert result == {"0": {"code": "1234", "label": "label", "length": 4}}


async def test_get_usercode_nousercode_node(hass, client):
    """Test getting usercodes on node without usercodes."""
    network = hass.data[DATA_NETWORK] = MagicMock()
    node = MockNode(node_id=18)

    network.nodes = {18: node}
    node.get_values.return_value = node.values

    resp = await client.get("/api/zwave/usercodes/18")

    assert resp.status == 200
    result = await resp.json()

    assert result == {}


async def test_get_usercodes_no_genreuser(hass, client):
    """Test getting usercodes on node missing genre user."""
    network = hass.data[DATA_NETWORK] = MagicMock()
    node = MockNode(node_id=18, command_classes=[const.COMMAND_CLASS_USER_CODE])
    value = MockValue(index=0, command_class=const.COMMAND_CLASS_USER_CODE)
    value.genre = const.GENRE_SYSTEM
    value.label = "label"
    value.data = "1234"
    node.values = {0: value}
    network.nodes = {18: node}
    node.get_values.return_value = node.values

    resp = await client.get("/api/zwave/usercodes/18")

    assert resp.status == 200
    result = await resp.json()

    assert result == {}


async def test_save_config_no_network(hass, client):
    """Test saving configuration without network data."""
    resp = await client.post("/api/zwave/saveconfig")

    assert resp.status == HTTP_NOT_FOUND
    result = await resp.json()
    assert result == {"message": "No Z-Wave network data found"}


async def test_save_config(hass, client):
    """Test saving configuration."""
    network = hass.data[DATA_NETWORK] = MagicMock()

    resp = await client.post("/api/zwave/saveconfig")

    assert resp.status == 200
    result = await resp.json()
    assert network.write_config.called
    assert result == {"message": "Z-Wave configuration saved to file."}


async def test_get_protection_values(hass, client):
    """Test getting protection values on node."""
    network = hass.data[DATA_NETWORK] = MagicMock()
    node = MockNode(node_id=18, command_classes=[const.COMMAND_CLASS_PROTECTION])
    value = MockValue(
        value_id=123456,
        index=0,
        instance=1,
        command_class=const.COMMAND_CLASS_PROTECTION,
    )
    value.label = "Protection Test"
    value.data_items = [
        "Unprotected",
        "Protection by Sequence",
        "No Operation Possible",
    ]
    value.data = "Unprotected"
    network.nodes = {18: node}
    node.value = value

    node.get_protection_item.return_value = "Unprotected"
    node.get_protection_items.return_value = value.data_items
    node.get_protections.return_value = {value.value_id: "Object"}

    resp = await client.get("/api/zwave/protection/18")

    assert resp.status == 200
    result = await resp.json()
    assert node.get_protections.called
    assert node.get_protection_item.called
    assert node.get_protection_items.called
    assert result == {
        "value_id": "123456",
        "selected": "Unprotected",
        "options": ["Unprotected", "Protection by Sequence", "No Operation Possible"],
    }


async def test_get_protection_values_nonexisting_node(hass, client):
    """Test getting protection values on node with wrong nodeid."""
    network = hass.data[DATA_NETWORK] = MagicMock()
    node = MockNode(node_id=18, command_classes=[const.COMMAND_CLASS_PROTECTION])
    value = MockValue(
        value_id=123456,
        index=0,
        instance=1,
        command_class=const.COMMAND_CLASS_PROTECTION,
    )
    value.label = "Protection Test"
    value.data_items = [
        "Unprotected",
        "Protection by Sequence",
        "No Operation Possible",
    ]
    value.data = "Unprotected"
    network.nodes = {17: node}
    node.value = value

    resp = await client.get("/api/zwave/protection/18")

    assert resp.status == HTTP_NOT_FOUND
    result = await resp.json()
    assert not node.get_protections.called
    assert not node.get_protection_item.called
    assert not node.get_protection_items.called
    assert result == {"message": "Node not found"}


async def test_get_protection_values_without_protectionclass(hass, client):
    """Test getting protection values on node without protectionclass."""
    network = hass.data[DATA_NETWORK] = MagicMock()
    node = MockNode(node_id=18)
    value = MockValue(value_id=123456, index=0, instance=1)
    network.nodes = {18: node}
    node.value = value

    resp = await client.get("/api/zwave/protection/18")

    assert resp.status == 200
    result = await resp.json()
    assert not node.get_protections.called
    assert not node.get_protection_item.called
    assert not node.get_protection_items.called
    assert result == {}


async def test_set_protection_value(hass, client):
    """Test setting protection value on node."""
    network = hass.data[DATA_NETWORK] = MagicMock()
    node = MockNode(node_id=18, command_classes=[const.COMMAND_CLASS_PROTECTION])
    value = MockValue(
        value_id=123456,
        index=0,
        instance=1,
        command_class=const.COMMAND_CLASS_PROTECTION,
    )
    value.label = "Protection Test"
    value.data_items = [
        "Unprotected",
        "Protection by Sequence",
        "No Operation Possible",
    ]
    value.data = "Unprotected"
    network.nodes = {18: node}
    node.value = value

    resp = await client.post(
        "/api/zwave/protection/18",
        data=json.dumps({"value_id": "123456", "selection": "Protection by Sequence"}),
    )

    assert resp.status == 200
    result = await resp.json()
    assert node.set_protection.called
    assert result == {"message": "Protection setting succsessfully set"}


async def test_set_protection_value_failed(hass, client):
    """Test setting protection value failed on node."""
    network = hass.data[DATA_NETWORK] = MagicMock()
    node = MockNode(node_id=18, command_classes=[const.COMMAND_CLASS_PROTECTION])
    value = MockValue(
        value_id=123456,
        index=0,
        instance=1,
        command_class=const.COMMAND_CLASS_PROTECTION,
    )
    value.label = "Protection Test"
    value.data_items = [
        "Unprotected",
        "Protection by Sequence",
        "No Operation Possible",
    ]
    value.data = "Unprotected"
    network.nodes = {18: node}
    node.value = value
    node.set_protection.return_value = False

    resp = await client.post(
        "/api/zwave/protection/18",
        data=json.dumps({"value_id": "123456", "selection": "Protecton by Sequence"}),
    )

    assert resp.status == 202
    result = await resp.json()
    assert node.set_protection.called
    assert result == {"message": "Protection setting did not complete"}


async def test_set_protection_value_nonexisting_node(hass, client):
    """Test setting protection value on nonexisting node."""
    network = hass.data[DATA_NETWORK] = MagicMock()
    node = MockNode(node_id=17, command_classes=[const.COMMAND_CLASS_PROTECTION])
    value = MockValue(
        value_id=123456,
        index=0,
        instance=1,
        command_class=const.COMMAND_CLASS_PROTECTION,
    )
    value.label = "Protection Test"
    value.data_items = [
        "Unprotected",
        "Protection by Sequence",
        "No Operation Possible",
    ]
    value.data = "Unprotected"
    network.nodes = {17: node}
    node.value = value
    node.set_protection.return_value = False

    resp = await client.post(
        "/api/zwave/protection/18",
        data=json.dumps({"value_id": "123456", "selection": "Protecton by Sequence"}),
    )

    assert resp.status == HTTP_NOT_FOUND
    result = await resp.json()
    assert not node.set_protection.called
    assert result == {"message": "Node not found"}


async def test_set_protection_value_missing_class(hass, client):
    """Test setting protection value on node without protectionclass."""
    network = hass.data[DATA_NETWORK] = MagicMock()
    node = MockNode(node_id=17)
    value = MockValue(value_id=123456, index=0, instance=1)
    network.nodes = {17: node}
    node.value = value
    node.set_protection.return_value = False

    resp = await client.post(
        "/api/zwave/protection/17",
        data=json.dumps({"value_id": "123456", "selection": "Protecton by Sequence"}),
    )

    assert resp.status == HTTP_NOT_FOUND
    result = await resp.json()
    assert not node.set_protection.called
    assert result == {"message": "No protection commandclass on this node"}
