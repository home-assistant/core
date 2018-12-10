"""Test Z-Wave locks."""
from unittest.mock import patch, MagicMock

from homeassistant import config_entries
from homeassistant.components.lock import zwave
from homeassistant.components.zwave import const

from tests.mock.zwave import (
    MockNode, MockValue, MockEntityValues, value_changed)


def test_get_device_detects_lock(mock_openzwave):
    """Test get_device returns a Z-Wave lock."""
    node = MockNode()
    values = MockEntityValues(
        primary=MockValue(data=None, node=node),
        access_control=None,
        alarm_type=None,
        alarm_level=None,
    )

    device = zwave.get_device(node=node, values=values, node_config={})
    assert isinstance(device, zwave.ZwaveLock)


def test_lock_turn_on_and_off(mock_openzwave):
    """Test turning on a Z-Wave lock."""
    node = MockNode()
    values = MockEntityValues(
        primary=MockValue(data=None, node=node),
        access_control=None,
        alarm_type=None,
        alarm_level=None,
    )
    device = zwave.get_device(node=node, values=values, node_config={})

    assert not values.primary.data

    device.lock()
    assert values.primary.data

    device.unlock()
    assert not values.primary.data


def test_lock_value_changed(mock_openzwave):
    """Test value changed for Z-Wave lock."""
    node = MockNode()
    values = MockEntityValues(
        primary=MockValue(data=None, node=node),
        access_control=None,
        alarm_type=None,
        alarm_level=None,
    )
    device = zwave.get_device(node=node, values=values, node_config={})

    assert not device.is_locked

    values.primary.data = True
    value_changed(values.primary)

    assert device.is_locked


def test_lock_state_workaround(mock_openzwave):
    """Test value changed for Z-Wave lock using notification state."""
    node = MockNode(manufacturer_id='0090', product_id='0440')
    values = MockEntityValues(
        primary=MockValue(data=True, node=node),
        access_control=MockValue(data=1, node=node),
        alarm_type=None,
        alarm_level=None,
    )
    device = zwave.get_device(node=node, values=values)
    assert device.is_locked
    values.access_control.data = 2
    value_changed(values.access_control)
    assert not device.is_locked


def test_track_message_workaround(mock_openzwave):
    """Test value changed for Z-Wave lock by alarm-clearing workaround."""
    node = MockNode(manufacturer_id='003B', product_id='5044',
                    stats={'lastReceivedMessage': [0] * 6})
    values = MockEntityValues(
        primary=MockValue(data=True, node=node),
        access_control=None,
        alarm_type=None,
        alarm_level=None,
    )

    # Here we simulate an RF lock. The first zwave.get_device will call
    # update properties, simulating the first DoorLock report. We then trigger
    # a change, simulating the openzwave automatic refreshing behavior (which
    # is enabled for at least the lock that needs this workaround)
    node.stats['lastReceivedMessage'][5] = const.COMMAND_CLASS_DOOR_LOCK
    device = zwave.get_device(node=node, values=values)
    value_changed(values.primary)
    assert device.is_locked
    assert device.device_state_attributes[zwave.ATTR_NOTIFICATION] == 'RF Lock'

    # Simulate a keypad unlock. We trigger a value_changed() which simulates
    # the Alarm notification received from the lock. Then, we trigger
    # value_changed() to simulate the automatic refreshing behavior.
    values.access_control = MockValue(data=6, node=node)
    values.alarm_type = MockValue(data=19, node=node)
    values.alarm_level = MockValue(data=3, node=node)
    node.stats['lastReceivedMessage'][5] = const.COMMAND_CLASS_ALARM
    value_changed(values.access_control)
    node.stats['lastReceivedMessage'][5] = const.COMMAND_CLASS_DOOR_LOCK
    values.primary.data = False
    value_changed(values.primary)
    assert not device.is_locked
    assert device.device_state_attributes[zwave.ATTR_LOCK_STATUS] == \
        'Unlocked with Keypad by user 3'

    # Again, simulate an RF lock.
    device.lock()
    node.stats['lastReceivedMessage'][5] = const.COMMAND_CLASS_DOOR_LOCK
    value_changed(values.primary)
    assert device.is_locked
    assert device.device_state_attributes[zwave.ATTR_NOTIFICATION] == 'RF Lock'


