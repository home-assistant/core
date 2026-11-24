"""Tests for Broadlink fans."""

from datetime import timedelta
from unittest.mock import call

import broadlink_async as blk
from freezegun.api import FrozenDateTimeFactory
from pytest_homeassistant.common import async_fire_time_changed

from homeassistant.components.broadlink.const import DOMAIN
from homeassistant.components.broadlink.updater import BroadlinkLIFAAIRUpdateManager
from homeassistant.components.fan import (
    ATTR_PERCENTAGE,
    ATTR_PRESET_MODE,
    DOMAIN as FAN_DOMAIN,
    FanService,
    FanServiceArgument,
)
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
    TargetKey,
    UnitOfDensity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import get_device

FAN_ENTITY_ID = "fan.air_purifier"
PURIFIER_ONLINE_ENTITY_ID = "binary_sensor.air_purifier_purifier_online"
TEMPERATURE_ENTITY_ID = "sensor.air_purifier_temperature"
HUMIDITY_ENTITY_ID = "sensor.air_purifier_humidity"
FORMALDEHYDE_ENTITY_ID = "sensor.air_purifier_formaldehyde"
TVOC_ENTITY_ID = "sensor.air_purifier_volatile_organic_compounds"
CO2_ENTITY_ID = "sensor.air_purifier_carbon_dioxide"


