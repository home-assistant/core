"""
Test for Nest climate platform for the Smart Device Management API.

These tests fake out the subscriber/devicemanager, and are not using a real
pubsub subscriber.
"""

from google_nest_sdm.device import Device
from google_nest_sdm.event import EventMessage
import pytest

from homeassistant.components.climate.const import (
    ATTR_CURRENT_TEMPERATURE,
    ATTR_FAN_MODE,
    ATTR_FAN_MODES,
    ATTR_HVAC_ACTION,
    ATTR_HVAC_MODES,
    ATTR_PRESET_MODE,
    ATTR_PRESET_MODES,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    CURRENT_HVAC_COOL,
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_OFF,
    FAN_LOW,
    FAN_OFF,
    FAN_ON,
    HVAC_MODE_COOL,
    HVAC_MODE_DRY,
    HVAC_MODE_FAN_ONLY,
    HVAC_MODE_HEAT,
    HVAC_MODE_HEAT_COOL,
    HVAC_MODE_OFF,
    PRESET_ECO,
    PRESET_NONE,
    PRESET_SLEEP,
)
from homeassistant.const import ATTR_TEMPERATURE

from .common import async_setup_sdm_platform

from tests.components.climate import common

PLATFORM = "climate"


async def setup_climate(hass, raw_traits=None, auth=None):
    """Load Nest climate devices."""
    devices = None
    if raw_traits:
        traits = raw_traits
        traits["sdm.devices.traits.Info"] = {"customName": "My Thermostat"}
        devices = {
            "some-device-id": Device.MakeDevice(
                {
                    "name": "some-device-id",
                    "type": "sdm.devices.types.Thermostat",
                    "traits": traits,
                },
                auth=auth,
            ),
        }
    return await async_setup_sdm_platform(hass, PLATFORM, devices)


async def test_no_devices(hass):
    """Test no devices returned by the api."""
    await setup_climate(hass)
    assert len(hass.states.async_all()) == 0


async def test_climate_devices(hass):
    """Test no eligible climate devices returned by the api."""
    await setup_climate(hass, {"sdm.devices.traits.CameraImage": {}})
    assert len(hass.states.async_all()) == 0


async def test_thermostat_off(hass):
    """Test a thermostat that is not running."""
    await setup_climate(
        hass,
        {
            "sdm.devices.traits.ThermostatHvac": {"status": "OFF"},
            "sdm.devices.traits.ThermostatMode": {
                "availableModes": ["HEAT", "COOL", "HEATCOOL", "OFF"],
                "mode": "OFF",
            },
            "sdm.devices.traits.Temperature": {
                "ambientTemperatureCelsius": 16.2,
            },
        },
    )

    assert len(hass.states.async_all()) == 1
    thermostat = hass.states.get("climate.my_thermostat")
    assert thermostat is not None
    assert thermostat.state == HVAC_MODE_OFF
    assert thermostat.attributes[ATTR_HVAC_ACTION] == CURRENT_HVAC_OFF
    assert thermostat.attributes[ATTR_CURRENT_TEMPERATURE] == 16.2
    assert set(thermostat.attributes[ATTR_HVAC_MODES]) == {
        HVAC_MODE_HEAT,
        HVAC_MODE_COOL,
        HVAC_MODE_HEAT_COOL,
        HVAC_MODE_OFF,
    }
    assert thermostat.attributes[ATTR_TEMPERATURE] is None
    assert thermostat.attributes[ATTR_TARGET_TEMP_LOW] is None
    assert thermostat.attributes[ATTR_TARGET_TEMP_HIGH] is None
    assert ATTR_PRESET_MODE not in thermostat.attributes
    assert ATTR_PRESET_MODES not in thermostat.attributes
    assert ATTR_FAN_MODE not in thermostat.attributes
    assert ATTR_FAN_MODES not in thermostat.attributes


async def test_thermostat_heat(hass):
    """Test a thermostat that is heating."""
    await setup_climate(
        hass,
        {
            "sdm.devices.traits.ThermostatHvac": {
                "status": "HEATING",
            },
            "sdm.devices.traits.ThermostatMode": {
                "availableModes": ["HEAT", "COOL", "HEATCOOL", "OFF"],
                "mode": "HEAT",
            },
            "sdm.devices.traits.Temperature": {
                "ambientTemperatureCelsius": 16.2,
            },
            "sdm.devices.traits.ThermostatTemperatureSetpoint": {
                "heatCelsius": 22.0,
            },
        },
    )

    assert len(hass.states.async_all()) == 1
    thermostat = hass.states.get("climate.my_thermostat")
    assert thermostat is not None
    assert thermostat.state == HVAC_MODE_HEAT
    assert thermostat.attributes[ATTR_HVAC_ACTION] == CURRENT_HVAC_HEAT
    assert thermostat.attributes[ATTR_CURRENT_TEMPERATURE] == 16.2
    assert set(thermostat.attributes[ATTR_HVAC_MODES]) == {
        HVAC_MODE_HEAT,
        HVAC_MODE_COOL,
        HVAC_MODE_HEAT_COOL,
        HVAC_MODE_OFF,
    }
    assert thermostat.attributes[ATTR_TEMPERATURE] == 22.0
    assert thermostat.attributes[ATTR_TARGET_TEMP_LOW] is None
    assert thermostat.attributes[ATTR_TARGET_TEMP_HIGH] is None
    assert ATTR_PRESET_MODE not in thermostat.attributes
    assert ATTR_PRESET_MODES not in thermostat.attributes


