"""Test all functions related to the basic accessory implementation.

This includes tests for all mock object types.
"""

from unittest.mock import Mock, patch

import pytest

from homeassistant.components.homekit.accessories import (
    HomeAccessory,
    HomeBridge,
    HomeDriver,
)
from homeassistant.components.homekit.const import (
    ATTR_DISPLAY_NAME,
    ATTR_INTEGRATION,
    ATTR_VALUE,
    BRIDGE_MODEL,
    BRIDGE_NAME,
    BRIDGE_SERIAL_NUMBER,
    CHAR_FIRMWARE_REVISION,
    CHAR_HARDWARE_REVISION,
    CHAR_MANUFACTURER,
    CHAR_MODEL,
    CHAR_NAME,
    CHAR_SERIAL_NUMBER,
    CONF_LINKED_BATTERY_CHARGING_SENSOR,
    CONF_LINKED_BATTERY_SENSOR,
    CONF_LOW_BATTERY_THRESHOLD,
    EMPTY_MAC,
    MANUFACTURER,
    SERV_ACCESSORY_INFO,
)
from homeassistant.components.homekit.util import format_version
from homeassistant.const import (
    ATTR_BATTERY_CHARGING,
    ATTR_BATTERY_LEVEL,
    ATTR_ENTITY_ID,
    ATTR_HW_VERSION,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_SERVICE,
    ATTR_SW_VERSION,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    __version__ as hass_version,
)
from homeassistant.core import Event, HomeAssistant

from tests.common import async_mock_service


async def test_accessory_cancels_track_state_change_on_stop(
    hass: HomeAssistant, hk_driver
) -> None:
    """Ensure homekit state changed listeners are unsubscribed on reload."""
    entity_id = "sensor.accessory"
    hass.states.async_set(entity_id, None)
    acc = HomeAccessory(
        hass, hk_driver, "Home Accessory", entity_id, 2, {"platform": "isy994"}
    )
    with patch(
        "homeassistant.components.homekit.accessories.HomeAccessory.async_update_state"
    ):
        acc.run()
    await acc.stop()


