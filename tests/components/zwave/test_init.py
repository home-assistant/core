"""Tests for the Z-Wave init."""
import asyncio
from collections import OrderedDict
from datetime import datetime

import unittest
from unittest.mock import patch, MagicMock

from homeassistant.bootstrap import async_setup_component
from homeassistant.const import ATTR_ENTITY_ID, EVENT_HOMEASSISTANT_START
from homeassistant.components import zwave
from homeassistant.components.binary_sensor.zwave import get_device
from homeassistant.components.zwave import (
    const, CONFIG_SCHEMA, CONF_DEVICE_CONFIG_GLOB, DATA_NETWORK)
from homeassistant.setup import setup_component

import pytest

from tests.common import (
    get_test_home_assistant, async_fire_time_changed)
from tests.mock.zwave import MockNetwork, MockNode, MockValue, MockEntityValues


@asyncio.coroutine
def test_missing_openzwave(hass):
    """Test that missing openzwave lib stops setup."""
    result = yield from async_setup_component(hass, 'zwave', {'zwave': {}})
    assert not result


@asyncio.coroutine
def test_valid_device_config(hass, mock_openzwave):
    """Test valid device config."""
    device_config = {
        'light.kitchen': {
            'ignored': 'true'
        }
    }
    result = yield from async_setup_component(hass, 'zwave', {
        'zwave': {
            'device_config': device_config
        }})

    assert result


@asyncio.coroutine
def test_invalid_device_config(hass, mock_openzwave):
    """Test invalid device config."""
    device_config = {
        'light.kitchen': {
            'some_ignored': 'true'
        }
    }
    result = yield from async_setup_component(hass, 'zwave', {
        'zwave': {
            'device_config': device_config
        }})

    assert not result


def test_config_access_error():
    """Test threading error accessing config values."""
    node = MagicMock()

    def side_effect():
        raise RuntimeError

    node.values.values.side_effect = side_effect
    result = zwave.get_config_value(node, 1)
    assert result is None


@asyncio.coroutine
def test_network_options(hass, mock_openzwave):
    """Test network options."""
    result = yield from async_setup_component(hass, 'zwave', {
        'zwave': {
            'usb_path': 'mock_usb_path',
            'config_path': 'mock_config_path',
        }})

    assert result

    network = hass.data[zwave.DATA_NETWORK]
    assert network.options.device == 'mock_usb_path'
    assert network.options.config_path == 'mock_config_path'


@asyncio.coroutine
def test_auto_heal_midnight(hass, mock_openzwave):
    """Test network auto-heal at midnight."""
    assert (yield from async_setup_component(hass, 'zwave', {
        'zwave': {
            'autoheal': True,
        }}))
    network = hass.data[zwave.DATA_NETWORK]
    assert not network.heal.called

    time = datetime(2017, 5, 6, 0, 0, 0)
    async_fire_time_changed(hass, time)
    yield from hass.async_block_till_done()
    assert network.heal.called
    assert len(network.heal.mock_calls) == 1


@asyncio.coroutine
def test_auto_heal_disabled(hass, mock_openzwave):
    """Test network auto-heal disabled."""
    assert (yield from async_setup_component(hass, 'zwave', {
        'zwave': {
            'autoheal': False,
        }}))
    network = hass.data[zwave.DATA_NETWORK]
    assert not network.heal.called

    time = datetime(2017, 5, 6, 0, 0, 0)
    async_fire_time_changed(hass, time)
    yield from hass.async_block_till_done()
    assert not network.heal.called


@asyncio.coroutine
def test_setup_platform(hass, mock_openzwave):
    """Test invalid device config."""
    mock_device = MagicMock()
    hass.data[DATA_NETWORK] = MagicMock()
    hass.data[zwave.DATA_DEVICES] = {456: mock_device}
    async_add_devices = MagicMock()

    result = yield from zwave.async_setup_platform(
        hass, None, async_add_devices, None)
    assert not result
    assert not async_add_devices.called

    result = yield from zwave.async_setup_platform(
        hass, None, async_add_devices, {const.DISCOVERY_DEVICE: 123})
    assert not result
    assert not async_add_devices.called

    result = yield from zwave.async_setup_platform(
        hass, None, async_add_devices, {const.DISCOVERY_DEVICE: 456})
    assert result
    assert async_add_devices.called
    assert len(async_add_devices.mock_calls) == 1
    assert async_add_devices.mock_calls[0][1][0] == [mock_device]


@asyncio.coroutine
def test_zwave_ready_wait(hass, mock_openzwave):
    """Test that zwave continues after waiting for network ready."""
    # Initialize zwave
    yield from async_setup_component(hass, 'zwave', {'zwave': {}})
    yield from hass.async_block_till_done()

    sleeps = []

    def utcnow():
        return datetime.fromtimestamp(len(sleeps))

    asyncio_sleep = asyncio.sleep

    @asyncio.coroutine
    def sleep(duration, loop):
        if duration > 0:
            sleeps.append(duration)
        yield from asyncio_sleep(0, loop=loop)

    with patch('homeassistant.components.zwave.dt_util.utcnow', new=utcnow):
        with patch('asyncio.sleep', new=sleep):
            with patch.object(zwave, '_LOGGER') as mock_logger:
                hass.data[DATA_NETWORK].state = MockNetwork.STATE_STARTED
                hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
                yield from hass.async_block_till_done()

                assert len(sleeps) == const.NETWORK_READY_WAIT_SECS
                assert mock_logger.warning.called
                assert len(mock_logger.warning.mock_calls) == 1
                assert mock_logger.warning.mock_calls[0][1][1] == \
                    const.NETWORK_READY_WAIT_SECS