async def test_thermostat_cool(hass):
    """Test a thermostat that is cooling."""
    await setup_climate(
        hass,
        {
            "sdm.devices.traits.ThermostatHvac": {
                "status": "COOLING",
            },
            "sdm.devices.traits.ThermostatMode": {
                "availableModes": ["HEAT", "COOL", "HEATCOOL", "OFF"],
                "mode": "COOL",
            },
            "sdm.devices.traits.Temperature": {
                "ambientTemperatureCelsius": 29.9,
            },
            "sdm.devices.traits.ThermostatTemperatureSetpoint": {
                "coolCelsius": 28.0,
            },
        },
    )

    assert len(hass.states.async_all()) == 1
    thermostat = hass.states.get("climate.my_thermostat")
    assert thermostat is not None
    assert thermostat.state == HVAC_MODE_COOL
    assert thermostat.attributes[ATTR_HVAC_ACTION] == CURRENT_HVAC_COOL
    assert thermostat.attributes[ATTR_CURRENT_TEMPERATURE] == 29.9
    assert set(thermostat.attributes[ATTR_HVAC_MODES]) == {
        HVAC_MODE_HEAT,
        HVAC_MODE_COOL,
        HVAC_MODE_HEAT_COOL,
        HVAC_MODE_OFF,
    }
    assert thermostat.attributes[ATTR_TEMPERATURE] == 28.0
    assert thermostat.attributes[ATTR_TARGET_TEMP_LOW] is None
    assert thermostat.attributes[ATTR_TARGET_TEMP_HIGH] is None
    assert ATTR_PRESET_MODE not in thermostat.attributes
    assert ATTR_PRESET_MODES not in thermostat.attributes


async def test_thermostat_heatcool(hass):
    """Test a thermostat that is cooling in heatcool mode."""
    await setup_climate(
        hass,
        {
            "sdm.devices.traits.ThermostatHvac": {
                "status": "COOLING",
            },
            "sdm.devices.traits.ThermostatMode": {
                "availableModes": ["HEAT", "COOL", "HEATCOOL", "OFF"],
                "mode": "HEATCOOL",
            },
            "sdm.devices.traits.Temperature": {
                "ambientTemperatureCelsius": 29.9,
            },
            "sdm.devices.traits.ThermostatTemperatureSetpoint": {
                "heatCelsius": 22.0,
                "coolCelsius": 28.0,
            },
        },
    )

    assert len(hass.states.async_all()) == 1
    thermostat = hass.states.get("climate.my_thermostat")
    assert thermostat is not None
    assert thermostat.state == HVAC_MODE_HEAT_COOL
    assert thermostat.attributes[ATTR_HVAC_ACTION] == CURRENT_HVAC_COOL
    assert thermostat.attributes[ATTR_CURRENT_TEMPERATURE] == 29.9
    assert set(thermostat.attributes[ATTR_HVAC_MODES]) == {
        HVAC_MODE_HEAT,
        HVAC_MODE_COOL,
        HVAC_MODE_HEAT_COOL,
        HVAC_MODE_OFF,
    }
    assert thermostat.attributes[ATTR_TARGET_TEMP_LOW] == 22.0
    assert thermostat.attributes[ATTR_TARGET_TEMP_HIGH] == 28.0
    assert thermostat.attributes[ATTR_TEMPERATURE] is None
    assert ATTR_PRESET_MODE not in thermostat.attributes
    assert ATTR_PRESET_MODES not in thermostat.attributes


async def test_thermostat_eco_off(hass):
    """Test a thermostat cooling with eco off."""
    await setup_climate(
        hass,
        {
            "sdm.devices.traits.ThermostatHvac": {
                "status": "COOLING",
            },
            "sdm.devices.traits.ThermostatMode": {
                "availableModes": ["HEAT", "COOL", "HEATCOOL", "OFF"],
                "mode": "HEATCOOL",
            },
            "sdm.devices.traits.ThermostatEco": {
                "availableModes": ["MANUAL_ECO", "OFF"],
                "mode": "OFF",
                "heatCelsius": 20.0,
                "coolCelsius": 22.0,
            },
            "sdm.devices.traits.Temperature": {
                "ambientTemperatureCelsius": 29.9,
            },
            "sdm.devices.traits.ThermostatTemperatureSetpoint": {
                "heatCelsius": 22.0,
                "coolCelsius": 28.0,
            },
        },
    )

    assert len(hass.states.async_all()) == 1
    thermostat = hass.states.get("climate.my_thermostat")
    assert thermostat is not None
    assert thermostat.state == HVAC_MODE_HEAT_COOL
    assert thermostat.attributes[ATTR_HVAC_ACTION] == CURRENT_HVAC_COOL
    assert thermostat.attributes[ATTR_CURRENT_TEMPERATURE] == 29.9
    assert set(thermostat.attributes[ATTR_HVAC_MODES]) == {
        HVAC_MODE_HEAT,
        HVAC_MODE_COOL,
        HVAC_MODE_HEAT_COOL,
        HVAC_MODE_OFF,
    }
    assert thermostat.attributes[ATTR_TARGET_TEMP_LOW] == 22.0
    assert thermostat.attributes[ATTR_TARGET_TEMP_HIGH] == 28.0
    assert thermostat.attributes[ATTR_TEMPERATURE] is None
    assert thermostat.attributes[ATTR_PRESET_MODE] == PRESET_NONE
    assert thermostat.attributes[ATTR_PRESET_MODES] == [PRESET_ECO, PRESET_NONE]


async def test_thermostat_eco_on(hass):
    """Test a thermostat in eco mode."""
    await setup_climate(
        hass,
        {
            "sdm.devices.traits.ThermostatHvac": {
                "status": "COOLING",
            },
            "sdm.devices.traits.ThermostatMode": {
                "availableModes": ["HEAT", "COOL", "HEATCOOL", "OFF"],
                "mode": "HEATCOOL",
            },
            "sdm.devices.traits.ThermostatEco": {
                "availableModes": ["MANUAL_ECO", "OFF"],
                "mode": "MANUAL_ECO",
                "heatCelsius": 21.0,
                "coolCelsius": 29.0,
            },
            "sdm.devices.traits.Temperature": {
                "ambientTemperatureCelsius": 29.9,
            },
            "sdm.devices.traits.ThermostatTemperatureSetpoint": {
                "heatCelsius": 22.0,
                "coolCelsius": 28.0,
            },
        },
    )

    assert len(hass.states.async_all()) == 1
    thermostat = hass.states.get("climate.my_thermostat")
    assert thermostat is not None
    assert thermostat.state == HVAC_MODE_HEAT_COOL
    assert thermostat.attributes[ATTR_HVAC_ACTION] == CURRENT_HVAC_COOL
    assert thermostat.attributes[ATTR_CURRENT_TEMPERATURE] == 29.9
    assert set(thermostat.attributes[ATTR_HVAC_MODES]) == {
        HVAC_MODE_HEAT,
        HVAC_MODE_COOL,
        HVAC_MODE_HEAT_COOL,
        HVAC_MODE_OFF,
    }
    assert thermostat.attributes[ATTR_TARGET_TEMP_LOW] == 21.0
    assert thermostat.attributes[ATTR_TARGET_TEMP_HIGH] == 29.0
    assert thermostat.attributes[ATTR_TEMPERATURE] is None
    assert thermostat.attributes[ATTR_PRESET_MODE] == PRESET_ECO
    assert thermostat.attributes[ATTR_PRESET_MODES] == [PRESET_ECO, PRESET_NONE]