def test_v2btze_value_changed(mock_openzwave):
    """Test value changed for v2btze Z-Wave lock."""
    node = MockNode(manufacturer_id='010e', product_id='0002')
    values = MockEntityValues(
        primary=MockValue(data=None, node=node),
        v2btze_advanced=MockValue(data='Advanced', node=node),
        access_control=MockValue(data=19, node=node),
        alarm_type=None,
        alarm_level=None,
    )
    device = zwave.get_device(node=node, values=values, node_config={})
    assert device._v2btze

    assert not device.is_locked

    values.access_control.data = 24
    value_changed(values.primary)

    assert device.is_locked


def test_lock_access_control(mock_openzwave):
    """Test access control for Z-Wave lock."""
    node = MockNode()
    values = MockEntityValues(
        primary=MockValue(data=None, node=node),
        access_control=MockValue(data=11, node=node),
        alarm_type=None,
        alarm_level=None,
    )
    device = zwave.get_device(node=node, values=values, node_config={})

    assert device.device_state_attributes[zwave.ATTR_NOTIFICATION] == \
        'Lock Jammed'


def test_lock_alarm_type(mock_openzwave):
    """Test alarm type for Z-Wave lock."""
    node = MockNode()
    values = MockEntityValues(
        primary=MockValue(data=None, node=node),
        access_control=None,
        alarm_type=MockValue(data=None, node=node),
        alarm_level=None,
    )
    device = zwave.get_device(node=node, values=values, node_config={})

    assert zwave.ATTR_LOCK_STATUS not in device.device_state_attributes

    values.alarm_type.data = 21
    value_changed(values.alarm_type)
    assert device.device_state_attributes[zwave.ATTR_LOCK_STATUS] == \
        'Manually Locked None'

    values.alarm_type.data = 18
    value_changed(values.alarm_type)
    assert device.device_state_attributes[zwave.ATTR_LOCK_STATUS] == \
        'Locked with Keypad by user None'

    values.alarm_type.data = 161
    value_changed(values.alarm_type)
    assert device.device_state_attributes[zwave.ATTR_LOCK_STATUS] == \
        'Tamper Alarm: None'

    values.alarm_type.data = 9
    value_changed(values.alarm_type)
    assert device.device_state_attributes[zwave.ATTR_LOCK_STATUS] == \
        'Deadbolt Jammed'


def test_lock_alarm_level(mock_openzwave):
    """Test alarm level for Z-Wave lock."""
    node = MockNode()
    values = MockEntityValues(
        primary=MockValue(data=None, node=node),
        access_control=None,
        alarm_type=MockValue(data=None, node=node),
        alarm_level=MockValue(data=None, node=node),
    )
    device = zwave.get_device(node=node, values=values, node_config={})

    assert zwave.ATTR_LOCK_STATUS not in device.device_state_attributes

    values.alarm_type.data = 21
    values.alarm_level.data = 1
    value_changed(values.alarm_type)
    value_changed(values.alarm_level)
    assert device.device_state_attributes[zwave.ATTR_LOCK_STATUS] == \
        'Manually Locked by Key Cylinder or Inside thumb turn'

    values.alarm_type.data = 18
    values.alarm_level.data = 'alice'
    value_changed(values.alarm_type)
    value_changed(values.alarm_level)
    assert device.device_state_attributes[zwave.ATTR_LOCK_STATUS] == \
        'Locked with Keypad by user alice'

    values.alarm_type.data = 161
    values.alarm_level.data = 1
    value_changed(values.alarm_type)
    value_changed(values.alarm_level)
    assert device.device_state_attributes[zwave.ATTR_LOCK_STATUS] == \
        'Tamper Alarm: Too many keypresses'


