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
    ATTR_PRESET_MODES,
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

FAN_ENTITY_ID = "fan.nursery"
PURIFIER_ONLINE_ENTITY_ID = "binary_sensor.nursery_purifier_online"
TEMPERATURE_ENTITY_ID = "sensor.nursery_temperature"
HUMIDITY_ENTITY_ID = "sensor.nursery_humidity"
FORMALDEHYDE_ENTITY_ID = "sensor.nursery_formaldehyde"
TVOC_ENTITY_ID = "sensor.nursery_volatile_organic_compounds"
CO2_ENTITY_ID = "sensor.nursery_carbon_dioxide"


async def test_lifaair_fan_setup(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test setting up a LIFAair fan."""
    device = get_device("Nursery")
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
    assert fan_state.attributes[ATTR_PRESET_MODES] == [
        "auto",
        "night",
        "turbo",
        "anti_allergy",
    ]

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
    device = get_device("Nursery")
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
    device = get_device("Nursery")
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
    device = get_device("Nursery")
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


async def test_lifaair_fan_unknown_mode(hass: HomeAssistant) -> None:
    """Test an unknown fan mode is not reported as a preset."""
    device = get_device("Nursery")
    mock_api = device.get_mock_api()
    mock_api.get_state.return_value = {
        "fan_mode": blk.lifaair.FanMode.UNKNOWN,
        "fan_speed": 60,
        "purifier_online": True,
    }

    await device.setup_entry(hass, mock_api=mock_api)

    fan_state = hass.states.get(FAN_ENTITY_ID)
    assert fan_state is not None
    assert fan_state.state == STATE_ON
    assert fan_state.attributes[ATTR_PRESET_MODE] is None
    assert fan_state.attributes[ATTR_PERCENTAGE] == 50


async def test_lifaair_fan_turn_on_off(hass: HomeAssistant) -> None:
    """Test that the fan exposes working turn on and turn off services."""
    device = get_device("Nursery")
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

    fan_state = hass.states.get(FAN_ENTITY_ID)
    assert fan_state is not None
    assert fan_state.state == STATE_OFF
    assert fan_state.attributes[ATTR_PRESET_MODE] is None
    assert fan_state.attributes[ATTR_PERCENTAGE] == 0

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
    assert fan_state.attributes[ATTR_PRESET_MODE] is None
    assert fan_state.attributes[ATTR_PERCENTAGE] == 0


async def test_lifaair_fan_preset_from_off(hass: HomeAssistant) -> None:
    """Test setting a preset from off starts the fan before changing its mode."""
    device = get_device("Nursery")
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
    assert fan_state.attributes[ATTR_PRESET_MODE] is None
    assert fan_state.attributes[ATTR_PERCENTAGE] == 0

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


async def test_lifaair_fan_set_percentage(hass: HomeAssistant) -> None:
    """Test setting the fan speed enters manual mode."""
    device = get_device("Nursery")
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
        FanService.SET_PERCENTAGE,
        {TargetKey.ENTITY_ID: FAN_ENTITY_ID, FanServiceArgument.PERCENTAGE: 50},
        blocking=True,
    )

    mock_api.set_fan_speed.assert_awaited_once_with(60)
    mock_api.set_fan_mode.assert_not_awaited()
    fan_state = hass.states.get(FAN_ENTITY_ID)
    assert fan_state is not None
    assert fan_state.state == STATE_ON
    assert fan_state.attributes[ATTR_PRESET_MODE] is None
    assert fan_state.attributes[ATTR_PERCENTAGE] == 50


async def test_lifaair_fan_preset_from_manual(hass: HomeAssistant) -> None:
    """Test setting a preset from manual speed does not turn the fan on first."""
    device = get_device("Nursery")
    mock_api = device.get_mock_api()
    fan_mode = blk.lifaair.FanMode
    mock_api.get_state.return_value = {
        "fan_mode": fan_mode.MANUAL,
        "fan_speed": 60,
        "purifier_online": True,
    }
    mock_api.set_fan_mode.return_value = {
        "fan_mode": fan_mode.NIGHT,
        "fan_speed": 10,
        "purifier_online": True,
    }

    await device.setup_entry(hass, mock_api=mock_api)

    await hass.services.async_call(
        FAN_DOMAIN,
        FanService.SET_PRESET_MODE,
        {
            TargetKey.ENTITY_ID: FAN_ENTITY_ID,
            FanServiceArgument.PRESET_MODE: "night",
        },
        blocking=True,
    )

    mock_api.set_fan_mode.assert_awaited_once_with(fan_mode.NIGHT)
    fan_state = hass.states.get(FAN_ENTITY_ID)
    assert fan_state is not None
    assert fan_state.state == STATE_ON
    assert fan_state.attributes[ATTR_PRESET_MODE] == "night"


async def test_lifaair_fan_set_percentage_zero(hass: HomeAssistant) -> None:
    """Test setting the fan speed to zero turns the fan off."""
    device = get_device("Nursery")
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
    assert fan_state.attributes[ATTR_PRESET_MODE] is None
    assert fan_state.attributes[ATTR_PERCENTAGE] == 0