async def test_thermostat_eco_heat_only(hass):
    """Test a thermostat in eco mode that only supports heat."""
    await setup_climate(
        hass,
        {
            "sdm.devices.traits.ThermostatHvac": {
                "status": "OFF",
            },
            "sdm.devices.traits.ThermostatMode": {
                "availableModes": ["HEAT", "OFF"],
                "mode": "HEAT",
            },
            "sdm.devices.traits.ThermostatEco": {
                "availableModes": ["MANUAL_ECO", "OFF"],
                "mode": "MANUAL_ECO",
                "heatCelsius": 21.0,
                "coolCelsius": 29.0,
            },
            "sdm.devices.traits.Temperature": {
                "ambientTemperatureCelsius": 29.9,
            },
            "sdm.devices.traits.ThermostatTemperatureSetpoint": {},
        },
    )

    assert len(hass.states.async_all()) == 1
    thermostat = hass.states.get("climate.my_thermostat")
    assert thermostat is not None
    assert thermostat.state == HVAC_MODE_HEAT
    assert thermostat.attributes[ATTR_HVAC_ACTION] == CURRENT_HVAC_OFF
    assert thermostat.attributes[ATTR_CURRENT_TEMPERATURE] == 29.9
    assert set(thermostat.attributes[ATTR_HVAC_MODES]) == {
        HVAC_MODE_HEAT,
        HVAC_MODE_OFF,
    }
    assert thermostat.attributes[ATTR_TEMPERATURE] == 21.0
    assert ATTR_TARGET_TEMP_LOW not in thermostat.attributes
    assert ATTR_TARGET_TEMP_HIGH not in thermostat.attributes
    assert thermostat.attributes[ATTR_PRESET_MODE] == PRESET_ECO
    assert thermostat.attributes[ATTR_PRESET_MODES] == [PRESET_ECO, PRESET_NONE]


async def test_thermostat_set_hvac_mode(hass, auth):
    """Test a thermostat changing hvac modes."""
    subscriber = await setup_climate(
        hass,
        {
            "sdm.devices.traits.ThermostatHvac": {"status": "OFF"},
            "sdm.devices.traits.ThermostatMode": {
                "availableModes": ["HEAT", "COOL", "HEATCOOL", "OFF"],
                "mode": "OFF",
            },
        },
        auth=auth,
    )

    assert len(hass.states.async_all()) == 1
    thermostat = hass.states.get("climate.my_thermostat")
    assert thermostat is not None
    assert thermostat.state == HVAC_MODE_OFF
    assert thermostat.attributes[ATTR_HVAC_ACTION] == CURRENT_HVAC_OFF

    await common.async_set_hvac_mode(hass, HVAC_MODE_HEAT)
    await hass.async_block_till_done()

    assert auth.method == "post"
    assert auth.url == "some-device-id:executeCommand"
    assert auth.json == {
        "command": "sdm.devices.commands.ThermostatMode.SetMode",
        "params": {"mode": "HEAT"},
    }

    # Local state does not reflect the update
    thermostat = hass.states.get("climate.my_thermostat")
    assert thermostat is not None
    assert thermostat.state == HVAC_MODE_OFF
    assert thermostat.attributes[ATTR_HVAC_ACTION] == CURRENT_HVAC_OFF

    # Simulate pubsub message when mode changes
    event = EventMessage(
        {
            "eventId": "some-event-id",
            "timestamp": "2019-01-01T00:00:01Z",
            "resourceUpdate": {
                "name": "some-device-id",
                "traits": {
                    "sdm.devices.traits.ThermostatMode": {
                        "availableModes": ["HEAT", "COOL", "HEATCOOL", "OFF"],
                        "mode": "HEAT",
                    },
                },
            },
        },
        auth=None,
    )
    await subscriber.async_receive_event(event)
    await hass.async_block_till_done()  # Process dispatch/update signal

    thermostat = hass.states.get("climate.my_thermostat")
    assert thermostat is not None
    assert thermostat.state == HVAC_MODE_HEAT
    assert thermostat.attributes[ATTR_HVAC_ACTION] == CURRENT_HVAC_OFF

    # Simulate pubsub message when the thermostat starts heating
    event = EventMessage(
        {
            "eventId": "some-event-id",
            "timestamp": "2019-01-01T00:00:01Z",
            "resourceUpdate": {
                "name": "some-device-id",
                "traits": {
                    "sdm.devices.traits.ThermostatHvac": {
                        "status": "HEATING",
                    },
                },
            },
        },
        auth=None,
    )
    await subscriber.async_receive_event(event)
    await hass.async_block_till_done()  # Process dispatch/update signal

    thermostat = hass.states.get("climate.my_thermostat")
    assert thermostat is not None
    assert thermostat.state == HVAC_MODE_HEAT
    assert thermostat.attributes[ATTR_HVAC_ACTION] == CURRENT_HVAC_HEAT


