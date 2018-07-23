"""Test MySensors gateway."""
import asyncio
import logging
from unittest.mock import call, patch

import pytest
import voluptuous as vol

from homeassistant.components import mysensors as mysensors_comp
from homeassistant.setup import async_setup_component
from tests.common import async_fire_mqtt_message, mock_coro_func
from tests.components.mysensors import (
    DEVICE, MockChild, MockGateway, MockMessage, MockMQTTGateway, MockNode,
    get_gateway, setup_mysensors)

# pylint: disable=protected-access, redefined-outer-name


@pytest.fixture
def gateway(loop, hass, mock_isdevice, mock_mysensors, mock_gw_ready):
    """Set up mysensors component and return a gateway instance."""
    res = loop.run_until_complete(setup_mysensors(hass))
    assert res
    loop.run_until_complete(hass.async_block_till_done())
    gateway = get_gateway(hass)
    return gateway


@pytest.fixture
def mock_isdevice():
    """Mock isdevice."""
    with patch('homeassistant.helpers.config_validation.isdevice',
               return_value=DEVICE) as mock_test:
        yield mock_test


@pytest.fixture
def mock_mysensors():
    """Mock mysensors library."""
    with patch('mysensors.mysensors.AsyncMQTTGateway',
               side_effect=MockMQTTGateway), \
        patch('mysensors.mysensors.AsyncSerialGateway',
              side_effect=MockGateway), \
            patch('mysensors.mysensors.AsyncTCPGateway',
                  side_effect=MockGateway):
        yield


@pytest.fixture
def mock_discover_platform():
    """Mock discovery.load_platform."""
    with patch('homeassistant.components.mysensors.gateway.discovery'
               '.async_load_platform',
               side_effect=mock_coro_func()) as mock_discovery:
        yield mock_discovery


@pytest.fixture
def mock_gw_ready(loop):
    """Mock gateway ready future."""
    fut = asyncio.Future(loop=loop)
    fut.set_result(True)
    with patch('homeassistant.components.mysensors.gateway.asyncio.Future',
               return_value=fut) as mock_future:
        yield mock_future


async def test_setup(gateway):
    """Test setup of mysensors."""
    assert not gateway.sensors


async def test_domain_name_device(hass, mock_mysensors, mock_gw_ready):
    """Test setup of mysensors with domain name device."""
    config = {'mysensors': {
        'gateways': [{'device': 'domain.com'}], 'version': '2.0',
        'persistence': False}}

    with patch('homeassistant.components.mysensors.cv.isdevice',
               side_effect=vol.Invalid('Bad device')):
        with patch('socket.getaddrinfo'):
            res = await async_setup_component(hass, 'mysensors', config)
    assert res
    await hass.async_block_till_done()
    gateway = get_gateway(hass)
    assert gateway.device == 'domain.com'
    assert not gateway.sensors


async def test_mqtt_device(hass, caplog, mock_mysensors, mqtt_mock):
    """Test setup of mysensors with mqtt device."""
    config = {'mysensors': {
        'gateways': [{'device': 'mqtt'}], 'version': '2.0',
        'persistence': False}}

    res = await async_setup_component(hass, 'mysensors', config)
    assert res
    await hass.async_block_till_done()
    gateway = get_gateway(hass)
    assert gateway.device == 'mqtt'
    assert not gateway.sensors

    topic = 'test'
    payload = 'test_payload'
    qos = 0
    retain = False

    gateway.pub_callback(topic, payload, qos, retain)
    await hass.async_block_till_done()

    assert mqtt_mock.async_publish.call_count == 1
    assert mqtt_mock.async_publish.call_args == call(
        topic, payload, qos, retain)

    calls = []

    def sub_callback(*args):
        """Mock the subscription callback."""
        calls.append(args)

    gateway.sub_callback(topic, sub_callback, qos)
    await hass.async_block_till_done()
    async_fire_mqtt_message(hass, topic, payload, qos, retain)
    await hass.async_block_till_done()
    await hass.async_block_till_done()  # not sure why we need two?

    assert len(calls) == 1
    assert calls[0] == (topic, payload, qos)


async def test_persistence(
        hass, mock_isdevice, mock_discover_platform, mock_mysensors,
        mock_gw_ready):
    """Test MySensors gateway persistence."""
    config = {'mysensors': {
        'gateways': [{'device': DEVICE, 'persistence_file': 'test.json'}],
        'version': '2.0', 'persistence': True}}
    res = await async_setup_component(hass, 'mysensors', config)
    assert res
    gateway = get_gateway(hass)
    gateway.sensors[1] = MockNode(1)
    child_type = gateway.const.Presentation.S_TEMP
    value_type = gateway.const.SetReq.V_TEMP
    gateway.sensors[1].children[1] = child = MockChild(1, child_type)
    payload = '20.0'
    child.values[value_type] = payload
    new_dev_ids = [(id(gateway), 1, child.id, value_type)]
    await hass.async_block_till_done()
    assert mock_discover_platform.call_count == 1
    assert mock_discover_platform.call_args == call(
        hass, 'sensor', mysensors_comp.DOMAIN,
        {'devices': new_dev_ids, 'name': mysensors_comp.DOMAIN})


