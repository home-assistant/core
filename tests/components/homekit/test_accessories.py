"""Test all functions related to the basic accessory implementation.

This includes tests for all mock object types.
"""
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import pytest

from homeassistant.components.homekit.accessories import (
    HomeAccessory,
    HomeBridge,
    HomeDriver,
    debounce,
)
from homeassistant.components.homekit.const import (
    ATTR_DISPLAY_NAME,
    ATTR_VALUE,
    BRIDGE_MODEL,
    BRIDGE_NAME,
    BRIDGE_SERIAL_NUMBER,
    CHAR_FIRMWARE_REVISION,
    CHAR_MANUFACTURER,
    CHAR_MODEL,
    CHAR_NAME,
    CHAR_SERIAL_NUMBER,
    CONF_LINKED_BATTERY_CHARGING_SENSOR,
    CONF_LINKED_BATTERY_SENSOR,
    CONF_LOW_BATTERY_THRESHOLD,
    MANUFACTURER,
    SERV_ACCESSORY_INFO,
)
from homeassistant.const import (
    ATTR_BATTERY_CHARGING,
    ATTR_BATTERY_LEVEL,
    ATTR_ENTITY_ID,
    ATTR_NOW,
    ATTR_SERVICE,
    EVENT_TIME_CHANGED,
    STATE_OFF,
    STATE_ON,
    __version__,
)
import homeassistant.util.dt as dt_util

from tests.common import async_mock_service


async def test_debounce(hass):
    """Test add_timeout decorator function."""

    def demo_func(*args):
        nonlocal arguments, counter
        counter += 1
        arguments = args

    arguments = None
    counter = 0
    mock = Mock(hass=hass, debounce={})

    debounce_demo = debounce(demo_func)
    assert debounce_demo.__name__ == "demo_func"
    now = datetime(2018, 1, 1, 20, 0, 0, tzinfo=dt_util.UTC)

    with patch("homeassistant.util.dt.utcnow", return_value=now):
        await hass.async_add_executor_job(debounce_demo, mock, "value")
    hass.bus.async_fire(EVENT_TIME_CHANGED, {ATTR_NOW: now + timedelta(seconds=3)})
    await hass.async_block_till_done()
    assert counter == 1
    assert len(arguments) == 2

    with patch("homeassistant.util.dt.utcnow", return_value=now):
        await hass.async_add_executor_job(debounce_demo, mock, "value")
        await hass.async_add_executor_job(debounce_demo, mock, "value")

    hass.bus.async_fire(EVENT_TIME_CHANGED, {ATTR_NOW: now + timedelta(seconds=3)})
    await hass.async_block_till_done()
    assert counter == 2


async def test_home_accessory(hass, hk_driver):
    """Test HomeAccessory class."""
    entity_id = "homekit.accessory"
    hass.states.async_set(entity_id, None)
    await hass.async_block_till_done()

    acc = HomeAccessory(hass, hk_driver, "Home Accessory", entity_id, 2, None)
    assert acc.hass == hass
    assert acc.display_name == "Home Accessory"
    assert acc.aid == 2
    assert acc.category == 1  # Category.OTHER
    assert len(acc.services) == 1
    serv = acc.services[0]  # SERV_ACCESSORY_INFO
    assert serv.display_name == SERV_ACCESSORY_INFO
    assert serv.get_characteristic(CHAR_NAME).value == "Home Accessory"
    assert serv.get_characteristic(CHAR_MANUFACTURER).value == MANUFACTURER
    assert serv.get_characteristic(CHAR_MODEL).value == "Homekit"
    assert serv.get_characteristic(CHAR_SERIAL_NUMBER).value == "homekit.accessory"

    hass.states.async_set(entity_id, "on")
    await hass.async_block_till_done()
    with patch(
        "homeassistant.components.homekit.accessories.HomeAccessory.update_state"
    ) as mock_update_state:
        await acc.run_handler()
        await hass.async_block_till_done()
        state = hass.states.get(entity_id)
        mock_update_state.assert_called_with(state)

        hass.states.async_remove(entity_id)
        await hass.async_block_till_done()
        assert mock_update_state.call_count == 1

    with pytest.raises(NotImplementedError):
        acc.update_state("new_state")

    # Test model name from domain
    entity_id = "test_model.demo"
    hass.states.async_set(entity_id, None)
    await hass.async_block_till_done()
    acc = HomeAccessory(hass, hk_driver, "test_name", entity_id, 2, None)
    serv = acc.services[0]  # SERV_ACCESSORY_INFO
    assert serv.get_characteristic(CHAR_MODEL).value == "Test Model"