async def test_thermostat_invalid_hvac_mode(hass, auth):
    """Test setting an hvac_mode that is not supported."""
    await setup_climate(
        hass,
        {
            "sdm.devices.traits.ThermostatHvac": {"status": "OFF"},
            "sdm.devices.traits.ThermostatMode": {
                "availableModes": ["HEAT", "COOL", "HEATCOOL", "OFF"],
                "mode": "OFF",
            },
        },
        auth=auth,
    )

    assert len(hass.states.async_all()) == 1
    thermostat = hass.states.get("climate.my_thermostat")
    assert thermostat is not None
    assert thermostat.state == HVAC_MODE_OFF
    assert thermostat.attributes[ATTR_HVAC_ACTION] == CURRENT_HVAC_OFF

    with pytest.raises(ValueError):
        await common.async_set_hvac_mode(hass, HVAC_MODE_DRY)
        await hass.async_block_till_done()

    assert thermostat.state == HVAC_MODE_OFF
    assert auth.method is None  # No communication with API


async def test_thermostat_set_eco_preset(hass, auth):
    """Test a thermostat put into eco mode."""
    subscriber = await setup_climate(
        hass,
        {
            "sdm.devices.traits.ThermostatHvac": {"status": "OFF"},
            "sdm.devices.traits.ThermostatEco": {
                "availableModes": ["MANUAL_ECO", "OFF"],
                "mode": "OFF",
                "heatCelsius": 15.0,
                "coolCelsius": 28.0,
            },
            "sdm.devices.traits.ThermostatMode": {
                "availableModes": ["HEAT", "COOL", "HEATCOOL", "OFF"],
                "mode": "OFF",
            },
        },
        auth=auth,
    )

    assert len(hass.states.async_all()) == 1
    thermostat = hass.states.get("climate.my_thermostat")
    assert thermostat is not None
    assert thermostat.state == HVAC_MODE_OFF
    assert thermostat.attributes[ATTR_HVAC_ACTION] == CURRENT_HVAC_OFF
    assert thermostat.attributes[ATTR_PRESET_MODE] == PRESET_NONE

    # Turn on eco mode
    await common.async_set_preset_mode(hass, PRESET_ECO)
    await hass.async_block_till_done()

    assert auth.method == "post"
    assert auth.url == "some-device-id:executeCommand"
    assert auth.json == {
        "command": "sdm.devices.commands.ThermostatEco.SetMode",
        "params": {"mode": "MANUAL_ECO"},
    }

    # Local state does not reflect the update
    thermostat = hass.states.get("climate.my_thermostat")
    assert thermostat is not None
    assert thermostat.state == HVAC_MODE_OFF
    assert thermostat.attributes[ATTR_HVAC_ACTION] == CURRENT_HVAC_OFF
    assert thermostat.attributes[ATTR_PRESET_MODE] == PRESET_NONE

    # Simulate pubsub message when mode changes
    event = EventMessage(
        {
            "eventId": "some-event-id",
            "timestamp": "2019-01-01T00:00:01Z",
            "resourceUpdate": {
                "name": "some-device-id",
                "traits": {
                    "sdm.devices.traits.ThermostatEco": {
                        "availableModes": ["HEAT", "COOL", "HEATCOOL", "OFF"],
                        "mode": "MANUAL_ECO",
                        "heatCelsius": 15.0,
                        "coolCelsius": 28.0,
                    },
                },
            },
        },
        auth=auth,
    )
    await subscriber.async_receive_event(event)
    await hass.async_block_till_done()  # Process dispatch/update signal

    thermostat = hass.states.get("climate.my_thermostat")
    assert thermostat is not None
    assert thermostat.state == HVAC_MODE_OFF
    assert thermostat.attributes[ATTR_HVAC_ACTION] == CURRENT_HVAC_OFF
    assert thermostat.attributes[ATTR_PRESET_MODE] == PRESET_ECO

    # Turn off eco mode
    await common.async_set_preset_mode(hass, PRESET_NONE)
    await hass.async_block_till_done()

    assert auth.method == "post"
    assert auth.url == "some-device-id:executeCommand"
    assert auth.json == {
        "command": "sdm.devices.commands.ThermostatEco.SetMode",
        "params": {"mode": "OFF"},
    }


async def test_thermostat_set_cool(hass, auth):
    """Test a thermostat in cool mode with a temperature change."""
    await setup_climate(
        hass,
        {
            "sdm.devices.traits.ThermostatHvac": {"status": "OFF"},
            "sdm.devices.traits.ThermostatMode": {
                "availableModes": ["HEAT", "COOL", "HEATCOOL", "OFF"],
                "mode": "COOL",
            },
            "sdm.devices.traits.ThermostatTemperatureSetpoint": {
                "coolCelsius": 25.0,
            },
        },
        auth=auth,
    )

    assert len(hass.states.async_all()) == 1
    thermostat = hass.states.get("climate.my_thermostat")
    assert thermostat is not None
    assert thermostat.state == HVAC_MODE_COOL

    await common.async_set_temperature(hass, temperature=24.0)
    await hass.async_block_till_done()

    assert auth.method == "post"
    assert auth.url == "some-device-id:executeCommand"
    assert auth.json == {
        "command": "sdm.devices.commands.ThermostatTemperatureSetpoint.SetCool",
        "params": {"coolCelsius": 24.0},
    }


async def test_thermostat_set_heat(hass, auth):
    """Test a thermostat heating mode with a temperature change."""
    await setup_climate(
        hass,
        {
            "sdm.devices.traits.ThermostatHvac": {"status": "OFF"},
            "sdm.devices.traits.ThermostatMode": {
                "availableModes": ["HEAT", "COOL", "HEATCOOL", "OFF"],
                "mode": "HEAT",
            },
            "sdm.devices.traits.ThermostatTemperatureSetpoint": {
                "heatCelsius": 19.0,
            },
        },
        auth=auth,
    )

    assert len(hass.states.async_all()) == 1
    thermostat = hass.states.get("climate.my_thermostat")
    assert thermostat is not None
    assert thermostat.state == HVAC_MODE_HEAT

    await common.async_set_temperature(hass, temperature=20.0)
    await hass.async_block_till_done()

    assert auth.method == "post"
    assert auth.url == "some-device-id:executeCommand"
    assert auth.json == {
        "command": "sdm.devices.commands.ThermostatTemperatureSetpoint.SetHeat",
        "params": {"heatCelsius": 20.0},
    }


