"""Tests for the HomeKit component."""
from unittest.mock import patch, ANY, Mock

import pytest

from homeassistant import setup
from homeassistant.components.homekit import (
    generate_aid, HomeKit, STATUS_READY, STATUS_RUNNING,
    STATUS_STOPPED, STATUS_WAIT)
from homeassistant.components.homekit.accessories import HomeBridge
from homeassistant.components.homekit.const import (
    CONF_AUTO_START, BRIDGE_NAME, DEFAULT_PORT, DOMAIN, HOMEKIT_FILE,
    SERVICE_HOMEKIT_START)
from homeassistant.const import (
    CONF_NAME, CONF_IP_ADDRESS, CONF_PORT,
    EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP)
from homeassistant.core import State
from homeassistant.helpers.entityfilter import generate_filter

from tests.components.homekit.common import patch_debounce

IP_ADDRESS = '127.0.0.1'
PATH_HOMEKIT = 'homeassistant.components.homekit'


@pytest.fixture(scope='module')
def debounce_patcher():
    """Patch debounce method."""
    patcher = patch_debounce()
    yield patcher.start()
    patcher.stop()


def test_generate_aid():
    """Test generate aid method."""
    aid = generate_aid('demo.entity')
    assert isinstance(aid, int)
    assert aid >= 2 and aid <= 18446744073709551615

    with patch(PATH_HOMEKIT + '.adler32') as mock_adler32:
        mock_adler32.side_effect = [0, 1]
        assert generate_aid('demo.entity') is None


async def test_setup_min(hass):
    """Test async_setup with min config options."""
    with patch(PATH_HOMEKIT + '.HomeKit') as mock_homekit:
        assert await setup.async_setup_component(
            hass, DOMAIN, {DOMAIN: {}})

    mock_homekit.assert_any_call(hass, BRIDGE_NAME, DEFAULT_PORT, None, ANY,
                                 {})
    assert mock_homekit().setup.called is True

    # Test auto start enabled
    mock_homekit.reset_mock()
    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()

    mock_homekit().start.assert_called_with(ANY)


async def test_setup_auto_start_disabled(hass):
    """Test async_setup with auto start disabled and test service calls."""
    config = {DOMAIN: {CONF_AUTO_START: False, CONF_NAME: 'Test Name',
                       CONF_PORT: 11111, CONF_IP_ADDRESS: '172.0.0.0'}}

    with patch(PATH_HOMEKIT + '.HomeKit') as mock_homekit:
        mock_homekit.return_value = homekit = Mock()
        assert await setup.async_setup_component(
            hass, DOMAIN, config)

    mock_homekit.assert_any_call(hass, 'Test Name', 11111, '172.0.0.0', ANY,
                                 {})
    assert mock_homekit().setup.called is True

    # Test auto_start disabled
    homekit.reset_mock()
    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()
    assert homekit.start.called is False

    # Test start call with driver is ready
    homekit.reset_mock()
    homekit.status = STATUS_READY

    await hass.services.async_call(
        DOMAIN, SERVICE_HOMEKIT_START, blocking=True)
    assert homekit.start.called is True

    # Test start call with driver started
    homekit.reset_mock()
    homekit.status = STATUS_STOPPED

    await hass.services.async_call(
        DOMAIN, SERVICE_HOMEKIT_START, blocking=True)
    assert homekit.start.called is False


async def test_homekit_setup(hass, hk_driver):
    """Test setup of bridge and driver."""
    homekit = HomeKit(hass, BRIDGE_NAME, DEFAULT_PORT, None, {}, {})

    with patch(PATH_HOMEKIT + '.accessories.HomeDriver',
               return_value=hk_driver) as mock_driver, \
            patch('homeassistant.util.get_local_ip') as mock_ip:
        mock_ip.return_value = IP_ADDRESS
        await hass.async_add_job(homekit.setup)

    path = hass.config.path(HOMEKIT_FILE)
    assert isinstance(homekit.bridge, HomeBridge)
    mock_driver.assert_called_with(
        hass, address=IP_ADDRESS, port=DEFAULT_PORT, persist_file=path)

    # Test if stop listener is setup
    assert hass.bus.async_listeners().get(EVENT_HOMEASSISTANT_STOP) == 1