async def test_lifaair_fan_setup(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test setting up a LIFAair fan."""
    device = get_device("Air purifier")
    mock_api = device.get_mock_api()
    mock_api.get_state.return_value = {
        "co2": 425,
        "fan_mode": blk.lifaair.FanMode.AUTO,
        "fan_speed": 50,
        "formaldehyde": 0.03,
        "humidity": 41,
        "pm1": 5,
        "pm2_5": 7,
        "pm10": 9,
        "purifier_online": True,
        "temperature": 24.5,
        "tvoc": 150,
    }

    mock_setup = await device.setup_entry(hass, mock_api=mock_api)

    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, mock_setup.entry.unique_id), mock_setup.entry.entry_id
    )
    assert device_entry is not None
    assert device_entry.model == "LM05"
    assert device_entry.manufacturer == "LIFAair"

    fan_state = hass.states.get(FAN_ENTITY_ID)
    assert fan_state is not None
    assert fan_state.state == STATE_ON
    assert fan_state.attributes[ATTR_PRESET_MODE] == "auto"
    assert fan_state.attributes[ATTR_PERCENTAGE] == 41

    formaldehyde_state = hass.states.get(FORMALDEHYDE_ENTITY_ID)
    assert formaldehyde_state is not None
    assert formaldehyde_state.state == "0.03"
    assert ATTR_DEVICE_CLASS not in formaldehyde_state.attributes
    assert (
        formaldehyde_state.attributes[ATTR_UNIT_OF_MEASUREMENT]
        == UnitOfDensity.MILLIGRAMS_PER_CUBIC_METER
    )
    tvoc_state = hass.states.get(TVOC_ENTITY_ID)
    assert tvoc_state is not None
    assert tvoc_state.state == "150"
    assert (
        tvoc_state.attributes[ATTR_DEVICE_CLASS]
        == SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS
    )
    co2_state = hass.states.get(CO2_ENTITY_ID)
    assert co2_state is not None
    assert co2_state.state == "425"
    online_state = hass.states.get(PURIFIER_ONLINE_ENTITY_ID)
    assert online_state is not None
    assert online_state.state == STATE_ON


async def test_lifaair_purifier_offline(hass: HomeAssistant) -> None:
    """Test the purifier offline state is exposed separately from the station."""
    device = get_device("Air purifier")
    mock_api = device.get_mock_api()
    mock_api.get_state.return_value = {
        "fan_mode": None,
        "fan_speed": None,
        "temperature": None,
        "humidity": None,
        "purifier_online": False,
    }

    await device.setup_entry(hass, mock_api=mock_api)

    fan_state = hass.states.get(FAN_ENTITY_ID)
    assert fan_state is not None
    assert fan_state.state == STATE_UNAVAILABLE
    online_state = hass.states.get(PURIFIER_ONLINE_ENTITY_ID)
    assert online_state is not None
    assert online_state.state == STATE_OFF
    sensor_states = hass.states.async_all(Platform.SENSOR)
    assert len(sensor_states) == 2
    assert {state.entity_id for state in sensor_states} == {
        TEMPERATURE_ENTITY_ID,
        HUMIDITY_ENTITY_ID,
    }
    assert {state.state for state in sensor_states} == {STATE_UNAVAILABLE}


async def test_lifaair_climate_sensors_unknown_when_online_without_readings(
    hass: HomeAssistant,
) -> None:
    """Test missing climate readings are unknown while the purifier is online."""
    device = get_device("Air purifier")
    mock_api = device.get_mock_api()
    mock_api.get_state.return_value = {
        "fan_mode": blk.lifaair.FanMode.AUTO,
        "fan_speed": 30,
        "temperature": None,
        "humidity": None,
        "purifier_online": True,
    }

    await device.setup_entry(hass, mock_api=mock_api)

    sensor_states = hass.states.async_all(Platform.SENSOR)
    assert len(sensor_states) == 2
    assert {state.entity_id for state in sensor_states} == {
        TEMPERATURE_ENTITY_ID,
        HUMIDITY_ENTITY_ID,
    }
    assert {state.state for state in sensor_states} == {STATE_UNKNOWN}


async def test_lifaair_scan_interval(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test the purifier is polled on the same interval as the A1 and A2 sensors."""
    device = get_device("Air purifier")
    mock_api = device.get_mock_api()
    mock_api.get_state.return_value = {
        "fan_mode": blk.lifaair.FanMode.AUTO,
        "fan_speed": 30,
        "purifier_online": True,
    }
    await device.setup_entry(hass, mock_api=mock_api)
    assert mock_api.get_state.call_count == 1

    freezer.tick(BroadlinkLIFAAIRUpdateManager.SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert timedelta(seconds=10) == BroadlinkLIFAAIRUpdateManager.SCAN_INTERVAL
    assert mock_api.get_state.call_count == 2


async def test_lifaair_fan_turn_on_off(hass: HomeAssistant) -> None:
    """Test that the fan exposes working turn on and turn off services."""
    device = get_device("Air purifier")
    mock_api = device.get_mock_api()
    fan_mode = blk.lifaair.FanMode
    mock_api.get_state.return_value = {
        "fan_mode": fan_mode.OFF,
        "fan_speed": 50,
        "purifier_online": True,
    }
    mock_api.set_fan_mode.side_effect = [
        {"fan_mode": fan_mode.AUTO, "fan_speed": 30, "purifier_online": True},
        {"fan_mode": fan_mode.OFF, "fan_speed": 30, "purifier_online": True},
    ]

    await device.setup_entry(hass, mock_api=mock_api)

    await hass.services.async_call(
        FAN_DOMAIN,
        FanService.TURN_ON,
        {TargetKey.ENTITY_ID: FAN_ENTITY_ID},
        blocking=True,
    )
    fan_state = hass.states.get(FAN_ENTITY_ID)
    assert fan_state is not None
    assert fan_state.state == STATE_ON

    await hass.services.async_call(
        FAN_DOMAIN,
        FanService.TURN_OFF,
        {TargetKey.ENTITY_ID: FAN_ENTITY_ID},
        blocking=True,
    )

    assert mock_api.set_fan_mode.await_args_list == [
        call(fan_mode.AUTO),
        call(fan_mode.OFF),
    ]
    fan_state = hass.states.get(FAN_ENTITY_ID)
    assert fan_state is not None
    assert fan_state.state == STATE_OFF


async def test_lifaair_fan_preset_from_off(hass: HomeAssistant) -> None:
    """Test setting a preset from off starts the fan before changing its mode."""
    device = get_device("Air purifier")
    mock_api = device.get_mock_api()
    fan_mode = blk.lifaair.FanMode
    mock_api.get_state.return_value = {
        "fan_mode": fan_mode.OFF,
        "fan_speed": 50,
        "purifier_online": True,
    }
    mock_api.set_fan_mode.return_value = {
        "fan_mode": fan_mode.NIGHT,
        "fan_speed": 10,
        "purifier_online": True,
    }

    await device.setup_entry(hass, mock_api=mock_api)

    fan_state = hass.states.get(FAN_ENTITY_ID)
    assert fan_state is not None
    assert fan_state.state == STATE_OFF

    await hass.services.async_call(
        FAN_DOMAIN,
        FanService.SET_PRESET_MODE,
        {
            TargetKey.ENTITY_ID: FAN_ENTITY_ID,
            FanServiceArgument.PRESET_MODE: "night",
        },
        blocking=True,
    )

    assert mock_api.set_fan_mode.await_args_list == [
        call(fan_mode.AUTO),
        call(fan_mode.NIGHT),
    ]
    fan_state = hass.states.get(FAN_ENTITY_ID)
    assert fan_state is not None
    assert fan_state.state == STATE_ON


async def test_lifaair_manual_preset_sets_speed(hass: HomeAssistant) -> None:
    """Test the API's manual mode is entered through its speed setter."""
    device = get_device("Air purifier")
    mock_api = device.get_mock_api()
    fan_mode = blk.lifaair.FanMode
    mock_api.get_state.return_value = {
        "fan_mode": fan_mode.AUTO,
        "fan_speed": 60,
        "purifier_online": True,
    }
    mock_api.set_fan_speed.return_value = {
        "fan_mode": fan_mode.MANUAL,
        "fan_speed": 60,
        "purifier_online": True,
    }

    await device.setup_entry(hass, mock_api=mock_api)

    await hass.services.async_call(
        FAN_DOMAIN,
        FanService.SET_PRESET_MODE,
        {
            TargetKey.ENTITY_ID: FAN_ENTITY_ID,
            FanServiceArgument.PRESET_MODE: "manual",
        },
        blocking=True,
    )

    mock_api.set_fan_speed.assert_awaited_once_with(60)
    mock_api.set_fan_mode.assert_not_awaited()


async def test_lifaair_manual_preset_with_zero_auto_speed(hass: HomeAssistant) -> None:
    """Test selecting manual while auto is stopped uses the fallback speed."""
    device = get_device("Air purifier")
    mock_api = device.get_mock_api()
    fan_mode = blk.lifaair.FanMode
    mock_api.get_state.return_value = {
        "fan_mode": fan_mode.AUTO,
        "fan_speed": 0,
        "purifier_online": True,
    }
    mock_api.set_fan_speed.return_value = {
        "fan_mode": fan_mode.MANUAL,
        "fan_speed": 60,
        "purifier_online": True,
    }

    await device.setup_entry(hass, mock_api=mock_api)

    await hass.services.async_call(
        FAN_DOMAIN,
        FanService.SET_PRESET_MODE,
        {
            TargetKey.ENTITY_ID: FAN_ENTITY_ID,
            FanServiceArgument.PRESET_MODE: "manual",
        },
        blocking=True,
    )

    mock_api.set_fan_speed.assert_awaited_once_with(60)
    mock_api.set_fan_mode.assert_not_awaited()


async def test_lifaair_zero_percentage_turns_off(hass: HomeAssistant) -> None:
    """Test zero percent uses OFF mode instead of setting a manual speed."""
    device = get_device("Air purifier")
    mock_api = device.get_mock_api()
    fan_mode = blk.lifaair.FanMode
    mock_api.get_state.return_value = {
        "fan_mode": fan_mode.AUTO,
        "fan_speed": 60,
        "purifier_online": True,
    }
    mock_api.set_fan_mode.return_value = {
        "fan_mode": fan_mode.OFF,
        "fan_speed": 60,
        "purifier_online": True,
    }

    await device.setup_entry(hass, mock_api=mock_api)

    await hass.services.async_call(
        FAN_DOMAIN,
        FanService.SET_PERCENTAGE,
        {TargetKey.ENTITY_ID: FAN_ENTITY_ID, FanServiceArgument.PERCENTAGE: 0},
        blocking=True,
    )

    mock_api.set_fan_mode.assert_awaited_once_with(fan_mode.OFF)
    mock_api.set_fan_speed.assert_not_awaited()
    fan_state = hass.states.get(FAN_ENTITY_ID)
    assert fan_state is not None
    assert fan_state.state == STATE_OFF