async def test_battery_service(hass, hk_driver, caplog):
    """Test battery service."""
    entity_id = "homekit.accessory"
    hass.states.async_set(entity_id, None, {ATTR_BATTERY_LEVEL: 50})
    await hass.async_block_till_done()

    acc = HomeAccessory(hass, hk_driver, "Battery Service", entity_id, 2, None)
    acc.update_state = lambda x: None
    assert acc._char_battery.value == 0
    assert acc._char_low_battery.value == 0
    assert acc._char_charging.value == 2

    await acc.run_handler()
    await hass.async_block_till_done()
    assert acc._char_battery.value == 50
    assert acc._char_low_battery.value == 0
    assert acc._char_charging.value == 2

    hass.states.async_set(entity_id, None, {ATTR_BATTERY_LEVEL: 15})
    await hass.async_block_till_done()
    assert acc._char_battery.value == 15
    assert acc._char_low_battery.value == 1
    assert acc._char_charging.value == 2

    hass.states.async_set(entity_id, None, {ATTR_BATTERY_LEVEL: "error"})
    await hass.async_block_till_done()
    assert acc._char_battery.value == 15
    assert acc._char_low_battery.value == 1
    assert acc._char_charging.value == 2
    assert "ERROR" not in caplog.text

    # Test charging
    hass.states.async_set(
        entity_id, None, {ATTR_BATTERY_LEVEL: 10, ATTR_BATTERY_CHARGING: True}
    )
    await hass.async_block_till_done()

    acc = HomeAccessory(hass, hk_driver, "Battery Service", entity_id, 2, None)
    acc.update_state = lambda x: None
    assert acc._char_battery.value == 0
    assert acc._char_low_battery.value == 0
    assert acc._char_charging.value == 2

    await acc.run_handler()
    await hass.async_block_till_done()
    assert acc._char_battery.value == 10
    assert acc._char_low_battery.value == 1
    assert acc._char_charging.value == 1

    hass.states.async_set(
        entity_id, None, {ATTR_BATTERY_LEVEL: 100, ATTR_BATTERY_CHARGING: False}
    )
    await hass.async_block_till_done()
    assert acc._char_battery.value == 100
    assert acc._char_low_battery.value == 0
    assert acc._char_charging.value == 0


async def test_linked_battery_sensor(hass, hk_driver, caplog):
    """Test battery service with linked_battery_sensor."""
    entity_id = "homekit.accessory"
    linked_battery = "sensor.battery"
    hass.states.async_set(entity_id, "open", {ATTR_BATTERY_LEVEL: 100})
    hass.states.async_set(linked_battery, 50, None)
    await hass.async_block_till_done()

    acc = HomeAccessory(
        hass,
        hk_driver,
        "Battery Service",
        entity_id,
        2,
        {CONF_LINKED_BATTERY_SENSOR: linked_battery},
    )
    acc.update_state = lambda x: None
    assert acc.linked_battery_sensor == linked_battery

    await acc.run_handler()
    await hass.async_block_till_done()
    assert acc._char_battery.value == 50
    assert acc._char_low_battery.value == 0
    assert acc._char_charging.value == 2

    hass.states.async_set(linked_battery, 10, None)
    await hass.async_block_till_done()
    assert acc._char_battery.value == 10
    assert acc._char_low_battery.value == 1

    # Ignore battery change on entity if it has linked_battery
    hass.states.async_set(entity_id, "open", {ATTR_BATTERY_LEVEL: 90})
    await hass.async_block_till_done()
    assert acc._char_battery.value == 10

    # Test none numeric state for linked_battery
    hass.states.async_set(linked_battery, "error", None)
    await hass.async_block_till_done()
    assert acc._char_battery.value == 10
    assert "ERROR" not in caplog.text

    # Test charging & low battery threshold
    hass.states.async_set(linked_battery, 20, {ATTR_BATTERY_CHARGING: True})
    await hass.async_block_till_done()

    acc = HomeAccessory(
        hass,
        hk_driver,
        "Battery Service",
        entity_id,
        2,
        {CONF_LINKED_BATTERY_SENSOR: linked_battery, CONF_LOW_BATTERY_THRESHOLD: 50},
    )
    acc.update_state = lambda x: None
    await acc.run_handler()
    await hass.async_block_till_done()
    assert acc._char_battery.value == 20
    assert acc._char_low_battery.value == 1
    assert acc._char_charging.value == 1

    hass.states.async_set(linked_battery, 100, {ATTR_BATTERY_CHARGING: False})
    await hass.async_block_till_done()
    assert acc._char_battery.value == 100
    assert acc._char_low_battery.value == 0
    assert acc._char_charging.value == 0


