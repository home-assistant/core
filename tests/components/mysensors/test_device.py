"""Test MySensors device."""
import asyncio
import sys
from unittest.mock import MagicMock, patch

import pytest

from tests.components.mysensors import (
    DEVICE, MockChild, MockGateway, MockMessage, MockMQTTGateway, MockNode,
    get_gateway, setup_mysensors)

# pylint: disable=redefined-outer-name


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
    sys.modules['mysensors'] = MagicMock()
    sys.modules['mysensors.mysensors'] = MagicMock()
    import mysensors.mysensors as mysensors
    mysensors.AsyncMQTTGateway = MockMQTTGateway
    mysensors.AsyncSerialGateway = MockGateway
    mysensors.AsyncTCPGateway = MockGateway

    return mysensors


@pytest.fixture
def mock_gw_ready(loop):
    """Mock gateway ready future."""
    fut = asyncio.Future(loop=loop)
    fut.set_result(True)
    with patch('homeassistant.components.mysensors.gateway.asyncio.Future',
               return_value=fut) as mock_future:
        yield mock_future


async def test_sensor_unit_prefix(hass, gateway):
    """Test discovery of a sensor platform with sensor with unit prefix."""
    gateway.sensors[1] = node = MockNode(1)
    child_type = gateway.const.Presentation.S_SOUND
    value_type = gateway.const.SetReq.V_LEVEL
    gateway.sensors[1].children[1] = child = MockChild(1, child_type)
    payload = '20.0'
    child.values[value_type] = payload
    child.values[gateway.const.SetReq.V_UNIT_PREFIX] = 'MdB'
    msg = MockMessage(
        1, 1, 1, sub_type=value_type, payload=payload, gateway=gateway)
    gateway.event_callback(msg)
    await hass.async_block_till_done()
    entity_id = 'sensor.mock_sketch_{}_{}'.format(node.sensor_id, child.id)
    state = hass.states.get(entity_id)
    assert state.state == payload
    assert state.attributes['unit_of_measurement'] == 'MdB'


async def test_update_switch(hass, gateway):
    """Test update value of switch device."""
    gateway.sensors[1] = node = MockNode(1)
    child_type = gateway.const.Presentation.S_BINARY
    value_type = gateway.const.SetReq.V_STATUS
    gateway.sensors[1].children[1] = child = MockChild(1, child_type)
    payload = '0'
    child.values[value_type] = payload
    msg = MockMessage(
        1, 1, 1, sub_type=value_type, payload=payload, gateway=gateway)
    gateway.event_callback(msg)
    await hass.async_block_till_done()
    entity_id = 'switch.mock_sketch_{}_{}'.format(node.sensor_id, child.id)
    state = hass.states.get(entity_id)
    assert state.state == 'off'
    payload = '1'
    child.values[value_type] = payload
    msg = MockMessage(
        1, 1, 1, sub_type=value_type, payload=payload, gateway=gateway)
    gateway.event_callback(msg)
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == 'on'


async def test_update_light(hass, gateway):
    """Test update value of light device."""
    gateway.sensors[1] = node = MockNode(1)
    child_type = gateway.const.Presentation.S_DIMMER
    value_type = gateway.const.SetReq.V_PERCENTAGE
    gateway.sensors[1].children[1] = child = MockChild(1, child_type)
    payload = '100'
    child.values[value_type] = payload
    v_status_type = gateway.const.SetReq.V_STATUS
    child.values[v_status_type] = '0'
    msg = MockMessage(
        1, 1, 1, sub_type=value_type, payload=payload, gateway=gateway)
    gateway.event_callback(msg)
    await hass.async_block_till_done()
    entity_id = 'light.mock_sketch_{}_{}'.format(node.sensor_id, child.id)
    state = hass.states.get(entity_id)
    assert state.state == 'off'
    child.values[v_status_type] = '1'
    msg = MockMessage(
        1, 1, 1, sub_type=v_status_type, payload='1', gateway=gateway)
    gateway.event_callback(msg)
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == 'on'
    assert state.attributes['brightness'] == 255