async def test_thermostat_set_heat_cool(hass, auth):
    """Test a thermostat in heatcool mode with a temperature change."""
    await setup_climate(
        hass,
        {
            "sdm.devices.traits.ThermostatHvac": {"status": "OFF"},
            "sdm.devices.traits.ThermostatMode": {
                "availableModes": ["HEAT", "COOL", "HEATCOOL", "OFF"],
                "mode": "HEATCOOL",
            },
            "sdm.devices.traits.ThermostatTemperatureSetpoint": {
                "heatCelsius": 19.0,
                "coolCelsius": 25.0,
            },
        },
        auth=auth,
    )

    assert len(hass.states.async_all()) == 1
    thermostat = hass.states.get("climate.my_thermostat")
    assert thermostat is not None
    assert thermostat.state == HVAC_MODE_HEAT_COOL

    await common.async_set_temperature(
        hass, target_temp_low=20.0, target_temp_high=24.0
    )
    await hass.async_block_till_done()

    assert auth.method == "post"
    assert auth.url == "some-device-id:executeCommand"
    assert auth.json == {
        "command": "sdm.devices.commands.ThermostatTemperatureSetpoint.SetRange",
        "params": {"heatCelsius": 20.0, "coolCelsius": 24.0},
    }


async def test_thermostat_fan_off(hass):
    """Test a thermostat with the fan not running."""
    await setup_climate(
        hass,
        {
            "sdm.devices.traits.Fan": {
                "timerMode": "OFF",
                "timerTimeout": "2019-05-10T03:22:54Z",
            },
            "sdm.devices.traits.ThermostatHvac": {"status": "OFF"},
            "sdm.devices.traits.ThermostatMode": {
                "availableModes": ["HEAT", "COOL", "HEATCOOL", "OFF"],
                "mode": "OFF",
            },
            "sdm.devices.traits.Temperature": {
                "ambientTemperatureCelsius": 16.2,
            },
        },
    )

    assert len(hass.states.async_all()) == 1
    thermostat = hass.states.get("climate.my_thermostat")
    assert thermostat is not None
    assert thermostat.state == HVAC_MODE_OFF
    assert thermostat.attributes[ATTR_HVAC_ACTION] == CURRENT_HVAC_OFF
    assert thermostat.attributes[ATTR_CURRENT_TEMPERATURE] == 16.2
    assert set(thermostat.attributes[ATTR_HVAC_MODES]) == {
        HVAC_MODE_HEAT,
        HVAC_MODE_COOL,
        HVAC_MODE_HEAT_COOL,
        HVAC_MODE_FAN_ONLY,
        HVAC_MODE_OFF,
    }
    assert thermostat.attributes[ATTR_FAN_MODE] == FAN_OFF
    assert thermostat.attributes[ATTR_FAN_MODES] == [FAN_ON, FAN_OFF]


async def test_thermostat_fan_on(hass):
    """Test a thermostat with the fan running."""
    await setup_climate(
        hass,
        {
            "sdm.devices.traits.Fan": {
                "timerMode": "ON",
                "timerTimeout": "2019-05-10T03:22:54Z",
            },
            "sdm.devices.traits.ThermostatHvac": {
                "status": "OFF",
            },
            "sdm.devices.traits.ThermostatMode": {
                "availableModes": ["HEAT", "COOL", "HEATCOOL", "OFF"],
                "mode": "OFF",
            },
            "sdm.devices.traits.Temperature": {
                "ambientTemperatureCelsius": 16.2,
            },
        },
    )

    assert len(hass.states.async_all()) == 1
    thermostat = hass.states.get("climate.my_thermostat")
    assert thermostat is not None
    assert thermostat.state == HVAC_MODE_FAN_ONLY
    assert thermostat.attributes[ATTR_HVAC_ACTION] == CURRENT_HVAC_OFF
    assert thermostat.attributes[ATTR_CURRENT_TEMPERATURE] == 16.2
    assert set(thermostat.attributes[ATTR_HVAC_MODES]) == {
        HVAC_MODE_HEAT,
        HVAC_MODE_COOL,
        HVAC_MODE_HEAT_COOL,
        HVAC_MODE_FAN_ONLY,
        HVAC_MODE_OFF,
    }
    assert thermostat.attributes[ATTR_FAN_MODE] == FAN_ON
    assert thermostat.attributes[ATTR_FAN_MODES] == [FAN_ON, FAN_OFF]


async def test_thermostat_cool_with_fan(hass):
    """Test a thermostat cooling while the fan is on."""
    await setup_climate(
        hass,
        {
            "sdm.devices.traits.Fan": {
                "timerMode": "ON",
                "timerTimeout": "2019-05-10T03:22:54Z",
            },
            "sdm.devices.traits.ThermostatHvac": {
                "status": "OFF",
            },
            "sdm.devices.traits.ThermostatMode": {
                "availableModes": ["HEAT", "COOL", "HEATCOOL", "OFF"],
                "mode": "COOL",
            },
        },
    )

    assert len(hass.states.async_all()) == 1
    thermostat = hass.states.get("climate.my_thermostat")
    assert thermostat is not None
    assert thermostat.state == HVAC_MODE_COOL
    assert thermostat.attributes[ATTR_HVAC_ACTION] == CURRENT_HVAC_OFF
    assert set(thermostat.attributes[ATTR_HVAC_MODES]) == {
        HVAC_MODE_HEAT,
        HVAC_MODE_COOL,
        HVAC_MODE_HEAT_COOL,
        HVAC_MODE_FAN_ONLY,
        HVAC_MODE_OFF,
    }
    assert thermostat.attributes[ATTR_FAN_MODE] == FAN_ON
    assert thermostat.attributes[ATTR_FAN_MODES] == [FAN_ON, FAN_OFF]


