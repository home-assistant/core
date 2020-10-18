"""
Test for Nest sensors platform for the Smart Device Management API.

These tests fake out the subscriber/devicemanager, and are not using a real
pubsub subscriber.
"""

from google_nest_sdm.device import Device
from google_nest_sdm.event import EventMessage

from homeassistant.components.climate.const import (
    ATTR_CURRENT_TEMPERATURE,
    ATTR_HVAC_ACTION,
    ATTR_HVAC_MODES,
    ATTR_PRESET_MODE,
    ATTR_PRESET_MODES,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    CURRENT_HVAC_COOL,
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_OFF,
    HVAC_MODE_AUTO,
    HVAC_MODE_COOL,
    HVAC_MODE_HEAT,
    HVAC_MODE_HEAT_COOL,
    HVAC_MODE_OFF,
    PRESET_ECO,
    PRESET_NONE,
)

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
    assert thermostat.attributes[ATTR_HVAC_MODES] == [
        HVAC_MODE_HEAT,
        HVAC_MODE_COOL,
        HVAC_MODE_HEAT_COOL,
        HVAC_MODE_OFF,
    ]
    assert ATTR_TARGET_TEMP_HIGH not in thermostat.attributes
    assert ATTR_TARGET_TEMP_LOW not in thermostat.attributes
    assert ATTR_PRESET_MODE not in thermostat.attributes
    assert ATTR_PRESET_MODES not in thermostat.attributes


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
    assert thermostat.attributes[ATTR_HVAC_MODES] == [
        HVAC_MODE_HEAT,
        HVAC_MODE_COOL,
        HVAC_MODE_HEAT_COOL,
        HVAC_MODE_OFF,
    ]
    assert thermostat.attributes[ATTR_TARGET_TEMP_LOW] == 22.0
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
    assert thermostat.attributes[ATTR_HVAC_MODES] == [
        HVAC_MODE_HEAT,
        HVAC_MODE_COOL,
        HVAC_MODE_HEAT_COOL,
        HVAC_MODE_OFF,
    ]
    assert thermostat.attributes[ATTR_TARGET_TEMP_HIGH] == 28.0
    assert thermostat.attributes[ATTR_TARGET_TEMP_LOW] is None
    assert ATTR_PRESET_MODE not in thermostat.attributes
    assert ATTR_PRESET_MODES not in thermostat.attributes


async def test_thermostat_heatcool(hass):
    """Test a thermostat that is cooling."""
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
    assert thermostat.attributes[ATTR_HVAC_MODES] == [
        HVAC_MODE_HEAT,
        HVAC_MODE_COOL,
        HVAC_MODE_HEAT_COOL,
        HVAC_MODE_OFF,
    ]
    assert thermostat.attributes[ATTR_TARGET_TEMP_LOW] == 22.0
    assert thermostat.attributes[ATTR_TARGET_TEMP_HIGH] == 28.0
    assert ATTR_PRESET_MODE not in thermostat.attributes
    assert ATTR_PRESET_MODES not in thermostat.attributes


async def test_thermostat_eco_off(hass):
    """Test a thermostat that is cooling."""
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
    assert thermostat.attributes[ATTR_HVAC_MODES] == [
        HVAC_MODE_HEAT,
        HVAC_MODE_COOL,
        HVAC_MODE_HEAT_COOL,
        HVAC_MODE_OFF,
    ]
    assert thermostat.attributes[ATTR_TARGET_TEMP_LOW] == 22.0
    assert thermostat.attributes[ATTR_TARGET_TEMP_HIGH] == 28.0
    assert thermostat.attributes[ATTR_PRESET_MODE] == PRESET_NONE
    assert thermostat.attributes[ATTR_PRESET_MODES] == [PRESET_ECO]


async def test_thermostat_eco_on(hass):
    """Test a thermostat that is cooling."""
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
    assert thermostat.state == HVAC_MODE_AUTO
    assert thermostat.attributes[ATTR_HVAC_ACTION] == CURRENT_HVAC_COOL
    assert thermostat.attributes[ATTR_CURRENT_TEMPERATURE] == 29.9
    assert thermostat.attributes[ATTR_HVAC_MODES] == [
        HVAC_MODE_HEAT,
        HVAC_MODE_COOL,
        HVAC_MODE_HEAT_COOL,
        HVAC_MODE_OFF,
    ]
    assert thermostat.attributes[ATTR_TARGET_TEMP_LOW] == 21.0
    assert thermostat.attributes[ATTR_TARGET_TEMP_HIGH] == 29.0
    assert thermostat.attributes[ATTR_PRESET_MODE] == PRESET_ECO
    assert thermostat.attributes[ATTR_PRESET_MODES] == [PRESET_ECO]


class FakeAuth:
    """A fake implementation of the auth class that records requests."""

    def __init__(self):
        """Initialize FakeAuth."""
        self.method = None
        self.url = None
        self.json = None

    async def request(self, method, url, json):
        """Capure the request arguments for tests to assert on."""
        self.method = method
        self.url = url
        self.json = json


async def test_thermostat_set_hvac_mode(hass):
    """Test a thermostat that is not running."""
    auth = FakeAuth()
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
    subscriber.receive_event(event)
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
    subscriber.receive_event(event)
    await hass.async_block_till_done()  # Process dispatch/update signal

    thermostat = hass.states.get("climate.my_thermostat")
    assert thermostat is not None
    assert thermostat.state == HVAC_MODE_HEAT
    assert thermostat.attributes[ATTR_HVAC_ACTION] == CURRENT_HVAC_HEAT


async def test_thermostat_set_eco_preset(hass):
    """Test a thermostat that is not running."""
    auth = FakeAuth()
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
                    },
                },
            },
        },
        auth=auth,
    )
    subscriber.receive_event(event)
    await hass.async_block_till_done()  # Process dispatch/update signal

    thermostat = hass.states.get("climate.my_thermostat")
    assert thermostat is not None
    assert thermostat.state == HVAC_MODE_AUTO
    assert thermostat.attributes[ATTR_HVAC_ACTION] == CURRENT_HVAC_OFF
    assert thermostat.attributes[ATTR_PRESET_MODE] == PRESET_ECO

    await common.async_set_preset_mode(hass, PRESET_NONE)
    await hass.async_block_till_done()

    assert auth.method == "post"
    assert auth.url == "some-device-id:executeCommand"
    assert auth.json == {
        "command": "sdm.devices.commands.ThermostatEco.SetMode",
        "params": {"mode": "OFF"},
    }


async def test_thermostat_set_cool(hass):
    """Test a thermostat that is not running."""
    auth = FakeAuth()
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


async def test_thermostat_set_heat(hass):
    """Test a thermostat that is not running."""
    auth = FakeAuth()
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


async def test_thermostat_set_heat_cool(hass):
    """Test a thermostat that is not running."""
    auth = FakeAuth()
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