async def test_linked_battery_charging_sensor(hass, hk_driver, caplog):
    """Test battery service with linked_battery_charging_sensor."""
    entity_id = "homekit.accessory"
    linked_battery_charging_sensor = "binary_sensor.battery_charging"
    hass.states.async_set(entity_id, "open", {ATTR_BATTERY_LEVEL: 100})
    hass.states.async_set(linked_battery_charging_sensor, STATE_ON, None)
    await hass.async_block_till_done()

    acc = HomeAccessory(
        hass,
        hk_driver,
        "Battery Service",
        entity_id,
        2,
        {CONF_LINKED_BATTERY_CHARGING_SENSOR: linked_battery_charging_sensor},
    )
    acc.update_state = lambda x: None
    assert acc.linked_battery_charging_sensor == linked_battery_charging_sensor

    await acc.run_handler()
    await hass.async_block_till_done()
    assert acc._char_battery.value == 100
    assert acc._char_low_battery.value == 0
    assert acc._char_charging.value == 1

    hass.states.async_set(linked_battery_charging_sensor, STATE_OFF, None)
    await acc.run_handler()
    await hass.async_block_till_done()
    assert acc._char_charging.value == 0

    hass.states.async_set(linked_battery_charging_sensor, STATE_ON, None)
    await acc.run_handler()
    await hass.async_block_till_done()
    assert acc._char_charging.value == 1


async def test_linked_battery_sensor_and_linked_battery_charging_sensor(
    hass, hk_driver, caplog
):
    """Test battery service with linked_battery_sensor and a linked_battery_charging_sensor."""
    entity_id = "homekit.accessory"
    linked_battery = "sensor.battery"
    linked_battery_charging_sensor = "binary_sensor.battery_charging"
    hass.states.async_set(entity_id, "open", {ATTR_BATTERY_LEVEL: 100})
    hass.states.async_set(linked_battery, 50, None)
    hass.states.async_set(linked_battery_charging_sensor, STATE_ON, None)
    await hass.async_block_till_done()

    acc = HomeAccessory(
        hass,
        hk_driver,
        "Battery Service",
        entity_id,
        2,
        {
            CONF_LINKED_BATTERY_SENSOR: linked_battery,
            CONF_LINKED_BATTERY_CHARGING_SENSOR: linked_battery_charging_sensor,
        },
    )
    acc.update_state = lambda x: None
    assert acc.linked_battery_sensor == linked_battery

    await acc.run_handler()
    await hass.async_block_till_done()
    assert acc._char_battery.value == 50
    assert acc._char_low_battery.value == 0
    assert acc._char_charging.value == 1

    hass.states.async_set(linked_battery_charging_sensor, STATE_OFF, None)
    await hass.async_block_till_done()
    assert acc._char_battery.value == 50
    assert acc._char_low_battery.value == 0
    assert acc._char_charging.value == 0


async def test_missing_linked_battery_charging_sensor(hass, hk_driver, caplog):
    """Test battery service with linked_battery_charging_sensor that is mapping to a missing entity."""
    entity_id = "homekit.accessory"
    linked_battery_charging_sensor = "binary_sensor.battery_charging"
    hass.states.async_set(entity_id, "open", {ATTR_BATTERY_LEVEL: 100})
    await hass.async_block_till_done()

    acc = HomeAccessory(
        hass,
        hk_driver,
        "Battery Service",
        entity_id,
        2,
        {CONF_LINKED_BATTERY_CHARGING_SENSOR: linked_battery_charging_sensor},
    )
    assert acc.linked_battery_charging_sensor is None