async def test_thermostat_set_fan(hass, auth):
    """Test a thermostat enabling the fan."""
    await setup_climate(
        hass,
        {
            "sdm.devices.traits.Fan": {
                "timerMode": "ON",
                "timerTimeout": "2019-05-10T03:22:54Z",
            },
            "sdm.devices.traits.ThermostatHvac": {
                "status": "OFF",
            },
            "sdm.devices.traits.ThermostatMode": {
                "availableModes": ["HEAT", "COOL", "HEATCOOL", "OFF"],
                "mode": "OFF",
            },
        },
        auth=auth,
    )

    assert len(hass.states.async_all()) == 1
    thermostat = hass.states.get("climate.my_thermostat")
    assert thermostat is not None
    assert thermostat.state == HVAC_MODE_FAN_ONLY
    assert thermostat.attributes[ATTR_FAN_MODE] == FAN_ON
    assert thermostat.attributes[ATTR_FAN_MODES] == [FAN_ON, FAN_OFF]

    # Turn off fan mode
    await common.async_set_fan_mode(hass, FAN_OFF)
    await hass.async_block_till_done()

    assert auth.method == "post"
    assert auth.url == "some-device-id:executeCommand"
    assert auth.json == {
        "command": "sdm.devices.commands.Fan.SetTimer",
        "params": {"timerMode": "OFF"},
    }

    # Turn on fan mode
    await common.async_set_fan_mode(hass, FAN_ON)
    await hass.async_block_till_done()

    assert auth.method == "post"
    assert auth.url == "some-device-id:executeCommand"
    assert auth.json == {
        "command": "sdm.devices.commands.Fan.SetTimer",
        "params": {
            "duration": "43200s",
            "timerMode": "ON",
        },
    }


async def test_thermostat_fan_empty(hass):
    """Test a fan trait with an empty response."""
    await setup_climate(
        hass,
        {
            "sdm.devices.traits.Fan": {},
            "sdm.devices.traits.ThermostatHvac": {"status": "OFF"},
            "sdm.devices.traits.ThermostatMode": {
                "availableModes": ["HEAT", "COOL", "HEATCOOL", "OFF"],
                "mode": "OFF",
            },
            "sdm.devices.traits.Temperature": {
                "ambientTemperatureCelsius": 16.2,
            },
        },
    )

    assert len(hass.states.async_all()) == 1
    thermostat = hass.states.get("climate.my_thermostat")
    assert thermostat is not None
    assert thermostat.state == HVAC_MODE_OFF
    assert thermostat.attributes[ATTR_HVAC_ACTION] == CURRENT_HVAC_OFF
    assert thermostat.attributes[ATTR_CURRENT_TEMPERATURE] == 16.2
    assert set(thermostat.attributes[ATTR_HVAC_MODES]) == {
        HVAC_MODE_HEAT,
        HVAC_MODE_COOL,
        HVAC_MODE_HEAT_COOL,
        HVAC_MODE_OFF,
    }
    assert ATTR_FAN_MODE not in thermostat.attributes
    assert ATTR_FAN_MODES not in thermostat.attributes

    # Ignores set_fan_mode since it is lacking SUPPORT_FAN_MODE
    await common.async_set_fan_mode(hass, FAN_ON)
    await hass.async_block_till_done()

    assert ATTR_FAN_MODE not in thermostat.attributes
    assert ATTR_FAN_MODES not in thermostat.attributes


async def test_thermostat_invalid_fan_mode(hass):
    """Test setting a fan mode that is not supported."""
    await setup_climate(
        hass,
        {
            "sdm.devices.traits.Fan": {
                "timerMode": "ON",
                "timerTimeout": "2019-05-10T03:22:54Z",
            },
            "sdm.devices.traits.ThermostatHvac": {"status": "OFF"},
            "sdm.devices.traits.ThermostatMode": {
                "availableModes": ["HEAT", "COOL", "HEATCOOL", "OFF"],
                "mode": "OFF",
            },
            "sdm.devices.traits.Temperature": {
                "ambientTemperatureCelsius": 16.2,
            },
        },
    )

    assert len(hass.states.async_all()) == 1
    thermostat = hass.states.get("climate.my_thermostat")
    assert thermostat is not None
    assert thermostat.state == HVAC_MODE_FAN_ONLY
    assert thermostat.attributes[ATTR_HVAC_ACTION] == CURRENT_HVAC_OFF
    assert thermostat.attributes[ATTR_CURRENT_TEMPERATURE] == 16.2
    assert set(thermostat.attributes[ATTR_HVAC_MODES]) == {
        HVAC_MODE_HEAT,
        HVAC_MODE_COOL,
        HVAC_MODE_HEAT_COOL,
        HVAC_MODE_FAN_ONLY,
        HVAC_MODE_OFF,
    }
    assert thermostat.attributes[ATTR_FAN_MODE] == FAN_ON
    assert thermostat.attributes[ATTR_FAN_MODES] == [FAN_ON, FAN_OFF]

    with pytest.raises(ValueError):
        await common.async_set_fan_mode(hass, FAN_LOW)
        await hass.async_block_till_done()


async def test_thermostat_set_hvac_fan_only(hass, auth):
    """Test a thermostat enabling the fan via hvac_mode."""
    await setup_climate(
        hass,
        {
            "sdm.devices.traits.Fan": {
                "timerMode": "OFF",
                "timerTimeout": "2019-05-10T03:22:54Z",
            },
            "sdm.devices.traits.ThermostatHvac": {
                "status": "OFF",
            },
            "sdm.devices.traits.ThermostatMode": {
                "availableModes": ["HEAT", "COOL", "HEATCOOL", "OFF"],
                "mode": "OFF",
            },
        },
        auth=auth,
    )

    assert len(hass.states.async_all()) == 1
    thermostat = hass.states.get("climate.my_thermostat")
    assert thermostat is not None
    assert thermostat.state == HVAC_MODE_OFF
    assert thermostat.attributes[ATTR_FAN_MODE] == FAN_OFF
    assert thermostat.attributes[ATTR_FAN_MODES] == [FAN_ON, FAN_OFF]

    await common.async_set_hvac_mode(hass, HVAC_MODE_FAN_ONLY)
    await hass.async_block_till_done()

    assert len(auth.captured_requests) == 2

    (method, url, json, headers) = auth.captured_requests.pop(0)
    assert method == "post"
    assert url == "some-device-id:executeCommand"
    assert json == {
        "command": "sdm.devices.commands.Fan.SetTimer",
        "params": {"duration": "43200s", "timerMode": "ON"},
    }
    (method, url, json, headers) = auth.captured_requests.pop(0)
    assert method == "post"
    assert url == "some-device-id:executeCommand"
    assert json == {
        "command": "sdm.devices.commands.ThermostatMode.SetMode",
        "params": {"mode": "OFF"},
    }