@asyncio.coroutine
def test_device_entity(hass, mock_openzwave):
    """Test device entity base class."""
    node = MockNode(node_id='10', name='Mock Node')
    value = MockValue(data=False, node=node, instance=2, object_id='11',
                      label='Sensor',
                      command_class=const.COMMAND_CLASS_SENSOR_BINARY)
    power_value = MockValue(data=50.123456, node=node, precision=3,
                            command_class=const.COMMAND_CLASS_METER)
    values = MockEntityValues(primary=value, power=power_value)
    device = zwave.ZWaveDeviceEntity(values, 'zwave')
    device.hass = hass
    device.value_added()
    device.update_properties()
    yield from hass.async_block_till_done()

    assert not device.should_poll
    assert device.unique_id == "10-11"
    assert device.name == 'Mock Node Sensor'
    assert device.device_state_attributes[zwave.ATTR_POWER] == 50.123


@asyncio.coroutine
def test_node_discovery(hass, mock_openzwave):
    """Test discovery of a node."""
    mock_receivers = []

    def mock_connect(receiver, signal, *args, **kwargs):
        if signal == MockNetwork.SIGNAL_NODE_ADDED:
            mock_receivers.append(receiver)

    with patch('pydispatch.dispatcher.connect', new=mock_connect):
        yield from async_setup_component(hass, 'zwave', {'zwave': {
            'new_entity_ids': True,
            }})

    assert len(mock_receivers) == 1

    node = MockNode(node_id=14)
    hass.async_add_job(mock_receivers[0], node)
    yield from hass.async_block_till_done()

    assert hass.states.get('zwave.mock_node').state is 'unknown'


@asyncio.coroutine
def test_node_ignored(hass, mock_openzwave):
    """Test discovery of a node."""
    mock_receivers = []

    def mock_connect(receiver, signal, *args, **kwargs):
        if signal == MockNetwork.SIGNAL_NODE_ADDED:
            mock_receivers.append(receiver)

    with patch('pydispatch.dispatcher.connect', new=mock_connect):
        yield from async_setup_component(hass, 'zwave', {'zwave': {
            'new_entity_ids': True,
            'device_config': {
                'zwave.mock_node': {
                    'ignored': True,
                    }}}})

    assert len(mock_receivers) == 1

    node = MockNode(node_id=14)
    hass.async_add_job(mock_receivers[0], node)
    yield from hass.async_block_till_done()

    assert hass.states.get('zwave.mock_node') is None


@asyncio.coroutine
def test_value_discovery(hass, mock_openzwave):
    """Test discovery of a node."""
    mock_receivers = []

    def mock_connect(receiver, signal, *args, **kwargs):
        if signal == MockNetwork.SIGNAL_VALUE_ADDED:
            mock_receivers.append(receiver)

    with patch('pydispatch.dispatcher.connect', new=mock_connect):
        yield from async_setup_component(hass, 'zwave', {'zwave': {
            'new_entity_ids': True,
            }})

    assert len(mock_receivers) == 1

    node = MockNode(node_id=11, generic=const.GENERIC_TYPE_SENSOR_BINARY)
    value = MockValue(data=False, node=node, index=12, instance=13,
                      command_class=const.COMMAND_CLASS_SENSOR_BINARY,
                      type=const.TYPE_BOOL, genre=const.GENRE_USER)
    hass.async_add_job(mock_receivers[0], node, value)
    yield from hass.async_block_till_done()

    assert hass.states.get(
        'binary_sensor.mock_node_mock_value').state is 'off'


@asyncio.coroutine
def test_value_discovery_existing_entity(hass, mock_openzwave):
    """Test discovery of a node."""
    mock_receivers = []

    def mock_connect(receiver, signal, *args, **kwargs):
        if signal == MockNetwork.SIGNAL_VALUE_ADDED:
            mock_receivers.append(receiver)

    with patch('pydispatch.dispatcher.connect', new=mock_connect):
        yield from async_setup_component(hass, 'zwave', {'zwave': {
            'new_entity_ids': True,
            }})

    assert len(mock_receivers) == 1

    node = MockNode(node_id=11, generic=const.GENERIC_TYPE_THERMOSTAT)
    setpoint = MockValue(
        data=22.0, node=node, index=12, instance=13,
        command_class=const.COMMAND_CLASS_THERMOSTAT_SETPOINT,
        genre=const.GENRE_USER, units='C')
    hass.async_add_job(mock_receivers[0], node, setpoint)
    yield from hass.async_block_till_done()

    assert hass.states.get('climate.mock_node_mock_value').attributes[
        'temperature'] == 22.0
    assert hass.states.get('climate.mock_node_mock_value').attributes[
        'current_temperature'] is None

    def mock_update(self):
        self.hass.add_job(self.async_update_ha_state)

    with patch.object(zwave.node_entity.ZWaveBaseEntity,
                      'maybe_schedule_update', new=mock_update):
        temperature = MockValue(
            data=23.5, node=node, index=1, instance=13,
            command_class=const.COMMAND_CLASS_SENSOR_MULTILEVEL,
            genre=const.GENRE_USER, units='C')
        hass.async_add_job(mock_receivers[0], node, temperature)
        yield from hass.async_block_till_done()

    assert hass.states.get('climate.mock_node_mock_value').attributes[
        'temperature'] == 22.0
    assert hass.states.get('climate.mock_node_mock_value').attributes[
        'current_temperature'] == 23.5


