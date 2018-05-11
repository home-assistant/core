"""Test all functions related to the basic accessory implementation.

This includes tests for all mock object types.
"""
from datetime import datetime, timedelta
from unittest.mock import patch, Mock

from homeassistant.components.homekit.accessories import (
    debounce, HomeAccessory, HomeBridge, HomeDriver)
from homeassistant.components.homekit.const import (
    BRIDGE_MODEL, BRIDGE_NAME, BRIDGE_SERIAL_NUMBER, SERV_ACCESSORY_INFO,
    CHAR_FIRMWARE_REVISION, CHAR_MANUFACTURER, CHAR_MODEL, CHAR_NAME,
    CHAR_SERIAL_NUMBER, MANUFACTURER)
from homeassistant.const import __version__, ATTR_NOW, EVENT_TIME_CHANGED
import homeassistant.util.dt as dt_util


def patch_debounce():
    """Return patch for debounce method."""
    return patch('homeassistant.components.homekit.accessories.debounce',
                 lambda f: lambda *args, **kwargs: f(*args, **kwargs))


async def test_debounce(hass):
    """Test add_timeout decorator function."""
    def demo_func(*args):
        nonlocal arguments, counter
        counter += 1
        arguments = args

    arguments = None
    counter = 0
    mock = Mock(hass=hass)

    debounce_demo = debounce(demo_func)
    assert debounce_demo.__name__ == 'demo_func'
    now = datetime(2018, 1, 1, 20, 0, 0, tzinfo=dt_util.UTC)

    with patch('homeassistant.util.dt.utcnow', return_value=now):
        await hass.async_add_job(debounce_demo, mock, 'value')
    hass.bus.async_fire(
        EVENT_TIME_CHANGED, {ATTR_NOW: now + timedelta(seconds=3)})
    await hass.async_block_till_done()
    assert counter == 1
    assert len(arguments) == 2

    with patch('homeassistant.util.dt.utcnow', return_value=now):
        await hass.async_add_job(debounce_demo, mock, 'value')
        await hass.async_add_job(debounce_demo, mock, 'value')

    hass.bus.async_fire(
        EVENT_TIME_CHANGED, {ATTR_NOW: now + timedelta(seconds=3)})
    await hass.async_block_till_done()
    assert counter == 2


async def test_home_accessory(hass):
    """Test HomeAccessory class."""
    acc = HomeAccessory(hass, 'Home Accessory', 'homekit.accessory', 2, None)
    assert acc.hass == hass
    assert acc.display_name == 'Home Accessory'
    assert acc.aid == 2
    assert acc.category == 1  # Category.OTHER
    assert len(acc.services) == 1
    serv = acc.services[0]  # SERV_ACCESSORY_INFO
    assert serv.display_name == SERV_ACCESSORY_INFO
    assert serv.get_characteristic(CHAR_NAME).value == 'Home Accessory'
    assert serv.get_characteristic(CHAR_MANUFACTURER).value == MANUFACTURER
    assert serv.get_characteristic(CHAR_MODEL).value == 'Homekit'
    assert serv.get_characteristic(CHAR_SERIAL_NUMBER).value == \
        'homekit.accessory'

    hass.states.async_set('homekit.accessory', 'on')
    await hass.async_block_till_done()
    await hass.async_add_job(acc.run)
    hass.states.async_set('homekit.accessory', 'off')
    await hass.async_block_till_done()

    acc = HomeAccessory('hass', 'test_name', 'test_model.demo', 2, None)
    assert acc.display_name == 'test_name'
    assert acc.aid == 2
    assert len(acc.services) == 1
    serv = acc.services[0]  # SERV_ACCESSORY_INFO
    assert serv.get_characteristic(CHAR_MODEL).value == 'Test Model'


def test_home_bridge():
    """Test HomeBridge class."""
    bridge = HomeBridge('hass')
    assert bridge.hass == 'hass'
    assert bridge.display_name == BRIDGE_NAME
    assert bridge.category == 2  # Category.BRIDGE
    assert len(bridge.services) == 1
    serv = bridge.services[0]  # SERV_ACCESSORY_INFO
    assert serv.display_name == SERV_ACCESSORY_INFO
    assert serv.get_characteristic(CHAR_NAME).value == BRIDGE_NAME
    assert serv.get_characteristic(CHAR_FIRMWARE_REVISION).value == __version__
    assert serv.get_characteristic(CHAR_MANUFACTURER).value == MANUFACTURER
    assert serv.get_characteristic(CHAR_MODEL).value == BRIDGE_MODEL
    assert serv.get_characteristic(CHAR_SERIAL_NUMBER).value == \
        BRIDGE_SERIAL_NUMBER

    bridge = HomeBridge('hass', 'test_name')
    assert bridge.display_name == 'test_name'
    assert len(bridge.services) == 1
    serv = bridge.services[0]  # SERV_ACCESSORY_INFO

    # setup_message
    bridge.setup_message()

    # add_paired_client
    with patch('pyhap.accessory.Accessory.add_paired_client') \
        as mock_add_paired_client, \
        patch('homeassistant.components.homekit.accessories.'
              'dismiss_setup_message') as mock_dissmiss_msg:
        bridge.add_paired_client('client_uuid', 'client_public')

    mock_add_paired_client.assert_called_with('client_uuid', 'client_public')
    mock_dissmiss_msg.assert_called_with('hass')

    # remove_paired_client
    with patch('pyhap.accessory.Accessory.remove_paired_client') \
        as mock_remove_paired_client, \
        patch('homeassistant.components.homekit.accessories.'
              'show_setup_message') as mock_show_msg:
        bridge.remove_paired_client('client_uuid')

    mock_remove_paired_client.assert_called_with('client_uuid')
    mock_show_msg.assert_called_with('hass', bridge)


def test_home_driver():
    """Test HomeDriver class."""
    bridge = HomeBridge('hass')
    ip_address = '127.0.0.1'
    port = 51826
    path = '.homekit.state'

    with patch('pyhap.accessory_driver.AccessoryDriver.__init__') \
            as mock_driver:
        HomeDriver(bridge, ip_address, port, path)

    mock_driver.assert_called_with(bridge, ip_address, port, path)