async def test_thermostat_target_temp(hass, auth):
    """Test a thermostat changing hvac modes and affected on target temps."""
    subscriber = await setup_climate(
        hass,
        {
            "sdm.devices.traits.ThermostatHvac": {
                "status": "HEATING",
            },
            "sdm.devices.traits.ThermostatMode": {
                "availableModes": ["HEAT", "COOL", "HEATCOOL", "OFF"],
                "mode": "HEAT",
            },
            "sdm.devices.traits.Temperature": {
                "ambientTemperatureCelsius": 20.1,
            },
            "sdm.devices.traits.ThermostatTemperatureSetpoint": {
                "heatCelsius": 23.0,
            },
        },
        auth=auth,
    )

    assert len(hass.states.async_all()) == 1
    thermostat = hass.states.get("climate.my_thermostat")
    assert thermostat is not None
    assert thermostat.state == HVAC_MODE_HEAT
    assert thermostat.attributes[ATTR_TEMPERATURE] == 23.0
    assert thermostat.attributes[ATTR_TARGET_TEMP_LOW] is None
    assert thermostat.attributes[ATTR_TARGET_TEMP_HIGH] is None

    # Simulate pubsub message changing modes
    event = EventMessage(
        {
            "eventId": "some-event-id",
            "timestamp": "2019-01-01T00:00:01Z",
            "resourceUpdate": {
                "name": "some-device-id",
                "traits": {
                    "sdm.devices.traits.ThermostatMode": {
                        "availableModes": ["HEAT", "COOL", "HEATCOOL", "OFF"],
                        "mode": "HEATCOOL",
                    },
                    "sdm.devices.traits.ThermostatTemperatureSetpoint": {
                        "heatCelsius": 22.0,
                        "coolCelsius": 28.0,
                    },
                },
            },
        },
        auth=None,
    )
    await subscriber.async_receive_event(event)
    await hass.async_block_till_done()  # Process dispatch/update signal

    thermostat = hass.states.get("climate.my_thermostat")
    assert thermostat is not None
    assert thermostat.state == HVAC_MODE_HEAT_COOL
    assert thermostat.attributes[ATTR_TARGET_TEMP_LOW] == 22.0
    assert thermostat.attributes[ATTR_TARGET_TEMP_HIGH] == 28.0
    assert thermostat.attributes[ATTR_TEMPERATURE] is None


async def test_thermostat_missing_mode_traits(hass):
    """Test a thermostat missing many thermostat traits in api response."""
    await setup_climate(
        hass,
        {
            "sdm.devices.traits.ThermostatHvac": {"status": "OFF"},
        },
    )

    assert len(hass.states.async_all()) == 1
    thermostat = hass.states.get("climate.my_thermostat")
    assert thermostat is not None
    assert thermostat.state == HVAC_MODE_OFF
    assert thermostat.attributes[ATTR_HVAC_ACTION] == CURRENT_HVAC_OFF
    assert thermostat.attributes[ATTR_CURRENT_TEMPERATURE] is None
    assert set(thermostat.attributes[ATTR_HVAC_MODES]) == set()
    assert ATTR_TEMPERATURE not in thermostat.attributes
    assert ATTR_TARGET_TEMP_LOW not in thermostat.attributes
    assert ATTR_TARGET_TEMP_HIGH not in thermostat.attributes
    assert ATTR_PRESET_MODE not in thermostat.attributes
    assert ATTR_PRESET_MODES not in thermostat.attributes
    assert ATTR_FAN_MODE not in thermostat.attributes
    assert ATTR_FAN_MODES not in thermostat.attributes

    await common.async_set_temperature(hass, temperature=24.0)
    await hass.async_block_till_done()
    assert ATTR_TEMPERATURE not in thermostat.attributes

    await common.async_set_preset_mode(hass, PRESET_ECO)
    await hass.async_block_till_done()
    assert ATTR_PRESET_MODE not in thermostat.attributes


async def test_thermostat_missing_temperature_trait(hass):
    """Test a thermostat missing many thermostat traits in api response."""
    await setup_climate(
        hass,
        {
            "sdm.devices.traits.ThermostatHvac": {"status": "OFF"},
            "sdm.devices.traits.ThermostatMode": {
                "availableModes": ["HEAT", "COOL", "HEATCOOL", "OFF"],
                "mode": "HEAT",
            },
        },
    )

    assert len(hass.states.async_all()) == 1
    thermostat = hass.states.get("climate.my_thermostat")
    assert thermostat is not None
    assert thermostat.state == HVAC_MODE_HEAT
    assert thermostat.attributes[ATTR_HVAC_ACTION] == CURRENT_HVAC_OFF
    assert thermostat.attributes[ATTR_CURRENT_TEMPERATURE] is None
    assert set(thermostat.attributes[ATTR_HVAC_MODES]) == {
        HVAC_MODE_HEAT,
        HVAC_MODE_COOL,
        HVAC_MODE_HEAT_COOL,
        HVAC_MODE_OFF,
    }
    assert thermostat.attributes[ATTR_TEMPERATURE] is None
    assert thermostat.attributes[ATTR_TARGET_TEMP_LOW] is None
    assert thermostat.attributes[ATTR_TARGET_TEMP_HIGH] is None
    assert ATTR_PRESET_MODE not in thermostat.attributes
    assert ATTR_PRESET_MODES not in thermostat.attributes
    assert ATTR_FAN_MODE not in thermostat.attributes
    assert ATTR_FAN_MODES not in thermostat.attributes

    await common.async_set_temperature(hass, temperature=24.0)
    await hass.async_block_till_done()
    assert thermostat.attributes[ATTR_TEMPERATURE] is None