@asyncio.coroutine
def test_power_schemes(hass, mock_openzwave):
    """Test power attribute."""
    mock_receivers = []

    def mock_connect(receiver, signal, *args, **kwargs):
        if signal == MockNetwork.SIGNAL_VALUE_ADDED:
            mock_receivers.append(receiver)

    with patch('pydispatch.dispatcher.connect', new=mock_connect):
        yield from async_setup_component(hass, 'zwave', {'zwave': {
            'new_entity_ids': True,
            }})

    assert len(mock_receivers) == 1

    node = MockNode(node_id=11, generic=const.GENERIC_TYPE_SWITCH_BINARY)
    switch = MockValue(
        data=True, node=node, index=12, instance=13,
        command_class=const.COMMAND_CLASS_SWITCH_BINARY,
        genre=const.GENRE_USER, type=const.TYPE_BOOL)
    hass.async_add_job(mock_receivers[0], node, switch)

    yield from hass.async_block_till_done()

    assert hass.states.get('switch.mock_node_mock_value').state == 'on'
    assert 'power_consumption' not in hass.states.get(
        'switch.mock_node_mock_value').attributes

    def mock_update(self):
        self.hass.add_job(self.async_update_ha_state)

    with patch.object(zwave.node_entity.ZWaveBaseEntity,
                      'maybe_schedule_update', new=mock_update):
        power = MockValue(
            data=23.5, node=node, index=const.INDEX_SENSOR_MULTILEVEL_POWER,
            instance=13, command_class=const.COMMAND_CLASS_SENSOR_MULTILEVEL)
        hass.async_add_job(mock_receivers[0], node, power)
        yield from hass.async_block_till_done()

    assert hass.states.get('switch.mock_node_mock_value').attributes[
        'power_consumption'] == 23.5


@asyncio.coroutine
def test_network_ready(hass, mock_openzwave):
    """Test Node network ready event."""
    mock_receivers = []

    def mock_connect(receiver, signal, *args, **kwargs):
        if signal == MockNetwork.SIGNAL_ALL_NODES_QUERIED:
            mock_receivers.append(receiver)

    with patch('pydispatch.dispatcher.connect', new=mock_connect):
        yield from async_setup_component(hass, 'zwave', {'zwave': {
            'new_entity_ids': True,
            }})

    assert len(mock_receivers) == 1

    events = []

    def listener(event):
        events.append(event)

    hass.bus.async_listen(const.EVENT_NETWORK_COMPLETE, listener)

    hass.async_add_job(mock_receivers[0])
    yield from hass.async_block_till_done()

    assert len(events) == 1


@asyncio.coroutine
def test_network_complete(hass, mock_openzwave):
    """Test Node network complete event."""
    mock_receivers = []

    def mock_connect(receiver, signal, *args, **kwargs):
        if signal == MockNetwork.SIGNAL_AWAKE_NODES_QUERIED:
            mock_receivers.append(receiver)

    with patch('pydispatch.dispatcher.connect', new=mock_connect):
        yield from async_setup_component(hass, 'zwave', {'zwave': {
            'new_entity_ids': True,
            }})

    assert len(mock_receivers) == 1

    events = []

    def listener(event):
        events.append(event)

    hass.bus.async_listen(const.EVENT_NETWORK_READY, listener)

    hass.async_add_job(mock_receivers[0])
    yield from hass.async_block_till_done()

    assert len(events) == 1