async def test_home_accessory(hass: HomeAssistant, hk_driver) -> None:
    """Test HomeAccessory class."""
    entity_id = "sensor.accessory"
    entity_id2 = "light.accessory_that_exceeds_the_maximum_maximum_maximum_maximum_maximum_maximum_maximum_allowed_length"

    hass.states.async_set(entity_id, None)
    hass.states.async_set(entity_id2, STATE_UNAVAILABLE)

    await hass.async_block_till_done()

    acc = HomeAccessory(
        hass, hk_driver, "Home Accessory", entity_id, 2, {"platform": "isy994"}
    )
    assert acc.hass == hass
    assert acc.display_name == "Home Accessory"
    assert acc.aid == 2
    assert acc.available is True
    assert acc.category == 1  # Category.OTHER
    assert len(acc.services) == 1
    serv = acc.services[0]  # SERV_ACCESSORY_INFO
    assert serv.display_name == SERV_ACCESSORY_INFO
    assert serv.get_characteristic(CHAR_NAME).value == "Home Accessory"
    assert serv.get_characteristic(CHAR_MANUFACTURER).value == "Isy994"
    assert serv.get_characteristic(CHAR_MODEL).value == "Sensor"
    assert serv.get_characteristic(CHAR_SERIAL_NUMBER).value == "sensor.accessory"

    acc2 = HomeAccessory(hass, hk_driver, "Home Accessory", entity_id2, 3, {})
    serv = acc2.services[0]  # SERV_ACCESSORY_INFO
    assert serv.get_characteristic(CHAR_NAME).value == "Home Accessory"
    assert serv.get_characteristic(CHAR_MANUFACTURER).value == f"{MANUFACTURER} Light"
    assert serv.get_characteristic(CHAR_MODEL).value == "Light"
    assert (
        serv.get_characteristic(CHAR_SERIAL_NUMBER).value
        == "light.accessory_that_exceeds_the_maximum_maximum_maximum_maximum"
    )

    acc3 = HomeAccessory(
        hass,
        hk_driver,
        "Home Accessory that exceeds the maximum maximum maximum maximum maximum maximum length",
        entity_id2,
        4,
        {
            ATTR_MODEL: "Awesome Model that exceeds the maximum maximum maximum maximum maximum maximum length",
            ATTR_MANUFACTURER: "Lux Brands that exceeds the maximum maximum maximum maximum maximum maximum length",
            ATTR_SW_VERSION: "0.4.3 that exceeds the maximum maximum maximum maximum maximum maximum length",
            ATTR_INTEGRATION: "luxe that exceeds the maximum maximum maximum maximum maximum maximum length",
        },
    )
    assert acc3.available is False
    serv = acc3.services[0]  # SERV_ACCESSORY_INFO
    assert (
        serv.get_characteristic(CHAR_NAME).value
        == "Home Accessory that exceeds the maximum maximum maximum maximum "
    )
    assert (
        serv.get_characteristic(CHAR_MANUFACTURER).value
        == "Lux Brands that exceeds the maximum maximum maximum maximum maxi"
    )
    assert (
        serv.get_characteristic(CHAR_MODEL).value
        == "Awesome Model that exceeds the maximum maximum maximum maximum m"
    )
    assert (
        serv.get_characteristic(CHAR_SERIAL_NUMBER).value
        == "light.accessory_that_exceeds_the_maximum_maximum_maximum_maximum"
    )
    assert serv.get_characteristic(CHAR_FIRMWARE_REVISION).value == "0.4.3"

    acc4 = HomeAccessory(
        hass,
        hk_driver,
        "Home Accessory that exceeds the maximum maximum maximum maximum maximum maximum length",
        entity_id2,
        5,
        {
            ATTR_MODEL: "Awesome Model that exceeds the maximum maximum maximum maximum maximum maximum length",
            ATTR_MANUFACTURER: "Lux Brands that exceeds the maximum maximum maximum maximum maximum maximum length",
            ATTR_SW_VERSION: "will_not_match_regex",
            ATTR_INTEGRATION: "luxe that exceeds the maximum maximum maximum maximum maximum maximum length",
        },
    )
    assert acc4.available is False
    serv = acc4.services[0]  # SERV_ACCESSORY_INFO
    assert (
        serv.get_characteristic(CHAR_NAME).value
        == "Home Accessory that exceeds the maximum maximum maximum maximum "
    )
    assert (
        serv.get_characteristic(CHAR_MANUFACTURER).value
        == "Lux Brands that exceeds the maximum maximum maximum maximum maxi"
    )
    assert (
        serv.get_characteristic(CHAR_MODEL).value
        == "Awesome Model that exceeds the maximum maximum maximum maximum m"
    )
    assert (
        serv.get_characteristic(CHAR_SERIAL_NUMBER).value
        == "light.accessory_that_exceeds_the_maximum_maximum_maximum_maximum"
    )
    assert format_version(hass_version).startswith(
        serv.get_characteristic(CHAR_FIRMWARE_REVISION).value
    )

    hass.states.async_set(entity_id, "on")
    await hass.async_block_till_done()
    with patch(
        "homeassistant.components.homekit.accessories.HomeAccessory.async_update_state"
    ) as mock_async_update_state:
        acc.run()
        await hass.async_block_till_done()
        state = hass.states.get(entity_id)
        mock_async_update_state.assert_called_with(state)

        hass.states.async_remove(entity_id)
        await hass.async_block_till_done()
        assert mock_async_update_state.call_count == 1

    with pytest.raises(NotImplementedError):
        acc.async_update_state("new_state")

    # Test model name from domain
    entity_id = "test_model.demo"
    hass.states.async_set(entity_id, None)
    await hass.async_block_till_done()
    acc = HomeAccessory(hass, hk_driver, "test_name", entity_id, 6, None)
    serv = acc.services[0]  # SERV_ACCESSORY_INFO
    assert serv.get_characteristic(CHAR_MODEL).value == "Test Model"