async def setup_ozw(hass, mock_openzwave):
    """Set up the mock ZWave config entry."""
    hass.config.components.add('zwave')
    config_entry = config_entries.ConfigEntry(1, 'zwave', 'Mock Title', {
        'usb_path': 'mock-path',
        'network_key': 'mock-key'
    }, 'test', config_entries.CONN_CLASS_LOCAL_PUSH)
    await hass.config_entries.async_forward_entry_setup(config_entry,
                                                        'lock')
    await hass.async_block_till_done()


async def test_lock_set_usercode_service(hass, mock_openzwave):
    """Test the zwave lock set_usercode service."""
    mock_network = hass.data[zwave.zwave.DATA_NETWORK] = MagicMock()

    node = MockNode(node_id=12)
    value0 = MockValue(data='          ', node=node, index=0)
    value1 = MockValue(data='          ', node=node, index=1)

    node.get_values.return_value = {
        value0.value_id: value0,
        value1.value_id: value1,
    }

    mock_network.nodes = {
        node.node_id: node
    }

    await setup_ozw(hass, mock_openzwave)
    await hass.async_block_till_done()

    await hass.services.async_call(
        zwave.DOMAIN, zwave.SERVICE_SET_USERCODE, {
            const.ATTR_NODE_ID: node.node_id,
            zwave.ATTR_USERCODE: '1234',
            zwave.ATTR_CODE_SLOT: 1,
            })
    await hass.async_block_till_done()

    assert value1.data == '1234'

    mock_network.nodes = {
        node.node_id: node
    }
    await hass.services.async_call(
        zwave.DOMAIN, zwave.SERVICE_SET_USERCODE, {
            const.ATTR_NODE_ID: node.node_id,
            zwave.ATTR_USERCODE: '123',
            zwave.ATTR_CODE_SLOT: 1,
            })
    await hass.async_block_till_done()

    assert value1.data == '1234'


async def test_lock_get_usercode_service(hass, mock_openzwave):
    """Test the zwave lock get_usercode service."""
    mock_network = hass.data[zwave.zwave.DATA_NETWORK] = MagicMock()
    node = MockNode(node_id=12)
    value0 = MockValue(data=None, node=node, index=0)
    value1 = MockValue(data='1234', node=node, index=1)

    node.get_values.return_value = {
        value0.value_id: value0,
        value1.value_id: value1,
    }

    await setup_ozw(hass, mock_openzwave)
    await hass.async_block_till_done()

    with patch.object(zwave, '_LOGGER') as mock_logger:
        mock_network.nodes = {node.node_id: node}
        await hass.services.async_call(
            zwave.DOMAIN, zwave.SERVICE_GET_USERCODE, {
                const.ATTR_NODE_ID: node.node_id,
                zwave.ATTR_CODE_SLOT: 1,
                })
        await hass.async_block_till_done()
        # This service only seems to write to the log
        assert mock_logger.info.called
        assert len(mock_logger.info.mock_calls) == 1
        assert mock_logger.info.mock_calls[0][1][2] == '1234'


async def test_lock_clear_usercode_service(hass, mock_openzwave):
    """Test the zwave lock clear_usercode service."""
    mock_network = hass.data[zwave.zwave.DATA_NETWORK] = MagicMock()
    node = MockNode(node_id=12)
    value0 = MockValue(data=None, node=node, index=0)
    value1 = MockValue(data='123', node=node, index=1)

    node.get_values.return_value = {
        value0.value_id: value0,
        value1.value_id: value1,
    }

    mock_network.nodes = {
        node.node_id: node
    }

    await setup_ozw(hass, mock_openzwave)
    await hass.async_block_till_done()

    await hass.services.async_call(
        zwave.DOMAIN, zwave.SERVICE_CLEAR_USERCODE, {
            const.ATTR_NODE_ID: node.node_id,
            zwave.ATTR_CODE_SLOT: 1
        })
    await hass.async_block_till_done()

    assert value1.data == '\0\0\0'