class TestZWaveDeviceEntityValues(unittest.TestCase):
    """Tests for the ZWaveDeviceEntityValues helper."""

    @pytest.fixture(autouse=True)
    def set_mock_openzwave(self, mock_openzwave):
        """Use the mock_openzwave fixture for this class."""
        self.mock_openzwave = mock_openzwave

    def setUp(self):
        """Initialize values for this testcase class."""
        self.hass = get_test_home_assistant()
        self.hass.start()

        setup_component(self.hass, 'zwave', {'zwave': {
            'new_entity_ids': True,
            }})
        self.hass.block_till_done()

        self.node = MockNode()
        self.mock_schema = {
            const.DISC_COMPONENT: 'mock_component',
            const.DISC_VALUES: {
                const.DISC_PRIMARY: {
                    const.DISC_COMMAND_CLASS: ['mock_primary_class'],
                },
                'secondary': {
                    const.DISC_COMMAND_CLASS: ['mock_secondary_class'],
                },
                'optional': {
                    const.DISC_COMMAND_CLASS: ['mock_optional_class'],
                    const.DISC_OPTIONAL: True,
                }}}
        self.primary = MockValue(
            command_class='mock_primary_class', node=self.node)
        self.secondary = MockValue(
            command_class='mock_secondary_class', node=self.node)
        self.duplicate_secondary = MockValue(
            command_class='mock_secondary_class', node=self.node)
        self.optional = MockValue(
            command_class='mock_optional_class', node=self.node)
        self.no_match_value = MockValue(
            command_class='mock_bad_class', node=self.node)

        self.entity_id = 'mock_component.mock_node_mock_value'
        self.zwave_config = {'zwave': {
            'new_entity_ids': True,
        }}
        self.device_config = {self.entity_id: {}}

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        self.hass.stop()

    @patch.object(zwave, 'get_platform')
    @patch.object(zwave, 'discovery')
    def test_entity_discovery(self, discovery, get_platform):
        """Test the creation of a new entity."""
        mock_platform = MagicMock()
        get_platform.return_value = mock_platform
        mock_device = MagicMock()
        mock_device.name = 'test_device'
        mock_platform.get_device.return_value = mock_device
        values = zwave.ZWaveDeviceEntityValues(
            hass=self.hass,
            schema=self.mock_schema,
            primary_value=self.primary,
            zwave_config=self.zwave_config,
            device_config=self.device_config,
        )

        assert values.primary is self.primary
        assert len(list(values)) == 3
        self.assertEqual(sorted(list(values),
                                key=lambda a: id(a)),
                         sorted([self.primary, None, None],
                                key=lambda a: id(a)))
        assert not discovery.async_load_platform.called

        values.check_value(self.secondary)
        self.hass.block_till_done()

        assert values.secondary is self.secondary
        assert len(list(values)) == 3
        self.assertEqual(sorted(list(values),
                                key=lambda a: id(a)),
                         sorted([self.primary, self.secondary, None],
                                key=lambda a: id(a)))

        assert discovery.async_load_platform.called
        # Second call is to async yield from
        assert len(discovery.async_load_platform.mock_calls) == 2
        args = discovery.async_load_platform.mock_calls[0][1]
        assert args[0] == self.hass
        assert args[1] == 'mock_component'
        assert args[2] == 'zwave'
        assert args[3] == {const.DISCOVERY_DEVICE: id(values)}
        assert args[4] == self.zwave_config

        discovery.async_load_platform.reset_mock()
        values.check_value(self.optional)
        values.check_value(self.duplicate_secondary)
        values.check_value(self.no_match_value)
        self.hass.block_till_done()

        assert values.optional is self.optional
        assert len(list(values)) == 3
        self.assertEqual(sorted(list(values),
                                key=lambda a: id(a)),
                         sorted([self.primary, self.secondary, self.optional],
                                key=lambda a: id(a)))
        assert not discovery.async_load_platform.called

        assert values._entity.value_added.called
        assert len(values._entity.value_added.mock_calls) == 1
        assert values._entity.value_changed.called
        assert len(values._entity.value_changed.mock_calls) == 1

    @patch.object(zwave, 'get_platform')
    @patch.object(zwave, 'discovery')
    def test_entity_existing_values(self, discovery, get_platform):
        """Test the loading of already discovered values."""
        mock_platform = MagicMock()
        get_platform.return_value = mock_platform
        mock_device = MagicMock()
        mock_device.name = 'test_device'
        mock_platform.get_device.return_value = mock_device
        self.node.values = {
            self.primary.value_id: self.primary,
            self.secondary.value_id: self.secondary,
            self.optional.value_id: self.optional,
            self.no_match_value.value_id: self.no_match_value,
        }

        values = zwave.ZWaveDeviceEntityValues(
            hass=self.hass,
            schema=self.mock_schema,
            primary_value=self.primary,
            zwave_config=self.zwave_config,
            device_config=self.device_config,
        )
        self.hass.block_till_done()

        assert values.primary is self.primary
        assert values.secondary is self.secondary
        assert values.optional is self.optional
        assert len(list(values)) == 3
        self.assertEqual(sorted(list(values),
                                key=lambda a: id(a)),
                         sorted([self.primary, self.secondary, self.optional],
                                key=lambda a: id(a)))

        assert discovery.async_load_platform.called
        # Second call is to async yield from
        assert len(discovery.async_load_platform.mock_calls) == 2
        args = discovery.async_load_platform.mock_calls[0][1]
        assert args[0] == self.hass
        assert args[1] == 'mock_component'
        assert args[2] == 'zwave'
        assert args[3] == {const.DISCOVERY_DEVICE: id(values)}
        assert args[4] == self.zwave_config
        assert not self.primary.enable_poll.called

    @patch.object(zwave, 'get_platform')
    @patch.object(zwave, 'discovery')
    def test_node_schema_mismatch(self, discovery, get_platform):
        """Test node schema mismatch."""
        self.node.generic = 'no_match'
        self.node.values = {
            self.primary.value_id: self.primary,
            self.secondary.value_id: self.secondary,
        }
        self.mock_schema[const.DISC_GENERIC_DEVICE_CLASS] = ['generic_match']
        values = zwave.ZWaveDeviceEntityValues(
            hass=self.hass,
            schema=self.mock_schema,
            primary_value=self.primary,
            zwave_config=self.zwave_config,
            device_config=self.device_config,
        )
        values._check_entity_ready()
        self.hass.block_till_done()

        assert not discovery.async_load_platform.called

    @patch.object(zwave, 'get_platform')
    @patch.object(zwave, 'discovery')
    def test_entity_workaround_component(self, discovery, get_platform):
        """Test ignore workaround."""
        mock_platform = MagicMock()
        get_platform.return_value = mock_platform
        mock_device = MagicMock()
        mock_device.name = 'test_device'
        mock_platform.get_device.return_value = mock_device
        self.node.manufacturer_id = '010f'
        self.node.product_type = '0b00'
        self.primary.command_class = const.COMMAND_CLASS_SENSOR_ALARM
        self.entity_id = 'binary_sensor.mock_node_mock_value'
        self.device_config = {self.entity_id: {}}

        self.mock_schema = {
            const.DISC_COMPONENT: 'mock_component',
            const.DISC_VALUES: {
                const.DISC_PRIMARY: {
                    const.DISC_COMMAND_CLASS: [
                        const.COMMAND_CLASS_SWITCH_BINARY],
                }}}

        values = zwave.ZWaveDeviceEntityValues(
            hass=self.hass,
            schema=self.mock_schema,
            primary_value=self.primary,
            zwave_config=self.zwave_config,
            device_config=self.device_config,
        )
        values._check_entity_ready()
        self.hass.block_till_done()

        assert discovery.async_load_platform.called
        # Second call is to async yield from
        assert len(discovery.async_load_platform.mock_calls) == 2
        args = discovery.async_load_platform.mock_calls[0][1]
        assert args[1] == 'binary_sensor'

    @patch.object(zwave, 'get_platform')
    @patch.object(zwave, 'discovery')
    def test_entity_workaround_ignore(self, discovery, get_platform):
        """Test ignore workaround."""
        self.node.manufacturer_id = '010f'
        self.node.product_type = '0301'
        self.primary.command_class = const.COMMAND_CLASS_SWITCH_BINARY

        self.mock_schema = {
            const.DISC_COMPONENT: 'mock_component',
            const.DISC_VALUES: {
                const.DISC_PRIMARY: {
                    const.DISC_COMMAND_CLASS: [
                        const.COMMAND_CLASS_SWITCH_BINARY],
                }}}

        values = zwave.ZWaveDeviceEntityValues(
            hass=self.hass,
            schema=self.mock_schema,
            primary_value=self.primary,
            zwave_config=self.zwave_config,
            device_config=self.device_config,
        )
        values._check_entity_ready()
        self.hass.block_till_done()

        assert not discovery.async_load_platform.called

    @patch.object(zwave, 'get_platform')
    @patch.object(zwave, 'discovery')
    def test_entity_config_ignore(self, discovery, get_platform):
        """Test ignore config."""
        self.node.values = {
            self.primary.value_id: self.primary,
            self.secondary.value_id: self.secondary,
        }
        self.device_config = {self.entity_id: {
            zwave.CONF_IGNORED: True
        }}
        values = zwave.ZWaveDeviceEntityValues(
            hass=self.hass,
            schema=self.mock_schema,
            primary_value=self.primary,
            zwave_config=self.zwave_config,
            device_config=self.device_config,
        )
        values._check_entity_ready()
        self.hass.block_till_done()

        assert not discovery.async_load_platform.called

    @patch.object(zwave, 'get_platform')
    @patch.object(zwave, 'discovery')
    def test_entity_platform_ignore(self, discovery, get_platform):
        """Test platform ignore device."""
        self.node.values = {
            self.primary.value_id: self.primary,
            self.secondary.value_id: self.secondary,
        }
        platform = MagicMock()
        get_platform.return_value = platform
        platform.get_device.return_value = None
        zwave.ZWaveDeviceEntityValues(
            hass=self.hass,
            schema=self.mock_schema,
            primary_value=self.primary,
            zwave_config=self.zwave_config,
            device_config=self.device_config,
        )
        self.hass.block_till_done()

        assert not discovery.async_load_platform.called

    @patch.object(zwave, 'get_platform')
    @patch.object(zwave, 'discovery')
    def test_config_polling_intensity(self, discovery, get_platform):
        """Test polling intensity."""
        mock_platform = MagicMock()
        get_platform.return_value = mock_platform
        mock_device = MagicMock()
        mock_device.name = 'test_device'
        mock_platform.get_device.return_value = mock_device
        self.node.values = {
            self.primary.value_id: self.primary,
            self.secondary.value_id: self.secondary,
        }
        self.device_config = {self.entity_id: {
            zwave.CONF_POLLING_INTENSITY: 123,
        }}
        values = zwave.ZWaveDeviceEntityValues(
            hass=self.hass,
            schema=self.mock_schema,
            primary_value=self.primary,
            zwave_config=self.zwave_config,
            device_config=self.device_config,
        )
        values._check_entity_ready()
        self.hass.block_till_done()

        assert discovery.async_load_platform.called
        assert self.primary.enable_poll.called
        assert len(self.primary.enable_poll.mock_calls) == 1
        assert self.primary.enable_poll.mock_calls[0][1][0] == 123