async def test_accessory_with_missing_basic_service_info(
    hass: HomeAssistant, hk_driver
) -> None:
    """Test HomeAccessory class."""
    entity_id = "sensor.accessory"
    hass.states.async_set(entity_id, "on")
    acc = HomeAccessory(
        hass,
        hk_driver,
        "Home Accessory",
        entity_id,
        3,
        {
            ATTR_MODEL: None,
            ATTR_MANUFACTURER: None,
            ATTR_SW_VERSION: None,
            ATTR_INTEGRATION: None,
        },
    )
    serv = acc.get_service(SERV_ACCESSORY_INFO)
    assert serv.get_characteristic(CHAR_NAME).value == "Home Accessory"
    assert serv.get_characteristic(CHAR_MANUFACTURER).value == "Home Assistant Sensor"
    assert serv.get_characteristic(CHAR_MODEL).value == "Sensor"
    assert serv.get_characteristic(CHAR_SERIAL_NUMBER).value == entity_id
    assert format_version(hass_version).startswith(
        serv.get_characteristic(CHAR_FIRMWARE_REVISION).value
    )
    assert isinstance(acc.to_HAP(), dict)


async def test_accessory_with_hardware_revision(hass: HomeAssistant, hk_driver) -> None:
    """Test HomeAccessory class with hardware revision."""
    entity_id = "sensor.accessory"
    hass.states.async_set(entity_id, "on")
    acc = HomeAccessory(
        hass,
        hk_driver,
        "Home Accessory",
        entity_id,
        3,
        {
            ATTR_MODEL: None,
            ATTR_MANUFACTURER: None,
            ATTR_SW_VERSION: None,
            ATTR_HW_VERSION: "1.2.3",
            ATTR_INTEGRATION: None,
        },
    )
    acc.driver = hk_driver
    serv = acc.get_service(SERV_ACCESSORY_INFO)
    assert serv.get_characteristic(CHAR_NAME).value == "Home Accessory"
    assert serv.get_characteristic(CHAR_MANUFACTURER).value == "Home Assistant Sensor"
    assert serv.get_characteristic(CHAR_MODEL).value == "Sensor"
    assert serv.get_characteristic(CHAR_SERIAL_NUMBER).value == entity_id
    assert format_version(hass_version).startswith(
        serv.get_characteristic(CHAR_FIRMWARE_REVISION).value
    )
    assert serv.get_characteristic(CHAR_HARDWARE_REVISION).value == "1.2.3"
    assert isinstance(acc.to_HAP(), dict)


async def test_battery_service(
    hass: HomeAssistant, hk_driver, caplog: pytest.LogCaptureFixture
) -> None:
    """Test battery service."""
    entity_id = "homekit.accessory"
    hass.states.async_set(entity_id, None, {ATTR_BATTERY_LEVEL: 50})
    await hass.async_block_till_done()

    acc = HomeAccessory(hass, hk_driver, "Battery Service", entity_id, 2, None)
    assert acc._char_battery.value == 0
    assert acc._char_low_battery.value == 0
    assert acc._char_charging.value == 2

    with patch(
        "homeassistant.components.homekit.accessories.HomeAccessory.async_update_state"
    ) as mock_async_update_state:
        acc.run()
        await hass.async_block_till_done()
        state = hass.states.get(entity_id)
        mock_async_update_state.assert_called_with(state)

    assert acc._char_battery.value == 50
    assert acc._char_low_battery.value == 0
    assert acc._char_charging.value == 2

    with patch(
        "homeassistant.components.homekit.accessories.HomeAccessory.async_update_state"
    ) as mock_async_update_state:
        hass.states.async_set(entity_id, None, {ATTR_BATTERY_LEVEL: 15})
        await hass.async_block_till_done()
        state = hass.states.get(entity_id)
        mock_async_update_state.assert_called_with(state)

    assert acc._char_battery.value == 15
    assert acc._char_low_battery.value == 1
    assert acc._char_charging.value == 2

    with patch(
        "homeassistant.components.homekit.accessories.HomeAccessory.async_update_state"
    ) as mock_async_update_state:
        hass.states.async_set(entity_id, None, {ATTR_BATTERY_LEVEL: "error"})
        await hass.async_block_till_done()
        state = hass.states.get(entity_id)
        mock_async_update_state.assert_called_with(state)

    assert acc._char_battery.value == 15
    assert acc._char_low_battery.value == 1
    assert acc._char_charging.value == 2
    assert "ERROR" not in caplog.text

    # Test charging
    with patch(
        "homeassistant.components.homekit.accessories.HomeAccessory.async_update_state"
    ) as mock_async_update_state:
        hass.states.async_set(
            entity_id, None, {ATTR_BATTERY_LEVEL: 10, ATTR_BATTERY_CHARGING: True}
        )
        await hass.async_block_till_done()
        state = hass.states.get(entity_id)
        mock_async_update_state.assert_called_with(state)

    with patch(
        "homeassistant.components.homekit.accessories.HomeAccessory.async_update_state"
    ):
        acc = HomeAccessory(hass, hk_driver, "Battery Service", entity_id, 3, None)
        assert acc._char_battery.value == 0
        assert acc._char_low_battery.value == 0
        assert acc._char_charging.value == 2

    with patch(
        "homeassistant.components.homekit.accessories.HomeAccessory.async_update_state"
    ) as mock_async_update_state:
        acc.run()
        await hass.async_block_till_done()
        state = hass.states.get(entity_id)
        mock_async_update_state.assert_called_with(state)
    assert acc._char_battery.value == 10
    assert acc._char_low_battery.value == 1
    assert acc._char_charging.value == 1

    with patch(
        "homeassistant.components.homekit.accessories.HomeAccessory.async_update_state"
    ):
        hass.states.async_set(
            entity_id, None, {ATTR_BATTERY_LEVEL: 100, ATTR_BATTERY_CHARGING: False}
        )
        await hass.async_block_till_done()
    assert acc._char_battery.value == 100
    assert acc._char_low_battery.value == 0
    assert acc._char_charging.value == 0


