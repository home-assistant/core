"""Test Z-Wave switches."""
from unittest.mock import patch

from homeassistant.components.zwave import switch

from tests.mock.zwave import MockEntityValues, MockNode, MockValue, value_changed


def test_get_device_detects_switch(mock_openzwave):
    """Test get_device returns a Z-Wave switch."""
    node = MockNode()
    value = MockValue(data=0, node=node)
    values = MockEntityValues(primary=value)

    device = switch.get_device(node=node, values=values, node_config={})
    assert isinstance(device, switch.ZwaveSwitch)


def test_switch_turn_on_and_off(mock_openzwave):
    """Test turning on a Z-Wave switch."""
    node = MockNode()
    value = MockValue(data=0, node=node)
    values = MockEntityValues(primary=value)
    device = switch.get_device(node=node, values=values, node_config={})

    device.turn_on()

    assert node.set_switch.called
    value_id, state = node.set_switch.mock_calls[0][1]
    assert value_id == value.value_id
    assert state is True
    node.reset_mock()

    device.turn_off()

    assert node.set_switch.called
    value_id, state = node.set_switch.mock_calls[0][1]
    assert value_id == value.value_id
    assert state is False


def test_switch_value_changed(mock_openzwave):
    """Test value changed for Z-Wave switch."""
    node = MockNode()
    value = MockValue(data=False, node=node)
    values = MockEntityValues(primary=value)
    device = switch.get_device(node=node, values=values, node_config={})

    assert not device.is_on

    value.data = True
    value_changed(value)

    assert device.is_on


@patch("time.perf_counter")
def test_switch_refresh_on_update(mock_counter, mock_openzwave):
    """Test value changed for refresh on update Z-Wave switch."""
    mock_counter.return_value = 10
    node = MockNode(manufacturer_id="013c", product_type="0001", product_id="0005")
    value = MockValue(data=False, node=node, instance=1)
    values = MockEntityValues(primary=value)
    device = switch.get_device(node=node, values=values, node_config={})

    assert not device.is_on

    mock_counter.return_value = 15
    value.data = True
    value_changed(value)

    assert device.is_on
    assert not node.request_state.called

    mock_counter.return_value = 45
    value.data = False
    value_changed(value)

    assert not device.is_on
    assert node.request_state.called