class TestZwave(unittest.TestCase):
    """Test zwave init."""

    def test_device_config_glob_is_ordered(self):
        """Test that device_config_glob preserves order."""
        conf = CONFIG_SCHEMA(
            {'zwave': {CONF_DEVICE_CONFIG_GLOB: OrderedDict()}})
        self.assertIsInstance(
            conf['zwave'][CONF_DEVICE_CONFIG_GLOB], OrderedDict)


class TestZWaveServices(unittest.TestCase):
    """Tests for zwave services."""

    @pytest.fixture(autouse=True)
    def set_mock_openzwave(self, mock_openzwave):
        """Use the mock_openzwave fixture for this class."""
        self.mock_openzwave = mock_openzwave

    def setUp(self):
        """Initialize values for this testcase class."""
        self.hass = get_test_home_assistant()
        self.hass.start()

        # Initialize zwave
        setup_component(self.hass, 'zwave', {'zwave': {
            'new_entity_ids': True,
            }})
        self.hass.block_till_done()
        self.zwave_network = self.hass.data[DATA_NETWORK]
        self.zwave_network.state = MockNetwork.STATE_READY
        self.hass.bus.fire(EVENT_HOMEASSISTANT_START)
        self.hass.block_till_done()

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        self.hass.services.call('zwave', 'stop_network', {})
        self.hass.block_till_done()
        self.hass.stop()

    def test_add_node(self):
        """Test zwave add_node service."""
        self.hass.services.call('zwave', 'add_node', {})
        self.hass.block_till_done()

        assert self.zwave_network.controller.add_node.called
        assert len(self.zwave_network.controller
                   .add_node.mock_calls) == 1
        assert len(self.zwave_network.controller
                   .add_node.mock_calls[0][1]) == 0

    def test_add_node_secure(self):
        """Test zwave add_node_secure service."""
        self.hass.services.call('zwave', 'add_node_secure', {})
        self.hass.block_till_done()

        assert self.zwave_network.controller.add_node.called
        assert len(self.zwave_network.controller.add_node.mock_calls) == 1
        assert (self.zwave_network.controller
                .add_node.mock_calls[0][1][0] is True)

    def test_remove_node(self):
        """Test zwave remove_node service."""
        self.hass.services.call('zwave', 'remove_node', {})
        self.hass.block_till_done()

        assert self.zwave_network.controller.remove_node.called
        assert len(self.zwave_network.controller.remove_node.mock_calls) == 1

    def test_cancel_command(self):
        """Test zwave cancel_command service."""
        self.hass.services.call('zwave', 'cancel_command', {})
        self.hass.block_till_done()

        assert self.zwave_network.controller.cancel_command.called
        assert len(self.zwave_network.controller
                   .cancel_command.mock_calls) == 1

    def test_heal_network(self):
        """Test zwave heal_network service."""
        self.hass.services.call('zwave', 'heal_network', {})
        self.hass.block_till_done()

        assert self.zwave_network.heal.called
        assert len(self.zwave_network.heal.mock_calls) == 1

    def test_soft_reset(self):
        """Test zwave soft_reset service."""
        self.hass.services.call('zwave', 'soft_reset', {})
        self.hass.block_till_done()

        assert self.zwave_network.controller.soft_reset.called
        assert len(self.zwave_network.controller.soft_reset.mock_calls) == 1

    def test_test_network(self):
        """Test zwave test_network service."""
        self.hass.services.call('zwave', 'test_network', {})
        self.hass.block_till_done()

        assert self.zwave_network.test.called
        assert len(self.zwave_network.test.mock_calls) == 1

    def test_stop_network(self):
        """Test zwave stop_network service."""
        with patch.object(self.hass.bus, 'fire') as mock_fire:
            self.hass.services.call('zwave', 'stop_network', {})
            self.hass.block_till_done()

            assert self.zwave_network.stop.called
            assert len(self.zwave_network.stop.mock_calls) == 1
            assert mock_fire.called
            assert len(mock_fire.mock_calls) == 2
            assert mock_fire.mock_calls[0][1][0] == const.EVENT_NETWORK_STOP

    def test_rename_node(self):
        """Test zwave rename_node service."""
        self.zwave_network.nodes = {11: MagicMock()}
        self.hass.services.call('zwave', 'rename_node', {
            const.ATTR_NODE_ID: 11,
            const.ATTR_NAME: 'test_name',
        })
        self.hass.block_till_done()

        assert self.zwave_network.nodes[11].name == 'test_name'

    def test_rename_value(self):
        """Test zwave rename_value service."""
        node = MockNode(node_id=14)
        value = MockValue(index=12, value_id=123456, label="Old Label")
        node.values = {123456: value}
        self.zwave_network.nodes = {11: node}

        assert value.label == "Old Label"
        self.hass.services.call('zwave', 'rename_value', {
            const.ATTR_NODE_ID: 11,
            const.ATTR_VALUE_ID: 123456,
            const.ATTR_NAME: "New Label",
        })
        self.hass.block_till_done()

        assert value.label == "New Label"

    def test_set_poll_intensity_enable(self):
        """Test zwave set_poll_intensity service, successful set."""
        node = MockNode(node_id=14)
        value = MockValue(index=12, value_id=123456, poll_intensity=0)
        node.values = {123456: value}
        self.zwave_network.nodes = {11: node}

        assert value.poll_intensity == 0
        self.hass.services.call('zwave', 'set_poll_intensity', {
            const.ATTR_NODE_ID: 11,
            const.ATTR_VALUE_ID: 123456,
            const.ATTR_POLL_INTENSITY: 4,
        })
        self.hass.block_till_done()

        enable_poll = value.enable_poll
        assert value.enable_poll.called
        assert len(enable_poll.mock_calls) == 2
        assert enable_poll.mock_calls[0][1][0] == 4

    def test_set_poll_intensity_enable_failed(self):
        """Test zwave set_poll_intensity service, failed set."""
        node = MockNode(node_id=14)
        value = MockValue(index=12, value_id=123456, poll_intensity=0)
        value.enable_poll.return_value = False
        node.values = {123456: value}
        self.zwave_network.nodes = {11: node}

        assert value.poll_intensity == 0
        self.hass.services.call('zwave', 'set_poll_intensity', {
            const.ATTR_NODE_ID: 11,
            const.ATTR_VALUE_ID: 123456,
            const.ATTR_POLL_INTENSITY: 4,
        })
        self.hass.block_till_done()

        enable_poll = value.enable_poll
        assert value.enable_poll.called
        assert len(enable_poll.mock_calls) == 1

    def test_set_poll_intensity_disable(self):
        """Test zwave set_poll_intensity service, successful disable."""
        node = MockNode(node_id=14)
        value = MockValue(index=12, value_id=123456, poll_intensity=4)
        node.values = {123456: value}
        self.zwave_network.nodes = {11: node}

        assert value.poll_intensity == 4
        self.hass.services.call('zwave', 'set_poll_intensity', {
            const.ATTR_NODE_ID: 11,
            const.ATTR_VALUE_ID: 123456,
            const.ATTR_POLL_INTENSITY: 0,
        })
        self.hass.block_till_done()

        disable_poll = value.disable_poll
        assert value.disable_poll.called
        assert len(disable_poll.mock_calls) == 2

    def test_set_poll_intensity_disable_failed(self):
        """Test zwave set_poll_intensity service, failed disable."""
        node = MockNode(node_id=14)
        value = MockValue(index=12, value_id=123456, poll_intensity=4)
        value.disable_poll.return_value = False
        node.values = {123456: value}
        self.zwave_network.nodes = {11: node}

        assert value.poll_intensity == 4
        self.hass.services.call('zwave', 'set_poll_intensity', {
            const.ATTR_NODE_ID: 11,
            const.ATTR_VALUE_ID: 123456,
            const.ATTR_POLL_INTENSITY: 0,
        })
        self.hass.block_till_done()

        disable_poll = value.disable_poll
        assert value.disable_poll.called
        assert len(disable_poll.mock_calls) == 1

    def test_remove_failed_node(self):
        """Test zwave remove_failed_node service."""
        self.hass.services.call('zwave', 'remove_failed_node', {
            const.ATTR_NODE_ID: 12,
        })
        self.hass.block_till_done()

        remove_failed_node = self.zwave_network.controller.remove_failed_node
        assert remove_failed_node.called
        assert len(remove_failed_node.mock_calls) == 1
        assert remove_failed_node.mock_calls[0][1][0] == 12

    def test_replace_failed_node(self):
        """Test zwave replace_failed_node service."""
        self.hass.services.call('zwave', 'replace_failed_node', {
            const.ATTR_NODE_ID: 13,
        })
        self.hass.block_till_done()

        replace_failed_node = self.zwave_network.controller.replace_failed_node
        assert replace_failed_node.called
        assert len(replace_failed_node.mock_calls) == 1
        assert replace_failed_node.mock_calls[0][1][0] == 13

    def test_set_config_parameter(self):
        """Test zwave set_config_parameter service."""
        value = MockValue(
            index=12,
            command_class=const.COMMAND_CLASS_CONFIGURATION,
            type=const.TYPE_BYTE,
        )
        value_list = MockValue(
            index=13,
            command_class=const.COMMAND_CLASS_CONFIGURATION,
            type=const.TYPE_LIST,
            data_items=['item1', 'item2', 'item3'],
        )
        node = MockNode(node_id=14)
        node.get_values.return_value = {12: value, 13: value_list}
        self.zwave_network.nodes = {14: node}

        self.hass.services.call('zwave', 'set_config_parameter', {
            const.ATTR_NODE_ID: 14,
            const.ATTR_CONFIG_PARAMETER: 13,
            const.ATTR_CONFIG_VALUE: 'item3',
        })
        self.hass.block_till_done()

        assert value_list.data == 'item3'

        self.hass.services.call('zwave', 'set_config_parameter', {
            const.ATTR_NODE_ID: 14,
            const.ATTR_CONFIG_PARAMETER: 12,
            const.ATTR_CONFIG_VALUE: 7,
        })
        self.hass.block_till_done()

        assert value.data == 7

        self.hass.services.call('zwave', 'set_config_parameter', {
            const.ATTR_NODE_ID: 14,
            const.ATTR_CONFIG_PARAMETER: 19,
            const.ATTR_CONFIG_VALUE: 0x01020304,
            const.ATTR_CONFIG_SIZE: 4
        })
        self.hass.block_till_done()

        assert node.set_config_param.called
        assert len(node.set_config_param.mock_calls) == 1
        assert node.set_config_param.mock_calls[0][1][0] == 19
        assert node.set_config_param.mock_calls[0][1][1] == 0x01020304
        assert node.set_config_param.mock_calls[0][1][2] == 4
        node.set_config_param.reset_mock()

    def test_print_config_parameter(self):
        """Test zwave print_config_parameter service."""
        value1 = MockValue(
            index=12,
            command_class=const.COMMAND_CLASS_CONFIGURATION,
            data=1234,
        )
        value2 = MockValue(
            index=13,
            command_class=const.COMMAND_CLASS_CONFIGURATION,
            data=2345,
        )
        node = MockNode(node_id=14)
        node.values = {12: value1, 13: value2}
        self.zwave_network.nodes = {14: node}

        with patch.object(zwave, '_LOGGER') as mock_logger:
            self.hass.services.call('zwave', 'print_config_parameter', {
                const.ATTR_NODE_ID: 14,
                const.ATTR_CONFIG_PARAMETER: 13,
            })
            self.hass.block_till_done()

            assert mock_logger.info.called
            assert len(mock_logger.info.mock_calls) == 1
            assert mock_logger.info.mock_calls[0][1][1] == 13
            assert mock_logger.info.mock_calls[0][1][2] == 14
            assert mock_logger.info.mock_calls[0][1][3] == 2345

    def test_print_node(self):
        """Test zwave print_config_parameter service."""
        node1 = MockNode(node_id=14)
        node2 = MockNode(node_id=15)
        self.zwave_network.nodes = {14: node1, 15: node2}

        with patch.object(zwave, 'pprint') as mock_pprint:
            self.hass.services.call('zwave', 'print_node', {
                const.ATTR_NODE_ID: 15,
            })
            self.hass.block_till_done()

            assert mock_pprint.called
            assert len(mock_pprint.mock_calls) == 1
            assert mock_pprint.mock_calls[0][1][0]['node_id'] == 15

    def test_set_wakeup(self):
        """Test zwave set_wakeup service."""
        value = MockValue(
            index=12,
            command_class=const.COMMAND_CLASS_WAKE_UP,
        )
        node = MockNode(node_id=14)
        node.values = {12: value}
        node.get_values.return_value = node.values
        self.zwave_network.nodes = {14: node}

        self.hass.services.call('zwave', 'set_wakeup', {
            const.ATTR_NODE_ID: 14,
            const.ATTR_CONFIG_VALUE: 15,
        })
        self.hass.block_till_done()

        assert value.data == 15

        node.can_wake_up_value = False
        self.hass.services.call('zwave', 'set_wakeup', {
            const.ATTR_NODE_ID: 14,
            const.ATTR_CONFIG_VALUE: 20,
        })
        self.hass.block_till_done()

        assert value.data == 15

    def test_reset_node_meters(self):
        """Test zwave reset_node_meters service."""
        value = MockValue(
            instance=1,
            index=8,
            data=99.5,
            command_class=const.COMMAND_CLASS_METER,
        )
        reset_value = MockValue(
            instance=1,
            index=33,
            command_class=const.COMMAND_CLASS_METER,
        )
        node = MockNode(node_id=14)
        node.values = {8: value, 33: reset_value}
        node.get_values.return_value = node.values
        self.zwave_network.nodes = {14: node}

        self.hass.services.call('zwave', 'reset_node_meters', {
            const.ATTR_NODE_ID: 14,
            const.ATTR_INSTANCE: 2,
        })
        self.hass.block_till_done()

        assert not self.zwave_network.manager.pressButton.called
        assert not self.zwave_network.manager.releaseButton.called

        self.hass.services.call('zwave', 'reset_node_meters', {
            const.ATTR_NODE_ID: 14,
        })
        self.hass.block_till_done()

        assert self.zwave_network.manager.pressButton.called
        value_id, = self.zwave_network.manager.pressButton.mock_calls.pop(0)[1]
        assert value_id == reset_value.value_id
        assert self.zwave_network.manager.releaseButton.called
        value_id, = (
            self.zwave_network.manager.releaseButton.mock_calls.pop(0)[1])
        assert value_id == reset_value.value_id

    def test_add_association(self):
        """Test zwave change_association service."""
        ZWaveGroup = self.mock_openzwave.group.ZWaveGroup
        group = MagicMock()
        ZWaveGroup.return_value = group

        value = MockValue(
            index=12,
            command_class=const.COMMAND_CLASS_WAKE_UP,
        )
        node = MockNode(node_id=14)
        node.values = {12: value}
        node.get_values.return_value = node.values
        self.zwave_network.nodes = {14: node}

        self.hass.services.call('zwave', 'change_association', {
            const.ATTR_ASSOCIATION: 'add',
            const.ATTR_NODE_ID: 14,
            const.ATTR_TARGET_NODE_ID: 24,
            const.ATTR_GROUP: 3,
            const.ATTR_INSTANCE: 5,
        })
        self.hass.block_till_done()

        assert ZWaveGroup.called
        assert len(ZWaveGroup.mock_calls) == 2
        assert ZWaveGroup.mock_calls[0][1][0] == 3
        assert ZWaveGroup.mock_calls[0][1][2] == 14
        assert group.add_association.called
        assert len(group.add_association.mock_calls) == 1
        assert group.add_association.mock_calls[0][1][0] == 24
        assert group.add_association.mock_calls[0][1][1] == 5

    def test_remove_association(self):
        """Test zwave change_association service."""
        ZWaveGroup = self.mock_openzwave.group.ZWaveGroup
        group = MagicMock()
        ZWaveGroup.return_value = group

        value = MockValue(
            index=12,
            command_class=const.COMMAND_CLASS_WAKE_UP,
        )
        node = MockNode(node_id=14)
        node.values = {12: value}
        node.get_values.return_value = node.values
        self.zwave_network.nodes = {14: node}

        self.hass.services.call('zwave', 'change_association', {
            const.ATTR_ASSOCIATION: 'remove',
            const.ATTR_NODE_ID: 14,
            const.ATTR_TARGET_NODE_ID: 24,
            const.ATTR_GROUP: 3,
            const.ATTR_INSTANCE: 5,
        })
        self.hass.block_till_done()

        assert ZWaveGroup.called
        assert len(ZWaveGroup.mock_calls) == 2
        assert ZWaveGroup.mock_calls[0][1][0] == 3
        assert ZWaveGroup.mock_calls[0][1][2] == 14
        assert group.remove_association.called
        assert len(group.remove_association.mock_calls) == 1
        assert group.remove_association.mock_calls[0][1][0] == 24
        assert group.remove_association.mock_calls[0][1][1] == 5

    def test_refresh_entity(self):
        """Test zwave refresh_entity service."""
        node = MockNode()
        value = MockValue(data=False, node=node,
                          command_class=const.COMMAND_CLASS_SENSOR_BINARY)
        power_value = MockValue(data=50, node=node,
                                command_class=const.COMMAND_CLASS_METER)
        values = MockEntityValues(primary=value, power=power_value)
        device = get_device(node=node, values=values, node_config={})
        device.hass = self.hass
        device.entity_id = 'binary_sensor.mock_entity_id'
        self.hass.add_job(device.async_added_to_hass())
        self.hass.block_till_done()

        self.hass.services.call('zwave', 'refresh_entity', {
            ATTR_ENTITY_ID: 'binary_sensor.mock_entity_id',
        })
        self.hass.block_till_done()

        assert node.refresh_value.called
        assert len(node.refresh_value.mock_calls) == 2
        self.assertEqual(sorted([node.refresh_value.mock_calls[0][1][0],
                                 node.refresh_value.mock_calls[1][1][0]]),
                         sorted([value.value_id, power_value.value_id]))

    def test_refresh_node(self):
        """Test zwave refresh_node service."""
        node = MockNode(node_id=14)
        self.zwave_network.nodes = {14: node}
        self.hass.services.call('zwave', 'refresh_node', {
            const.ATTR_NODE_ID: 14,
        })
        self.hass.block_till_done()

        assert node.refresh_info.called
        assert len(node.refresh_info.mock_calls) == 1

    def test_heal_node(self):
        """Test zwave heal_node service."""
        node = MockNode(node_id=19)
        self.zwave_network.nodes = {19: node}
        self.hass.services.call('zwave', 'heal_node', {
            const.ATTR_NODE_ID: 19,
        })
        self.hass.block_till_done()

        assert node.heal.called
        assert len(node.heal.mock_calls) == 1

    def test_test_node(self):
        """Test the zwave test_node service."""
        node = MockNode(node_id=19)
        self.zwave_network.nodes = {19: node}
        self.hass.services.call('zwave', 'test_node', {
            const.ATTR_NODE_ID: 19,
        })
        self.hass.block_till_done()

        assert node.test.called
        assert len(node.test.mock_calls) == 1