async def test_missing_linked_battery_sensor(hass, hk_driver, caplog):
    """Test battery service with missing linked_battery_sensor."""
    entity_id = "homekit.accessory"
    linked_battery = "sensor.battery"
    hass.states.async_set(entity_id, "open")
    await hass.async_block_till_done()

    acc = HomeAccessory(
        hass,
        hk_driver,
        "Battery Service",
        entity_id,
        2,
        {CONF_LINKED_BATTERY_SENSOR: linked_battery},
    )
    acc.update_state = lambda x: None
    assert not acc.linked_battery_sensor

    await acc.run_handler()
    await hass.async_block_till_done()

    assert not acc.linked_battery_sensor
    assert not hasattr(acc, "_char_battery")
    assert not hasattr(acc, "_char_low_battery")
    assert not hasattr(acc, "_char_charging")


async def test_call_service(hass, hk_driver, events):
    """Test call_service method."""
    entity_id = "homekit.accessory"
    hass.states.async_set(entity_id, None)
    await hass.async_block_till_done()

    acc = HomeAccessory(hass, hk_driver, "Home Accessory", entity_id, 2, None)
    call_service = async_mock_service(hass, "cover", "open_cover")

    test_domain = "cover"
    test_service = "open_cover"
    test_value = "value"

    await acc.async_call_service(
        test_domain, test_service, {ATTR_ENTITY_ID: entity_id}, test_value
    )
    await hass.async_block_till_done()

    assert len(events) == 1
    assert events[0].data == {
        ATTR_ENTITY_ID: acc.entity_id,
        ATTR_DISPLAY_NAME: acc.display_name,
        ATTR_SERVICE: test_service,
        ATTR_VALUE: test_value,
    }

    assert len(call_service) == 1
    assert call_service[0].domain == test_domain
    assert call_service[0].service == test_service
    assert call_service[0].data == {ATTR_ENTITY_ID: entity_id}


def test_home_bridge(hk_driver):
    """Test HomeBridge class."""
    bridge = HomeBridge("hass", hk_driver, BRIDGE_NAME)
    assert bridge.hass == "hass"
    assert bridge.display_name == BRIDGE_NAME
    assert bridge.category == 2  # Category.BRIDGE
    assert len(bridge.services) == 1
    serv = bridge.services[0]  # SERV_ACCESSORY_INFO
    assert serv.display_name == SERV_ACCESSORY_INFO
    assert serv.get_characteristic(CHAR_NAME).value == BRIDGE_NAME
    assert serv.get_characteristic(CHAR_FIRMWARE_REVISION).value == __version__
    assert serv.get_characteristic(CHAR_MANUFACTURER).value == MANUFACTURER
    assert serv.get_characteristic(CHAR_MODEL).value == BRIDGE_MODEL
    assert serv.get_characteristic(CHAR_SERIAL_NUMBER).value == BRIDGE_SERIAL_NUMBER

    bridge = HomeBridge("hass", hk_driver, "test_name")
    assert bridge.display_name == "test_name"
    assert len(bridge.services) == 1
    serv = bridge.services[0]  # SERV_ACCESSORY_INFO

    # setup_message
    bridge.setup_message()


def test_home_driver():
    """Test HomeDriver class."""
    ip_address = "127.0.0.1"
    port = 51826
    path = ".homekit.state"
    pin = b"123-45-678"

    with patch("pyhap.accessory_driver.AccessoryDriver.__init__") as mock_driver:
        driver = HomeDriver("hass", address=ip_address, port=port, persist_file=path)

    mock_driver.assert_called_with(address=ip_address, port=port, persist_file=path)
    driver.state = Mock(pincode=pin)
    xhm_uri_mock = Mock(return_value="X-HM://0")
    driver.accessory = Mock(xhm_uri=xhm_uri_mock)

    # pair
    with patch("pyhap.accessory_driver.AccessoryDriver.pair") as mock_pair, patch(
        "homeassistant.components.homekit.accessories.dismiss_setup_message"
    ) as mock_dissmiss_msg:
        driver.pair("client_uuid", "client_public")

    mock_pair.assert_called_with("client_uuid", "client_public")
    mock_dissmiss_msg.assert_called_with("hass")

    # unpair
    with patch("pyhap.accessory_driver.AccessoryDriver.unpair") as mock_unpair, patch(
        "homeassistant.components.homekit.accessories.show_setup_message"
    ) as mock_show_msg:
        driver.unpair("client_uuid")

    mock_unpair.assert_called_with("client_uuid")
    mock_show_msg.assert_called_with("hass", pin, "X-HM://0")
