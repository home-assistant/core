"""Test for smart home alexa support."""
import asyncio

import pytest

from homeassistant.components.alexa import smart_home

from tests.common import async_mock_service


def test_create_api_message():
    """Create a API message."""
    msg = smart_home.api_message('testName', 'testNameSpace')

    assert msg['header']['messageId'] is not None
    assert msg['header']['name'] == 'testName'
    assert msg['header']['namespace'] == 'testNameSpace'
    assert msg['header']['payloadVersion'] == '2'
    assert msg['payload'] == {}


@asyncio.coroutine
def test_wrong_version(hass):
    """Test with wrong version."""
    msg = smart_home.api_message('testName', 'testNameSpace')
    msg['header']['payloadVersion'] = '3'

    with pytest.raises(AssertionError):
        yield from smart_home.async_handle_message(hass, msg)


@asyncio.coroutine
def test_discovery_request(hass):
    """Test alexa discovery request."""
    msg = smart_home.api_message(
        'DiscoverAppliancesRequest', 'Alexa.ConnectedHome.Discovery')

    # settup test devices
    hass.states.async_set(
        'switch.test', 'on', {'friendly_name': "Test switch"})

    hass.states.async_set(
        'light.test_1', 'on', {'friendly_name': "Test light 1"})
    hass.states.async_set(
        'light.test_2', 'on', {
            'friendly_name': "Test light 2", 'supported_features': 1
        })

    resp = yield from smart_home.async_api_discovery(hass, msg)

    assert len(resp['payload']['discoveredAppliances']) == 3
    assert resp['header']['name'] == 'DiscoverAppliancesResponse'
    assert resp['header']['namespace'] == 'Alexa.ConnectedHome.Discovery'

    for i, appliance in enumerate(resp['payload']['discoveredAppliances']):
        if appliance['applianceId'] == 'switch#test':
            assert appliance['applianceTypes'][0] == "SWITCH"
            assert appliance['friendlyName'] == "Test switch"
            assert appliance['actions'] == ['turnOff', 'turnOn']
            continue

        if appliance['applianceId'] == 'light#test_1':
            assert appliance['applianceTypes'][0] == "LIGHT"
            assert appliance['friendlyName'] == "Test light 1"
            assert appliance['actions'] == ['turnOff', 'turnOn']
            continue

        if appliance['applianceId'] == 'light#test_2':
            assert appliance['applianceTypes'][0] == "LIGHT"
            assert appliance['friendlyName'] == "Test light 2"
            assert appliance['actions'] == \
                ['turnOff', 'turnOn', 'setPercentage']
            continue

        raise AssertionError("Unknown appliance!")


@asyncio.coroutine
def test_api_entity_not_exists(hass):
    """Test api turn on process without entity."""
    msg_switch = smart_home.api_message(
        'TurnOnRequest', 'Alexa.ConnectedHome.Control', {
            'appliance': {
                'applianceId': 'switch#test'
            }
        })

    call_switch = async_mock_service(hass, 'switch', 'turn_on')

    resp = yield from smart_home.async_api_turn_on(hass, msg_switch)
    assert len(call_switch) == 0
    assert resp['header']['name'] == 'DriverInternalError'
    assert resp['header']['namespace'] == 'Alexa.ConnectedHome.Control'


@asyncio.coroutine
@pytest.mark.parametrize("domain", ['light', 'switch'])
def test_api_turn_on(hass, domain):
    """Test api turn on process."""
    msg = smart_home.api_message(
        'TurnOnRequest', 'Alexa.ConnectedHome.Control', {
            'appliance': {
                'applianceId': '{}#test'.format(domain)
            }
        })

    # settup test devices
    hass.states.async_set(
        '{}.test'.format(domain), 'off', {
            'friendly_name': "Test {}".format(domain)
        })

    call = async_mock_service(hass, domain, 'turn_on')

    resp = yield from smart_home.async_api_turn_on(hass, msg)
    assert len(call) == 1
    assert call[0].data['entity_id'] == '{}.test'.format(domain)
    assert resp['header']['name'] == 'TurnOnConfirmation'


@asyncio.coroutine
@pytest.mark.parametrize("domain", ['light', 'switch'])
def test_api_turn_off(hass, domain):
    """Test api turn on process."""
    msg = smart_home.api_message(
        'TurnOffRequest', 'Alexa.ConnectedHome.Control', {
            'appliance': {
                'applianceId': '{}#test'.format(domain)
            }
        })

    # settup test devices
    hass.states.async_set(
        '{}.test'.format(domain), 'on', {
            'friendly_name': "Test {}".format(domain)
        })

    call = async_mock_service(hass, domain, 'turn_off')

    resp = yield from smart_home.async_api_turn_off(hass, msg)
    assert len(call) == 1
    assert call[0].data['entity_id'] == '{}.test'.format(domain)
    assert resp['header']['name'] == 'TurnOffConfirmation'


@asyncio.coroutine
def test_api_set_percentage_light(hass):
    """Test api set brightness process."""
    msg_light = smart_home.api_message(
        'SetPercentageRequest', 'Alexa.ConnectedHome.Control', {
            'appliance': {
                'applianceId': 'light#test'
            },
            'percentageState': {
                'value': '50'
            }
        })

    # settup test devices
    hass.states.async_set(
        'light.test', 'off', {'friendly_name': "Test light"})

    call_light = async_mock_service(hass, 'light', 'turn_on')

    resp = yield from smart_home.async_api_set_percentage(hass, msg_light)
    assert len(call_light) == 1
    assert call_light[0].data['entity_id'] == 'light.test'
    assert call_light[0].data['brightness'] == '50'
    assert resp['header']['name'] == 'SetPercentageConfirmation'
