"""Tests for the Freebox binary sensors."""
from copy import deepcopy
from unittest.mock import Mock

from freezegun.api import FrozenDateTimeFactory

from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorDeviceClass,
)
from homeassistant.components.freebox import SCAN_INTERVAL
from homeassistant.const import ATTR_DEVICE_CLASS
from homeassistant.core import HomeAssistant

from .common import setup_platform
from .const import DATA_HOME_PIR_GET_VALUE, DATA_STORAGE_GET_RAIDS

from tests.common import async_fire_time_changed


async def test_raid_array_degraded(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, router: Mock
) -> None:
    """Test raid array degraded binary sensor."""
    await setup_platform(hass, BINARY_SENSOR_DOMAIN)

    assert (
        hass.states.get("binary_sensor.freebox_server_r2_raid_array_0_degraded").state
        == "off"
    )

    # Now simulate we degraded
    data_storage_get_raids_degraded = deepcopy(DATA_STORAGE_GET_RAIDS)
    data_storage_get_raids_degraded[0]["degraded"] = True
    router().storage.get_raids.return_value = data_storage_get_raids_degraded
    # Simulate an update
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    # To execute the save
    await hass.async_block_till_done()
    assert (
        hass.states.get("binary_sensor.freebox_server_r2_raid_array_0_degraded").state
        == "on"
    )


async def test_home(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, router: Mock
) -> None:
    """Test home binary sensors."""
    await setup_platform(hass, BINARY_SENSOR_DOMAIN)

    # Device class
    assert (
        hass.states.get("binary_sensor.detecteur").attributes[ATTR_DEVICE_CLASS]
        == BinarySensorDeviceClass.MOTION
    )
    assert (
        hass.states.get("binary_sensor.ouverture_porte").attributes[ATTR_DEVICE_CLASS]
        == BinarySensorDeviceClass.DOOR
    )
    assert (
        hass.states.get("binary_sensor.ouverture_porte_couvercle").attributes[
            ATTR_DEVICE_CLASS
        ]
        == BinarySensorDeviceClass.SAFETY
    )

    # Initial state
    assert hass.states.get("binary_sensor.detecteur").state == "on"
    assert hass.states.get("binary_sensor.detecteur_couvercle").state == "off"
    assert hass.states.get("binary_sensor.ouverture_porte").state == "unknown"
    assert hass.states.get("binary_sensor.ouverture_porte_couvercle").state == "off"

    # Now simulate a changed status
    data_home_get_values_changed = deepcopy(DATA_HOME_PIR_GET_VALUE)
    data_home_get_values_changed["value"] = True
    router().home.get_home_endpoint_value.return_value = data_home_get_values_changed

    # Simulate an update
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.detecteur").state == "off"
    assert hass.states.get("binary_sensor.detecteur_couvercle").state == "on"
    assert hass.states.get("binary_sensor.ouverture_porte").state == "off"
    assert hass.states.get("binary_sensor.ouverture_porte_couvercle").state == "on"
