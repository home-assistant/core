"""Test Z-Wave cover devices."""
from unittest.mock import MagicMock

from homeassistant.components.cover import zwave, SUPPORT_OPEN, SUPPORT_CLOSE
from homeassistant.components.zwave import const

from tests.mock.zwave import (
    MockNode, MockValue, MockEntityValues, value_changed)


def test_get_device_detects_none(hass, mock_openzwave):
    """Test device returns none."""
    node = MockNode()
    value = MockValue(data=0, node=node)
    values = MockEntityValues(primary=value, node=node)

    device = zwave.get_device(hass=hass, node=node, values=values,
                              node_config={})
    assert device is None


def test_get_device_detects_rollershutter(hass, mock_openzwave):
    """Test device returns rollershutter."""
    hass.data[zwave.zwave.DATA_NETWORK] = MagicMock()
    node = MockNode()
    value = MockValue(data=0, node=node,
                      command_class=const.COMMAND_CLASS_SWITCH_MULTILEVEL)
    values = MockEntityValues(primary=value, open=None, close=None, node=node)

    device = zwave.get_device(hass=hass, node=node, values=values,
                              node_config={})
    assert isinstance(device, zwave.ZwaveRollershutter)


def test_get_device_detects_garagedoor(hass, mock_openzwave):
    """Test device returns garage door."""
    node = MockNode()
    value = MockValue(data=0, node=node,
                      command_class=const.COMMAND_CLASS_BARRIER_OPERATOR)
    values = MockEntityValues(primary=value, node=node)

    device = zwave.get_device(hass=hass, node=node, values=values,
                              node_config={})
    assert isinstance(device, zwave.ZwaveGarageDoor)
    assert device.device_class == "garage"
    assert device.supported_features == SUPPORT_OPEN | SUPPORT_CLOSE


def test_roller_no_position_workaround(hass, mock_openzwave):
    """Test position changed."""
    hass.data[zwave.zwave.DATA_NETWORK] = MagicMock()
    node = MockNode(manufacturer_id='0047', product_type='5a52')
    value = MockValue(data=45, node=node,
                      command_class=const.COMMAND_CLASS_SWITCH_MULTILEVEL)
    values = MockEntityValues(primary=value, open=None, close=None, node=node)
    device = zwave.get_device(hass=hass, node=node, values=values,
                              node_config={})

    assert device.current_cover_position is None


def test_roller_value_changed(hass, mock_openzwave):
    """Test position changed."""
    hass.data[zwave.zwave.DATA_NETWORK] = MagicMock()
    node = MockNode()
    value = MockValue(data=None, node=node,
                      command_class=const.COMMAND_CLASS_SWITCH_MULTILEVEL)
    values = MockEntityValues(primary=value, open=None, close=None, node=node)
    device = zwave.get_device(hass=hass, node=node, values=values,
                              node_config={})

    assert device.current_cover_position is None
    assert device.is_closed is None

    value.data = 2
    value_changed(value)

    assert device.current_cover_position == 0
    assert device.is_closed

    value.data = 35
    value_changed(value)

    assert device.current_cover_position == 35
    assert not device.is_closed

    value.data = 97
    value_changed(value)

    assert device.current_cover_position == 100
    assert not device.is_closed


def test_roller_commands(hass, mock_openzwave):
    """Test position changed."""
    mock_network = hass.data[zwave.zwave.DATA_NETWORK] = MagicMock()
    node = MockNode()
    value = MockValue(data=50, node=node,
                      command_class=const.COMMAND_CLASS_SWITCH_MULTILEVEL)
    open_value = MockValue(data=False, node=node)
    close_value = MockValue(data=False, node=node)
    values = MockEntityValues(primary=value, open=open_value,
                              close=close_value, node=node)
    device = zwave.get_device(hass=hass, node=node, values=values,
                              node_config={})

    device.set_cover_position(25)
    assert node.set_dimmer.called
    value_id, brightness = node.set_dimmer.mock_calls[0][1]
    assert value_id == value.value_id
    assert brightness == 25

    device.open_cover()
    assert mock_network.manager.pressButton.called
    value_id, = mock_network.manager.pressButton.mock_calls.pop(0)[1]
    assert value_id == open_value.value_id

    device.close_cover()
    assert mock_network.manager.pressButton.called
    value_id, = mock_network.manager.pressButton.mock_calls.pop(0)[1]
    assert value_id == close_value.value_id

    device.stop_cover()
    assert mock_network.manager.releaseButton.called
    value_id, = mock_network.manager.releaseButton.mock_calls.pop(0)[1]
    assert value_id == open_value.value_id


def test_roller_reverse_open_close(hass, mock_openzwave):
    """Test position changed."""
    mock_network = hass.data[zwave.zwave.DATA_NETWORK] = MagicMock()
    node = MockNode()
    value = MockValue(data=50, node=node,
                      command_class=const.COMMAND_CLASS_SWITCH_MULTILEVEL)
    open_value = MockValue(data=False, node=node)
    close_value = MockValue(data=False, node=node)
    values = MockEntityValues(primary=value, open=open_value,
                              close=close_value, node=node)
    device = zwave.get_device(
        hass=hass,
        node=node,
        values=values,
        node_config={zwave.zwave.CONF_INVERT_OPENCLOSE_BUTTONS: True})

    device.open_cover()
    assert mock_network.manager.pressButton.called
    value_id, = mock_network.manager.pressButton.mock_calls.pop(0)[1]
    assert value_id == close_value.value_id

    device.close_cover()
    assert mock_network.manager.pressButton.called
    value_id, = mock_network.manager.pressButton.mock_calls.pop(0)[1]
    assert value_id == open_value.value_id

    device.stop_cover()
    assert mock_network.manager.releaseButton.called
    value_id, = mock_network.manager.releaseButton.mock_calls.pop(0)[1]
    assert value_id == close_value.value_id


def test_garage_value_changed(hass, mock_openzwave):
    """Test position changed."""
    node = MockNode()
    value = MockValue(data=False, node=node,
                      command_class=const.COMMAND_CLASS_BARRIER_OPERATOR)
    values = MockEntityValues(primary=value, node=node)
    device = zwave.get_device(hass=hass, node=node, values=values,
                              node_config={})

    assert device.is_closed

    value.data = True
    value_changed(value)

    assert not device.is_closed


def test_garage_commands(hass, mock_openzwave):
    """Test position changed."""
    node = MockNode()
    value = MockValue(data=False, node=node,
                      command_class=const.COMMAND_CLASS_BARRIER_OPERATOR)
    values = MockEntityValues(primary=value, node=node)
    device = zwave.get_device(hass=hass, node=node, values=values,
                              node_config={})

    assert value.data is False
    device.open_cover()
    assert value.data is True
    device.close_cover()
    assert value.data is False