async def test_linked_battery_sensor(
    hass: HomeAssistant, hk_driver, caplog: pytest.LogCaptureFixture
) -> None:
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
    assert acc.linked_battery_sensor == linked_battery

    with patch(
        "homeassistant.components.homekit.accessories.HomeAccessory.async_update_state"
    ) as mock_async_update_state:
        acc.run()
        await hass.async_block_till_done()
        state = hass.states.get(entity_id)
        mock_async_update_state.assert_called_with(state)
    assert acc._char_battery.value == 50
    assert acc._char_low_battery.value == 0
    assert acc._char_charging.value == 2

    hass.states.async_set(linked_battery, 10, None)
    await hass.async_block_till_done()
    assert acc._char_battery.value == 10
    assert acc._char_low_battery.value == 1

    # Ignore battery change on entity if it has linked_battery
    with patch(
        "homeassistant.components.homekit.accessories.HomeAccessory.async_update_state"
    ):
        hass.states.async_set(entity_id, "open", {ATTR_BATTERY_LEVEL: 90})
        await hass.async_block_till_done()
    assert acc._char_battery.value == 10

    # Test none numeric state for linked_battery
    with patch(
        "homeassistant.components.homekit.accessories.HomeAccessory.async_update_state"
    ):
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
        3,
        {CONF_LINKED_BATTERY_SENSOR: linked_battery, CONF_LOW_BATTERY_THRESHOLD: 50},
    )
    with patch(
        "homeassistant.components.homekit.accessories.HomeAccessory.async_update_state"
    ) as mock_async_update_state:
        acc.run()
        await hass.async_block_till_done()
        state = hass.states.get(entity_id)
        mock_async_update_state.assert_called_with(state)
    assert acc._char_battery.value == 20
    assert acc._char_low_battery.value == 1
    assert acc._char_charging.value == 1

    hass.states.async_set(linked_battery, 100, {ATTR_BATTERY_CHARGING: False})
    await hass.async_block_till_done()
    assert acc._char_battery.value == 100
    assert acc._char_low_battery.value == 0
    assert acc._char_charging.value == 0

    hass.states.async_remove(linked_battery)
    await hass.async_block_till_done()
    assert acc._char_battery.value == 100
    assert acc._char_low_battery.value == 0
    assert acc._char_charging.value == 0