async def test_thermostat_unexpected_hvac_status(hass):
    """Test a thermostat missing many thermostat traits in api response."""
    await setup_climate(
        hass,
        {
            "sdm.devices.traits.ThermostatHvac": {"status": "UNEXPECTED"},
        },
    )

    assert len(hass.states.async_all()) == 1
    thermostat = hass.states.get("climate.my_thermostat")
    assert thermostat is not None
    assert thermostat.state == HVAC_MODE_OFF
    assert ATTR_HVAC_ACTION not in thermostat.attributes
    assert thermostat.attributes[ATTR_CURRENT_TEMPERATURE] is None
    assert set(thermostat.attributes[ATTR_HVAC_MODES]) == set()
    assert ATTR_TEMPERATURE not in thermostat.attributes
    assert ATTR_TARGET_TEMP_LOW not in thermostat.attributes
    assert ATTR_TARGET_TEMP_HIGH not in thermostat.attributes
    assert ATTR_PRESET_MODE not in thermostat.attributes
    assert ATTR_PRESET_MODES not in thermostat.attributes
    assert ATTR_FAN_MODE not in thermostat.attributes
    assert ATTR_FAN_MODES not in thermostat.attributes

    with pytest.raises(ValueError):
        await common.async_set_hvac_mode(hass, HVAC_MODE_DRY)
        await hass.async_block_till_done()
    assert thermostat.state == HVAC_MODE_OFF


async def test_thermostat_missing_set_point(hass):
    """Test a thermostat missing many thermostat traits in api response."""
    await setup_climate(
        hass,
        {
            "sdm.devices.traits.ThermostatHvac": {"status": "OFF"},
            "sdm.devices.traits.ThermostatMode": {
                "availableModes": ["HEAT", "COOL", "HEATCOOL", "OFF"],
                "mode": "HEATCOOL",
            },
        },
    )

    assert len(hass.states.async_all()) == 1
    thermostat = hass.states.get("climate.my_thermostat")
    assert thermostat is not None
    assert thermostat.state == HVAC_MODE_HEAT_COOL
    assert thermostat.attributes[ATTR_HVAC_ACTION] == CURRENT_HVAC_OFF
    assert thermostat.attributes[ATTR_CURRENT_TEMPERATURE] is None
    assert set(thermostat.attributes[ATTR_HVAC_MODES]) == {
        HVAC_MODE_HEAT,
        HVAC_MODE_COOL,
        HVAC_MODE_HEAT_COOL,
        HVAC_MODE_OFF,
    }
    assert thermostat.attributes[ATTR_TEMPERATURE] is None
    assert thermostat.attributes[ATTR_TARGET_TEMP_LOW] is None
    assert thermostat.attributes[ATTR_TARGET_TEMP_HIGH] is None
    assert ATTR_PRESET_MODE not in thermostat.attributes
    assert ATTR_PRESET_MODES not in thermostat.attributes
    assert ATTR_FAN_MODE not in thermostat.attributes
    assert ATTR_FAN_MODES not in thermostat.attributes


async def test_thermostat_unexepected_hvac_mode(hass):
    """Test a thermostat missing many thermostat traits in api response."""
    await setup_climate(
        hass,
        {
            "sdm.devices.traits.ThermostatHvac": {"status": "OFF"},
            "sdm.devices.traits.ThermostatMode": {
                "availableModes": ["HEAT", "COOL", "HEATCOOL", "OFF", "UNEXPECTED"],
                "mode": "UNEXPECTED",
            },
        },
    )

    assert len(hass.states.async_all()) == 1
    thermostat = hass.states.get("climate.my_thermostat")
    assert thermostat is not None
    assert thermostat.state == HVAC_MODE_OFF
    assert thermostat.attributes[ATTR_HVAC_ACTION] == CURRENT_HVAC_OFF
    assert thermostat.attributes[ATTR_CURRENT_TEMPERATURE] is None
    assert set(thermostat.attributes[ATTR_HVAC_MODES]) == {
        HVAC_MODE_HEAT,
        HVAC_MODE_COOL,
        HVAC_MODE_HEAT_COOL,
        HVAC_MODE_OFF,
    }
    assert thermostat.attributes[ATTR_TEMPERATURE] is None
    assert thermostat.attributes[ATTR_TARGET_TEMP_LOW] is None
    assert thermostat.attributes[ATTR_TARGET_TEMP_HIGH] is None
    assert ATTR_PRESET_MODE not in thermostat.attributes
    assert ATTR_PRESET_MODES not in thermostat.attributes
    assert ATTR_FAN_MODE not in thermostat.attributes
    assert ATTR_FAN_MODES not in thermostat.attributes


async def test_thermostat_invalid_set_preset_mode(hass, auth):
    """Test a thermostat set with an invalid preset mode."""
    await setup_climate(
        hass,
        {
            "sdm.devices.traits.ThermostatHvac": {"status": "OFF"},
            "sdm.devices.traits.ThermostatEco": {
                "availableModes": ["MANUAL_ECO", "OFF"],
                "mode": "OFF",
                "heatCelsius": 15.0,
                "coolCelsius": 28.0,
            },
        },
        auth=auth,
    )

    assert len(hass.states.async_all()) == 1
    thermostat = hass.states.get("climate.my_thermostat")
    assert thermostat is not None
    assert thermostat.state == HVAC_MODE_OFF
    assert thermostat.attributes[ATTR_PRESET_MODE] == PRESET_NONE
    assert thermostat.attributes[ATTR_PRESET_MODES] == [PRESET_ECO, PRESET_NONE]

    # Set preset mode that is invalid
    with pytest.raises(ValueError):
        await common.async_set_preset_mode(hass, PRESET_SLEEP)
        await hass.async_block_till_done()

    # No RPC sent
    assert auth.method is None

    # Preset is unchanged
    assert thermostat.attributes[ATTR_PRESET_MODE] == PRESET_NONE
    assert thermostat.attributes[ATTR_PRESET_MODES] == [PRESET_ECO, PRESET_NONE]