async def test_gateway_not_ready(hass, caplog, mock_isdevice, mock_mysensors):
    """Test gateway not ready."""
    called = False

    async def fut():
        """Fake future that raises asyncio.TimeoutError."""
        nonlocal called
        called = True
        raise asyncio.TimeoutError

    with patch('homeassistant.components.mysensors.gateway.asyncio.Future',
               return_value=fut()):
        assert not called
        res = await setup_mysensors(hass)
        assert res
        await hass.async_block_till_done()

    assert called
    assert 'Gateway {} not ready after {} secs'.format(
        DEVICE, mysensors_comp.gateway.GATEWAY_READY_TIMEOUT) in caplog.text


async def test_set_gateway_ready(hass, mock_isdevice, mock_mysensors):
    """Test set gateway ready."""
    fut = asyncio.Future(loop=hass.loop)

    with patch('homeassistant.components.mysensors.gateway.asyncio.Future',
               return_value=fut):
        res = await setup_mysensors(hass)
        assert res
        gateway = get_gateway(hass)

        async def gateway_start():
            """Start gateway."""
            value_type = gateway.const.Internal.I_GATEWAY_READY
            msg = MockMessage(0, 255, 3, sub_type=value_type, gateway=gateway)
            hass.async_add_job(gateway.event_callback, msg)

        gateway.start = gateway_start
        await hass.async_block_till_done()

    assert fut.done()


async def test_validate_child(gateway):
    """Test validate_child."""
    gateway.sensors[1] = MockNode(1)
    child_type = gateway.const.Presentation.S_TEMP
    value_type = gateway.const.SetReq.V_TEMP
    gateway.sensors[1].children[1] = child = MockChild(1, child_type)
    child.values[value_type] = '20.0'
    validated = mysensors_comp.gateway._validate_child(gateway, 1, child)
    assert 'sensor' in validated
    assert len(validated['sensor']) == 1
    dev_id = validated['sensor'][0]
    assert dev_id == (id(gateway), 1, child.id, value_type)


async def test_validate_child_no_values(gateway):
    """Test validate_child without child values."""
    gateway.sensors[1] = MockNode(1)
    child_type = gateway.const.Presentation.S_TEMP
    gateway.sensors[1].children[1] = child = MockChild(1, child_type)
    validated = mysensors_comp.gateway._validate_child(gateway, 1, child)
    assert not validated


async def test_validate_child_no_sketch(gateway):
    """Test validate_child with no sketch."""
    gateway.sensors[1] = MockNode(1, sketch_name=None)
    child_type = gateway.const.Presentation.S_TEMP
    value_type = gateway.const.SetReq.V_TEMP
    gateway.sensors[1].children[1] = child = MockChild(1, child_type)
    child.values[value_type] = '20.0'
    validated = mysensors_comp.gateway._validate_child(gateway, 1, child)
    assert not validated


async def test_validate_bad_child(gateway):
    """Test validate_child with bad child type."""
    gateway.sensors[1] = MockNode(1)
    child_type = -1
    value_type = gateway.const.SetReq.V_TEMP
    gateway.sensors[1].children[1] = child = MockChild(1, child_type)
    child.values[value_type] = '20.0'
    validated = mysensors_comp.gateway._validate_child(gateway, 1, child)
    assert not validated


async def test_validate_child_bad_value(gateway):
    """Test validate_child with bad value type."""
    gateway.sensors[1] = MockNode(1)
    child_type = gateway.const.Presentation.S_TEMP
    value_type = -1
    gateway.sensors[1].children[1] = child = MockChild(1, child_type)
    child.values[value_type] = '20.0'
    validated = mysensors_comp.gateway._validate_child(gateway, 1, child)
    assert not validated


async def test_callback(hass, gateway, mock_discover_platform):
    """Test MySensors gateway callback."""
    gateway.sensors[1] = MockNode(1)
    child_type = gateway.const.Presentation.S_TEMP
    value_type = gateway.const.SetReq.V_TEMP
    gateway.sensors[1].children[1] = child = MockChild(1, child_type)
    payload = '20.0'
    child.values[value_type] = payload
    new_dev_ids = [(id(gateway), 1, child.id, value_type)]
    msg = MockMessage(
        1, 1, 1, sub_type=value_type, payload=payload, gateway=gateway)
    gateway.event_callback(msg)
    assert mock_discover_platform.call_count == 1
    assert mock_discover_platform.call_args == call(
        hass, 'sensor', mysensors_comp.DOMAIN,
        {'devices': new_dev_ids, 'name': mysensors_comp.DOMAIN})


async def test_callback_no_child(caplog, gateway):
    """Test MySensors gateway callback for non child."""
    caplog.set_level(logging.DEBUG)
    gateway.sensors[1] = MockNode(1)
    msg = MockMessage(
        1, 255, 0, sub_type=17, gateway=gateway)
    gateway.event_callback(msg)
    assert 'DEBUG' in caplog.text
    assert 'Not a child update for node 1' in caplog.text


async def test_discover_platform(hass, gateway):
    """Test discovery of a sensor platform."""
    gateway.sensors[1] = node = MockNode(1)
    child_type = gateway.const.Presentation.S_SOUND
    value_type = gateway.const.SetReq.V_LEVEL
    gateway.sensors[1].children[1] = child = MockChild(1, child_type)
    payload = '20.0'
    child.values[value_type] = payload
    msg = MockMessage(
        1, 1, 1, sub_type=value_type, payload=payload, gateway=gateway)
    gateway.event_callback(msg)
    await hass.async_block_till_done()
    entity_id = 'sensor.mock_sketch_{}_{}'.format(node.sensor_id, child.id)
    state = hass.states.get(entity_id)
    assert state.state == payload