async def test_linked_battery_charging_sensor(
    hass: HomeAssistant, hk_driver, caplog: pytest.LogCaptureFixture
) -> None:
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
    assert acc.linked_battery_charging_sensor == linked_battery_charging_sensor

    with patch(
        "homeassistant.components.homekit.accessories.HomeAccessory.async_update_state"
    ) as mock_async_update_state:
        acc.run()
        await hass.async_block_till_done()
        state = hass.states.get(entity_id)
        mock_async_update_state.assert_called_with(state)
    assert acc._char_battery.value == 100
    assert acc._char_low_battery.value == 0
    assert acc._char_charging.value == 1

    with patch(
        "homeassistant.components.homekit.accessories.HomeAccessory.async_update_state"
    ) as mock_async_update_state:
        hass.states.async_set(linked_battery_charging_sensor, STATE_OFF, None)
        acc.run()
        await hass.async_block_till_done()
        state = hass.states.get(entity_id)
        mock_async_update_state.assert_called_with(state)
    assert acc._char_charging.value == 0

    with patch(
        "homeassistant.components.homekit.accessories.HomeAccessory.async_update_state"
    ) as mock_async_update_state:
        hass.states.async_set(linked_battery_charging_sensor, STATE_ON, None)
        acc.run()
        await hass.async_block_till_done()
        state = hass.states.get(entity_id)
        mock_async_update_state.assert_called_with(state)
    assert acc._char_charging.value == 1

    with patch(
        "homeassistant.components.homekit.accessories.HomeAccessory.async_update_state"
    ) as mock_async_update_state:
        hass.states.async_remove(linked_battery_charging_sensor)
        acc.run()
        await hass.async_block_till_done()
    assert acc._char_charging.value == 1


async def test_linked_battery_sensor_and_linked_battery_charging_sensor(
    hass: HomeAssistant, hk_driver, caplog: pytest.LogCaptureFixture
) -> None:
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
    assert acc.linked_battery_sensor == linked_battery

    with patch(
        "homeassistant.components.homekit.accessories.HomeAccessory.async_update_state"
    ) as mock_async_update_state:
        acc.run()
        await hass.async_block_till_done()
        state = hass.states.get(entity_id)
        mock_async_update_state.assert_called_with(state)
    assert acc._char_battery.value == 50
    assert acc._char_low_battery.value == 0
    assert acc._char_charging.value == 1

    hass.states.async_set(linked_battery_charging_sensor, STATE_OFF, None)
    await hass.async_block_till_done()
    assert acc._char_battery.value == 50
    assert acc._char_low_battery.value == 0
    assert acc._char_charging.value == 0

    hass.states.async_remove(linked_battery_charging_sensor)
    await hass.async_block_till_done()
    assert acc._char_battery.value == 50
    assert acc._char_low_battery.value == 0
    assert acc._char_charging.value == 0


async def test_missing_linked_battery_charging_sensor(
    hass: HomeAssistant, hk_driver, caplog: pytest.LogCaptureFixture
) -> None:
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

    # Make sure we don't throw if the linked_battery_charging_sensor
    # is removed
    hass.states.async_remove(linked_battery_charging_sensor)
    with patch(
        "homeassistant.components.homekit.accessories.HomeAccessory.async_update_state"
    ):
        acc.run()
        await hass.async_block_till_done()

    # Make sure we don't throw if the entity_id
    # is removed
    hass.states.async_remove(entity_id)
    with patch(
        "homeassistant.components.homekit.accessories.HomeAccessory.async_update_state"
    ):
        acc.run()
        await hass.async_block_till_done()


async def test_missing_linked_battery_sensor(
    hass: HomeAssistant, hk_driver, caplog: pytest.LogCaptureFixture
) -> None:
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
    assert not acc.linked_battery_sensor

    with patch(
        "homeassistant.components.homekit.accessories.HomeAccessory.async_update_state"
    ) as mock_async_update_state:
        acc.run()
        await hass.async_block_till_done()
        state = hass.states.get(entity_id)
        mock_async_update_state.assert_called_with(state)

    assert not acc.linked_battery_sensor
    assert acc._char_battery is None
    assert acc._char_low_battery is None
    assert acc._char_charging is None

    with patch(
        "homeassistant.components.homekit.accessories.HomeAccessory.async_update_state"
    ) as mock_async_update_state:
        hass.states.async_remove(entity_id)
        acc.run()
        await hass.async_block_till_done()

    assert not acc.linked_battery_sensor
    assert acc._char_battery is None
    assert acc._char_low_battery is None
    assert acc._char_charging is None