async def test_homekit_setup_ip_address(hass, hk_driver):
    """Test setup with given IP address."""
    homekit = HomeKit(hass, BRIDGE_NAME, DEFAULT_PORT, '172.0.0.0', {}, {})

    with patch(PATH_HOMEKIT + '.accessories.HomeDriver',
               return_value=hk_driver) as mock_driver:
        await hass.async_add_job(homekit.setup)
    mock_driver.assert_called_with(
        hass, address='172.0.0.0', port=DEFAULT_PORT, persist_file=ANY)


async def test_homekit_add_accessory():
    """Add accessory if config exists and get_acc returns an accessory."""
    homekit = HomeKit('hass', None, None, None, lambda entity_id: True, {})
    homekit.driver = 'driver'
    homekit.bridge = mock_bridge = Mock()

    with patch(PATH_HOMEKIT + '.get_accessory') as mock_get_acc:

        mock_get_acc.side_effect = [None, 'acc', None]
        homekit.add_bridge_accessory(State('light.demo', 'on'))
        mock_get_acc.assert_called_with('hass', 'driver', ANY, 363398124, {})
        assert not mock_bridge.add_accessory.called

        homekit.add_bridge_accessory(State('demo.test', 'on'))
        mock_get_acc.assert_called_with('hass', 'driver', ANY, 294192020, {})
        assert mock_bridge.add_accessory.called

        homekit.add_bridge_accessory(State('demo.test_2', 'on'))
        mock_get_acc.assert_called_with('hass', 'driver', ANY, 429982757, {})
        mock_bridge.add_accessory.assert_called_with('acc')


async def test_homekit_entity_filter(hass):
    """Test the entity filter."""
    entity_filter = generate_filter(['cover'], ['demo.test'], [], [])
    homekit = HomeKit(hass, None, None, None, entity_filter, {})

    with patch(PATH_HOMEKIT + '.get_accessory') as mock_get_acc:
        mock_get_acc.return_value = None

        homekit.add_bridge_accessory(State('cover.test', 'open'))
        assert mock_get_acc.called is True
        mock_get_acc.reset_mock()

        homekit.add_bridge_accessory(State('demo.test', 'on'))
        assert mock_get_acc.called is True
        mock_get_acc.reset_mock()

        homekit.add_bridge_accessory(State('light.demo', 'light'))
        assert mock_get_acc.called is False


async def test_homekit_start(hass, hk_driver, debounce_patcher):
    """Test HomeKit start method."""
    pin = b'123-45-678'
    homekit = HomeKit(hass, None, None, None, {}, {'cover.demo': {}})
    homekit.bridge = 'bridge'
    homekit.driver = hk_driver

    hass.states.async_set('light.demo', 'on')
    state = hass.states.async_all()[0]

    with patch(PATH_HOMEKIT + '.HomeKit.add_bridge_accessory') as \
        mock_add_acc, \
        patch(PATH_HOMEKIT + '.show_setup_message') as mock_setup_msg, \
        patch('pyhap.accessory_driver.AccessoryDriver.add_accessory') as \
        hk_driver_add_acc, \
        patch('pyhap.accessory_driver.AccessoryDriver.start') as \
            hk_driver_start:
        await hass.async_add_job(homekit.start)

    mock_add_acc.assert_called_with(state)
    mock_setup_msg.assert_called_with(hass, pin)
    hk_driver_add_acc.assert_called_with('bridge')
    assert hk_driver_start.called
    assert homekit.status == STATUS_RUNNING

    # Test start() if already started
    hk_driver_start.reset_mock()
    await hass.async_add_job(homekit.start)
    assert not hk_driver_start.called


async def test_homekit_stop(hass):
    """Test HomeKit stop method."""
    homekit = HomeKit(hass, None, None, None, None, None)
    homekit.driver = Mock()

    assert homekit.status == STATUS_READY
    await hass.async_add_job(homekit.stop)
    homekit.status = STATUS_WAIT
    await hass.async_add_job(homekit.stop)
    homekit.status = STATUS_STOPPED
    await hass.async_add_job(homekit.stop)
    assert homekit.driver.stop.called is False

    # Test if driver is started
    homekit.status = STATUS_RUNNING
    await hass.async_add_job(homekit.stop)
    assert homekit.driver.stop.called is True
