"""Test the Litter-Robot binary sensor entity."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorDeviceClass,
)
from homeassistant.const import ATTR_DEVICE_CLASS
from homeassistant.core import HomeAssistant

from .conftest import setup_integration


@pytest.mark.freeze_time("2022-09-18 23:00:44+00:00")
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_binary_sensors(
    hass: HomeAssistant,
    mock_account: MagicMock,
) -> None:
    """Tests binary sensors."""
    await setup_integration(hass, mock_account, BINARY_SENSOR_DOMAIN)

    state = hass.states.get("binary_sensor.test_sleeping")
    assert state.state == "off"
    state = hass.states.get("binary_sensor.test_sleep_mode")
    assert state.state == "on"
    state = hass.states.get("binary_sensor.test_power_status")
    assert state.attributes.get(ATTR_DEVICE_CLASS) == BinarySensorDeviceClass.PLUG
    assert state.state == "on"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_litterhopper_binary_sensors(
    hass: HomeAssistant,
    mock_account_with_litterhopper: MagicMock,
) -> None:
    """Tests LitterHopper-specific binary sensors."""
    await setup_integration(hass, mock_account_with_litterhopper, BINARY_SENSOR_DOMAIN)

    state = hass.states.get("binary_sensor.test_hopper_connected")
    assert state.state == "on"
    assert (
        state.attributes.get(ATTR_DEVICE_CLASS) == BinarySensorDeviceClass.CONNECTIVITY
    )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_litter_robot_5_binary_sensors(
    hass: HomeAssistant,
    mock_account_with_litterrobot_5: MagicMock,
) -> None:
    """Tests Litter-Robot 5 binary sensors."""
    await setup_integration(hass, mock_account_with_litterrobot_5, BINARY_SENSOR_DOMAIN)

    state = hass.states.get("binary_sensor.test_drawer_removed")
    assert state
    assert state.state == "off"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == BinarySensorDeviceClass.PROBLEM

    state = hass.states.get("binary_sensor.test_bonnet_removed")
    assert state
    assert state.state == "off"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == BinarySensorDeviceClass.PROBLEM

    state = hass.states.get("binary_sensor.test_laser_dirty")
    assert state
    assert state.state == "off"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == BinarySensorDeviceClass.PROBLEM

    state = hass.states.get("binary_sensor.test_hopper_connected")
    assert state
    assert state.state == "on"
    assert (
        state.attributes.get(ATTR_DEVICE_CLASS) == BinarySensorDeviceClass.CONNECTIVITY
    )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_litter_robot_5_online_sensor(
    hass: HomeAssistant,
    mock_account_with_litterrobot_5: MagicMock,
) -> None:
    """Tests Litter-Robot 5 online binary sensor (diagnostic, disabled by default)."""
    await setup_integration(hass, mock_account_with_litterrobot_5, BINARY_SENSOR_DOMAIN)

    state = hass.states.get("binary_sensor.test_online")
    assert state
    assert state.state == "on"
    assert (
        state.attributes.get(ATTR_DEVICE_CLASS) == BinarySensorDeviceClass.CONNECTIVITY
    )