async def test_battery_appears_after_startup(
    hass: HomeAssistant, hk_driver, caplog: pytest.LogCaptureFixture
) -> None:
    """Test battery level appears after homekit is started."""
    entity_id = "homekit.accessory"
    hass.states.async_set(entity_id, None, {})
    await hass.async_block_till_done()

    acc = HomeAccessory(hass, hk_driver, "Accessory without battery", entity_id, 2, {})
    assert acc._char_battery is None

    with patch(
        "homeassistant.components.homekit.accessories.HomeAccessory.async_update_state"
    ) as mock_async_update_state:
        acc.run()
        await hass.async_block_till_done()
        state = hass.states.get(entity_id)
        mock_async_update_state.assert_called_with(state)
    assert acc._char_battery is None

    with patch(
        "homeassistant.components.homekit.accessories.HomeAccessory.async_update_state"
    ):
        hass.states.async_set(entity_id, None, {ATTR_BATTERY_LEVEL: 15})
        await hass.async_block_till_done()
    assert acc._char_battery is None

    with patch(
        "homeassistant.components.homekit.accessories.HomeAccessory.async_update_state"
    ):
        hass.states.async_remove(entity_id)
        await hass.async_block_till_done()
    assert acc._char_battery is None


async def test_call_service(
    hass: HomeAssistant, hk_driver, events: list[Event]
) -> None:
    """Test call_service method."""
    entity_id = "homekit.accessory"
    hass.states.async_set(entity_id, None)
    await hass.async_block_till_done()

    acc = HomeAccessory(hass, hk_driver, "Home Accessory", entity_id, 2, {})
    call_service = async_mock_service(hass, "cover", "open_cover")

    test_domain = "cover"
    test_service = "open_cover"
    test_value = "value"

    acc.async_call_service(
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


def test_home_bridge(hk_driver) -> None:
    """Test HomeBridge class."""
    bridge = HomeBridge("hass", hk_driver, BRIDGE_NAME)
    assert bridge.hass == "hass"
    assert bridge.display_name == BRIDGE_NAME
    assert bridge.category == 2  # Category.BRIDGE
    assert len(bridge.services) == 2
    serv = bridge.services[0]  # SERV_ACCESSORY_INFO
    assert serv.display_name == SERV_ACCESSORY_INFO
    assert serv.get_characteristic(CHAR_NAME).value == BRIDGE_NAME
    assert format_version(hass_version).startswith(
        serv.get_characteristic(CHAR_FIRMWARE_REVISION).value
    )
    assert serv.get_characteristic(CHAR_MANUFACTURER).value == MANUFACTURER
    assert serv.get_characteristic(CHAR_MODEL).value == BRIDGE_MODEL
    assert serv.get_characteristic(CHAR_SERIAL_NUMBER).value == BRIDGE_SERIAL_NUMBER


def test_home_bridge_setup_message(hk_driver) -> None:
    """Test HomeBridge setup message."""
    bridge = HomeBridge("hass", hk_driver, "test_name")
    assert bridge.display_name == "test_name"
    assert len(bridge.services) == 2
    # setup_message
    bridge.setup_message()


def test_home_driver(iid_storage) -> None:
    """Test HomeDriver class."""
    ip_address = "127.0.0.1"
    port = 51826
    path = ".homekit.state"
    pin = b"123-45-678"

    with patch("pyhap.accessory_driver.AccessoryDriver.__init__") as mock_driver:
        driver = HomeDriver(
            "hass",
            "entry_id",
            "name",
            "title",
            iid_storage=iid_storage,
            address=ip_address,
            port=port,
            persist_file=path,
        )

    mock_driver.assert_called_with(
        address=ip_address, port=port, persist_file=path, mac=EMPTY_MAC
    )
    driver.state = Mock(pincode=pin, paired=False)
    xhm_uri_mock = Mock(return_value="X-HM://0")
    driver.accessory = Mock(display_name="any", xhm_uri=xhm_uri_mock)

    # pair
    with (
        patch("pyhap.accessory_driver.AccessoryDriver.pair") as mock_pair,
        patch(
            "homeassistant.components.homekit.accessories.async_dismiss_setup_message"
        ) as mock_dissmiss_msg,
    ):
        driver.pair("client_uuid", "client_public", b"1")

    mock_pair.assert_called_with("client_uuid", "client_public", b"1")
    mock_dissmiss_msg.assert_called_with("hass", "entry_id")

    # unpair
    with (
        patch("pyhap.accessory_driver.AccessoryDriver.unpair") as mock_unpair,
        patch(
            "homeassistant.components.homekit.accessories.async_show_setup_message"
        ) as mock_show_msg,
    ):
        driver.unpair("client_uuid")

    mock_unpair.assert_called_with("client_uuid")
    mock_show_msg.assert_called_with("hass", "entry_id", "title (any)", pin, "X-HM://0")
