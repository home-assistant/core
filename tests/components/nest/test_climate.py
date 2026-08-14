"""Test for Nest climate platform for the Smart Device Management API.

These tests fake out the subscriber/devicemanager, and are not using a real
pubsub subscriber.
"""

import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
from http import HTTPStatus
from typing import Any
from unittest.mock import AsyncMock, Mock

import aiohttp
import pytest

from homeassistant.components.climate import (
    ATTR_CURRENT_HUMIDITY,
    ATTR_CURRENT_TEMPERATURE,
    ATTR_FAN_MODE,
    ATTR_FAN_MODES,
    ATTR_HVAC_ACTION,
    ATTR_HVAC_MODES,
    ATTR_PRESET_MODE,
    ATTR_PRESET_MODES,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    FAN_LOW,
    FAN_OFF,
    FAN_ON,
    PRESET_ECO,
    PRESET_NONE,
    PRESET_SLEEP,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.components.nest import climate as nest_climate
from homeassistant.const import (
    ATTR_SUPPORTED_FEATURES,
    ATTR_TEMPERATURE,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    HomeAssistantError,
    ServiceNotSupported,
    ServiceValidationError,
)
from homeassistant.util import dt as dt_util

from .common import (
    DEVICE_COMMAND,
    DEVICE_ID,
    DOMAIN,
    CreateDevice,
    PlatformSetup,
    create_nest_event,
)
from .conftest import FakeAuth

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.components.climate import common

type CreateEvent = Callable[[dict[str, Any]], Awaitable[None]]

EVENT_ID = "some-event-id"


async def async_fire_temperature_debounce(hass: HomeAssistant) -> None:
    """Fire the pending temperature debounce timer."""
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=10))
    await hass.async_block_till_done()


@pytest.fixture
def platforms() -> list[str]:
    """Fixture to specify platforms to test."""
    return ["climate"]


@pytest.fixture
def device_traits() -> dict[str, Any]:
    """Fixture that sets default traits used for devices."""
    return {"sdm.devices.traits.Info": {"customName": "My Thermostat"}}


@pytest.fixture
async def create_event(
    hass: HomeAssistant,
    subscriber: AsyncMock,
) -> CreateEvent:
    """Fixture to send a pub/sub event."""

    async def create_event(traits: dict[str, Any]) -> None:
        await subscriber.async_receive_event(
            create_nest_event(
                {
                    "eventId": EVENT_ID,
                    "timestamp": "2019-01-01T00:00:01Z",
                    "resourceUpdate": {
                        "name": DEVICE_ID,
                        "traits": traits,
                    },
                },
            )
        )
        await hass.async_block_till_done()

    return create_event


async def test_no_devices(hass: HomeAssistant, setup_platform: PlatformSetup) -> None:
    """Test no devices returned by the api."""
    await setup_platform()
    assert len(hass.states.async_all()) == 0


async def test_climate_devices(
    hass: HomeAssistant, setup_platform: PlatformSetup, create_device: CreateDevice
) -> None:
    """Test no eligible climate devices returned by the api."""
    create_device.create({"sdm.devices.traits.CameraImage": {}})
    await setup_platform()
    assert len(hass.states.async_all()) == 0


async def test_thermostat_off(
    hass: HomeAssistant, setup_platform: PlatformSetup, create_device: CreateDevice
) -> None:
    """Test a thermostat that is not running."""
    create_device.create(
        {
            "sdm.devices.traits.ThermostatHvac": {"status": "OFF"},
            "sdm.devices.traits.ThermostatMode": {
                "availableModes": ["HEAT", "COOL", "HEATCOOL", "OFF"],
                "mode": "OFF",
            },
            "sdm.devices.traits.Temperature": {
                "ambientTemperatureCelsius": 16.2,
            },
            "sdm.devices.traits.Humidity": {
                "ambientHumidityPercent": 40.6,
            },
        },
    )
    await setup_platform()

    assert len(hass.states.async_all()) == 1
    thermostat = hass.states.get("climate.my_thermostat")
    assert thermostat is not None
    assert thermostat.state == HVACMode.OFF
    assert thermostat.attributes[ATTR_HVAC_ACTION] == HVACAction.OFF
    assert thermostat.attributes[ATTR_CURRENT_HUMIDITY] == 40.6
    assert thermostat.attributes[ATTR_CURRENT_TEMPERATURE] == 16.2
    assert set(thermostat.attributes[ATTR_HVAC_MODES]) == {
        HVACMode.HEAT,
        HVACMode.COOL,
        HVACMode.HEAT_COOL,
        HVACMode.OFF,
    }
    assert thermostat.attributes[ATTR_TEMPERATURE] is None
    assert thermostat.attributes[ATTR_TARGET_TEMP_LOW] is None
    assert thermostat.attributes[ATTR_TARGET_TEMP_HIGH] is None
    assert ATTR_PRESET_MODE not in thermostat.attributes
    assert ATTR_PRESET_MODES not in thermostat.attributes
    assert ATTR_FAN_MODE not in thermostat.attributes
    assert ATTR_FAN_MODES not in thermostat.attributes


async def test_thermostat_heat(
    hass: HomeAssistant, setup_platform: PlatformSetup, create_device: CreateDevice
) -> None:
    """Test a thermostat that is heating."""
    create_device.create(
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
            "sdm.devices.traits.Humidity": {
                "ambientHumidityPercent": 40.6,
            },
            "sdm.devices.traits.ThermostatTemperatureSetpoint": {
                "heatCelsius": 22.0,
            },
        },
    )
    await setup_platform()

    assert len(hass.states.async_all()) == 1
    thermostat = hass.states.get("climate.my_thermostat")
    assert thermostat is not None
    assert thermostat.state == HVACMode.HEAT
    assert thermostat.attributes[ATTR_HVAC_ACTION] == HVACAction.HEATING
    assert thermostat.attributes[ATTR_CURRENT_HUMIDITY] == 40.6
    assert thermostat.attributes[ATTR_CURRENT_TEMPERATURE] == 16.2
    assert set(thermostat.attributes[ATTR_HVAC_MODES]) == {
        HVACMode.HEAT,
        HVACMode.COOL,
        HVACMode.HEAT_COOL,
        HVACMode.OFF,
    }
    assert thermostat.attributes[ATTR_TEMPERATURE] == 22.0
    assert thermostat.attributes[ATTR_TARGET_TEMP_LOW] is None
    assert thermostat.attributes[ATTR_TARGET_TEMP_HIGH] is None
    assert ATTR_PRESET_MODE not in thermostat.attributes
    assert ATTR_PRESET_MODES not in thermostat.attributes


async def test_thermostat_cool(
    hass: HomeAssistant, setup_platform: PlatformSetup, create_device: CreateDevice
) -> None:
    """Test a thermostat that is cooling."""
    create_device.create(
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
    await setup_platform()

    assert len(hass.states.async_all()) == 1
    thermostat = hass.states.get("climate.my_thermostat")
    assert thermostat is not None
    assert thermostat.state == HVACMode.COOL
    assert thermostat.attributes[ATTR_HVAC_ACTION] == HVACAction.COOLING
    assert thermostat.attributes[ATTR_CURRENT_TEMPERATURE] == 29.9
    assert set(thermostat.attributes[ATTR_HVAC_MODES]) == {
        HVACMode.HEAT,
        HVACMode.COOL,
        HVACMode.HEAT_COOL,
        HVACMode.OFF,
    }
    assert thermostat.attributes[ATTR_TEMPERATURE] == 28.0
    assert thermostat.attributes[ATTR_TARGET_TEMP_LOW] is None
    assert thermostat.attributes[ATTR_TARGET_TEMP_HIGH] is None
    assert ATTR_PRESET_MODE not in thermostat.attributes
    assert ATTR_PRESET_MODES not in thermostat.attributes


async def test_thermostat_heatcool(
    hass: HomeAssistant, setup_platform: PlatformSetup, create_device: CreateDevice
) -> None:
    """Test a thermostat that is cooling in heatcool mode."""
    create_device.create(
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
    await setup_platform()

    assert len(hass.states.async_all()) == 1
    thermostat = hass.states.get("climate.my_thermostat")
    assert thermostat is not None
    assert thermostat.state == HVACMode.HEAT_COOL
    assert thermostat.attributes[ATTR_HVAC_ACTION] == HVACAction.COOLING
    assert thermostat.attributes[ATTR_CURRENT_TEMPERATURE] == 29.9
    assert set(thermostat.attributes[ATTR_HVAC_MODES]) == {
        HVACMode.HEAT,
        HVACMode.COOL,
        HVACMode.HEAT_COOL,
        HVACMode.OFF,
    }
    assert thermostat.attributes[ATTR_TARGET_TEMP_LOW] == 22.0
    assert thermostat.attributes[ATTR_TARGET_TEMP_HIGH] == 28.0
    assert thermostat.attributes[ATTR_TEMPERATURE] is None
    assert ATTR_PRESET_MODE not in thermostat.attributes
    assert ATTR_PRESET_MODES not in thermostat.attributes


async def test_thermostat_eco_off(
    hass: HomeAssistant, setup_platform: PlatformSetup, create_device: CreateDevice
) -> None:
    """Test a thermostat cooling with eco off."""
    create_device.create(
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
    await setup_platform()

    assert len(hass.states.async_all()) == 1
    thermostat = hass.states.get("climate.my_thermostat")
    assert thermostat is not None
    assert thermostat.state == HVACMode.HEAT_COOL
    assert thermostat.attributes[ATTR_HVAC_ACTION] == HVACAction.COOLING
    assert thermostat.attributes[ATTR_CURRENT_TEMPERATURE] == 29.9
    assert set(thermostat.attributes[ATTR_HVAC_MODES]) == {
        HVACMode.HEAT,
        HVACMode.COOL,
        HVACMode.HEAT_COOL,
        HVACMode.OFF,
    }
    assert thermostat.attributes[ATTR_TARGET_TEMP_LOW] == 22.0
    assert thermostat.attributes[ATTR_TARGET_TEMP_HIGH] == 28.0
    assert thermostat.attributes[ATTR_TEMPERATURE] is None
    assert thermostat.attributes[ATTR_PRESET_MODE] == PRESET_NONE
    assert thermostat.attributes[ATTR_PRESET_MODES] == [PRESET_ECO, PRESET_NONE]


async def test_thermostat_eco_on(
    hass: HomeAssistant, setup_platform: PlatformSetup, create_device: CreateDevice
) -> None:
    """Test a thermostat in eco mode."""
    create_device.create(
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
    await setup_platform()

    assert len(hass.states.async_all()) == 1
    thermostat = hass.states.get("climate.my_thermostat")
    assert thermostat is not None
    assert thermostat.state == HVACMode.HEAT_COOL
    assert thermostat.attributes[ATTR_HVAC_ACTION] == HVACAction.COOLING
    assert thermostat.attributes[ATTR_CURRENT_TEMPERATURE] == 29.9
    assert set(thermostat.attributes[ATTR_HVAC_MODES]) == {
        HVACMode.HEAT,
        HVACMode.COOL,
        HVACMode.HEAT_COOL,
        HVACMode.OFF,
    }
    assert thermostat.attributes[ATTR_TARGET_TEMP_LOW] == 21.0
    assert thermostat.attributes[ATTR_TARGET_TEMP_HIGH] == 29.0
    assert thermostat.attributes[ATTR_TEMPERATURE] is None
    assert thermostat.attributes[ATTR_PRESET_MODE] == PRESET_ECO
    assert thermostat.attributes[ATTR_PRESET_MODES] == [PRESET_ECO, PRESET_NONE]


async def test_thermostat_eco_heat_only(
    hass: HomeAssistant, setup_platform: PlatformSetup, create_device: CreateDevice
) -> None:
    """Test a thermostat in eco mode that only supports heat."""
    create_device.create(
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
    await setup_platform()

    assert len(hass.states.async_all()) == 1
    thermostat = hass.states.get("climate.my_thermostat")
    assert thermostat is not None
    assert thermostat.state == HVACMode.HEAT
    assert thermostat.attributes[ATTR_HVAC_ACTION] == HVACAction.IDLE
    assert thermostat.attributes[ATTR_CURRENT_TEMPERATURE] == 29.9
    assert set(thermostat.attributes[ATTR_HVAC_MODES]) == {
        HVACMode.HEAT,
        HVACMode.OFF,
    }
    assert thermostat.attributes[ATTR_TEMPERATURE] == 21.0
    assert ATTR_TARGET_TEMP_LOW not in thermostat.attributes
    assert ATTR_TARGET_TEMP_HIGH not in thermostat.attributes
    assert thermostat.attributes[ATTR_PRESET_MODE] == PRESET_ECO
    assert thermostat.attributes[ATTR_PRESET_MODES] == [PRESET_ECO, PRESET_NONE]


async def test_thermostat_set_hvac_mode(
    hass: HomeAssistant,
    setup_platform: PlatformSetup,
    auth: FakeAuth,
    create_device: CreateDevice,
    create_event: CreateEvent,
) -> None:
    """Test a thermostat changing hvac modes."""
    create_device.create(
        {
            "sdm.devices.traits.ThermostatHvac": {"status": "OFF"},
            "sdm.devices.traits.ThermostatMode": {
                "availableModes": ["HEAT", "COOL", "HEATCOOL", "OFF"],
                "mode": "OFF",
            },
        }
    )
    await setup_platform()

    assert len(hass.states.async_all()) == 1
    thermostat = hass.states.get("climate.my_thermostat")
    assert thermostat is not None
    assert thermostat.state == HVACMode.OFF
    assert thermostat.attributes[ATTR_HVAC_ACTION] == HVACAction.OFF

    await common.async_set_hvac_mode(hass, HVACMode.HEAT)
    await hass.async_block_till_done()

    assert auth.method == "post"
    assert auth.url == DEVICE_COMMAND
    assert auth.json == {
        "command": "sdm.devices.commands.ThermostatMode.SetMode",
        "params": {"mode": "HEAT"},
    }

    # Local state does not reflect the update
    thermostat = hass.states.get("climate.my_thermostat")
    assert thermostat is not None
    assert thermostat.state == HVACMode.OFF
    assert thermostat.attributes[ATTR_HVAC_ACTION] == HVACAction.OFF

    # Simulate pubsub message when mode changes
    await create_event(
        {
            "sdm.devices.traits.ThermostatMode": {
                "availableModes": ["HEAT", "COOL", "HEATCOOL", "OFF"],
                "mode": "HEAT",
            },
        }
    )

    thermostat = hass.states.get("climate.my_thermostat")
    assert thermostat is not None
    assert thermostat.state == HVACMode.HEAT
    assert thermostat.attributes[ATTR_HVAC_ACTION] == HVACAction.IDLE

    # Simulate pubsub message when the thermostat starts heating
    await create_event(
        {
            "sdm.devices.traits.ThermostatHvac": {
                "status": "HEATING",
            },
        }
    )

    thermostat = hass.states.get("climate.my_thermostat")
    assert thermostat is not None
    assert thermostat.state == HVACMode.HEAT
    assert thermostat.attributes[ATTR_HVAC_ACTION] == HVACAction.HEATING


async def test_thermostat_invalid_hvac_mode(
    hass: HomeAssistant,
    setup_platform: PlatformSetup,
    auth: FakeAuth,
    create_device: CreateDevice,
) -> None:
    """Test setting an hvac_mode that is not supported."""
    create_device.create(
        {
            "sdm.devices.traits.ThermostatHvac": {"status": "OFF"},
            "sdm.devices.traits.ThermostatMode": {
                "availableModes": ["HEAT", "COOL", "HEATCOOL", "OFF"],
                "mode": "OFF",
            },
        }
    )
    await setup_platform()

    assert len(hass.states.async_all()) == 1
    thermostat = hass.states.get("climate.my_thermostat")
    assert thermostat is not None
    assert thermostat.state == HVACMode.OFF
    assert thermostat.attributes[ATTR_HVAC_ACTION] == HVACAction.OFF

    with pytest.raises(ServiceValidationError):
        await common.async_set_hvac_mode(hass, HVACMode.DRY)

    assert thermostat.state == HVACMode.OFF
    assert auth.method is None  # No communication with API


async def test_thermostat_set_eco_preset(
    hass: HomeAssistant,
    setup_platform: PlatformSetup,
    auth: FakeAuth,
    create_device: CreateDevice,
    create_event: CreateEvent,
) -> None:
    """Test a thermostat put into eco mode."""
    create_device.create(
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
        }
    )
    await setup_platform()

    assert len(hass.states.async_all()) == 1
    thermostat = hass.states.get("climate.my_thermostat")
    assert thermostat is not None
    assert thermostat.state == HVACMode.OFF
    assert thermostat.attributes[ATTR_HVAC_ACTION] == HVACAction.OFF
    assert thermostat.attributes[ATTR_PRESET_MODE] == PRESET_NONE

    # Turn on eco mode
    await common.async_set_preset_mode(hass, PRESET_ECO)
    await hass.async_block_till_done()

    assert auth.method == "post"
    assert auth.url == DEVICE_COMMAND
    assert auth.json == {
        "command": "sdm.devices.commands.ThermostatEco.SetMode",
        "params": {"mode": "MANUAL_ECO"},
    }

    # Local state does not reflect the update
    thermostat = hass.states.get("climate.my_thermostat")
    assert thermostat is not None
    assert thermostat.state == HVACMode.OFF
    assert thermostat.attributes[ATTR_HVAC_ACTION] == HVACAction.OFF
    assert thermostat.attributes[ATTR_PRESET_MODE] == PRESET_NONE

    # Simulate pubsub message when mode changes
    await create_event(
        {
            "sdm.devices.traits.ThermostatEco": {
                "availableModes": ["HEAT", "COOL", "HEATCOOL", "OFF"],
                "mode": "MANUAL_ECO",
                "heatCelsius": 15.0,
                "coolCelsius": 28.0,
            },
        }
    )

    thermostat = hass.states.get("climate.my_thermostat")
    assert thermostat is not None
    assert thermostat.state == HVACMode.OFF
    assert thermostat.attributes[ATTR_HVAC_ACTION] == HVACAction.OFF
    assert thermostat.attributes[ATTR_PRESET_MODE] == PRESET_ECO

    # Turn off eco mode
    await common.async_set_preset_mode(hass, PRESET_NONE)
    await hass.async_block_till_done()

    assert auth.method == "post"
    assert auth.url == DEVICE_COMMAND
    assert auth.json == {
        "command": "sdm.devices.commands.ThermostatEco.SetMode",
        "params": {"mode": "OFF"},
    }

    # Simulate the mode changing
    await create_event(
        {
            "sdm.devices.traits.ThermostatEco": {
                "availableModes": ["HEAT", "COOL", "HEATCOOL", "OFF"],
                "mode": "OFF",
            },
        }
    )

    auth.method = None
    auth.url = None
    auth.json = None

    # Attempting to set the preset mode when already in that mode will
    # not send any messages to the API (it would otherwise fail)
    await common.async_set_preset_mode(hass, PRESET_NONE)
    await hass.async_block_till_done()

    assert auth.method is None
    assert auth.url is None
    assert auth.json is None


async def test_thermostat_set_cool(
    hass: HomeAssistant,
    setup_platform: PlatformSetup,
    auth: FakeAuth,
    create_device: CreateDevice,
) -> None:
    """Test a thermostat in cool mode with a temperature change."""
    create_device.create(
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
    )
    await setup_platform()

    assert len(hass.states.async_all()) == 1
    thermostat = hass.states.get("climate.my_thermostat")
    assert thermostat is not None
    assert thermostat.state == HVACMode.COOL

    await common.async_set_temperature(hass, temperature=24.0)
    await hass.async_block_till_done()
    await async_fire_temperature_debounce(hass)

    assert auth.method == "post"
    assert auth.url == DEVICE_COMMAND
    assert auth.json == {
        "command": "sdm.devices.commands.ThermostatTemperatureSetpoint.SetCool",
        "params": {"coolCelsius": 24.0},
    }


async def test_thermostat_set_heat(
    hass: HomeAssistant,
    setup_platform: PlatformSetup,
    auth: FakeAuth,
    create_device: CreateDevice,
) -> None:
    """Test a thermostat heating mode with a temperature change."""
    create_device.create(
        {
            "sdm.devices.traits.ThermostatHvac": {"status": "OFF"},
            "sdm.devices.traits.ThermostatMode": {
                "availableModes": ["HEAT", "COOL", "HEATCOOL", "OFF"],
                "mode": "HEAT",
            },
            "sdm.devices.traits.ThermostatTemperatureSetpoint": {
                "heatCelsius": 19.0,
            },
        }
    )
    await setup_platform()

    assert len(hass.states.async_all()) == 1
    thermostat = hass.states.get("climate.my_thermostat")
    assert thermostat is not None
    assert thermostat.state == HVACMode.HEAT

    await common.async_set_temperature(hass, temperature=20.0)
    await hass.async_block_till_done()
    await async_fire_temperature_debounce(hass)

    assert auth.method == "post"
    assert auth.url == DEVICE_COMMAND
    assert auth.json == {
        "command": "sdm.devices.commands.ThermostatTemperatureSetpoint.SetHeat",
        "params": {"heatCelsius": 20.0},
    }


async def test_thermostat_temperature_changes_use_trailing_debounce(
    hass: HomeAssistant,
    setup_platform: PlatformSetup,
    auth: FakeAuth,
    create_device: CreateDevice,
    create_event: CreateEvent,
) -> None:
    """Test only the final temperature is sent after the debounce period."""
    create_device.create(
        {
            "sdm.devices.traits.ThermostatHvac": {"status": "OFF"},
            "sdm.devices.traits.ThermostatMode": {
                "availableModes": ["HEAT", "OFF"],
                "mode": "HEAT",
            },
            "sdm.devices.traits.ThermostatTemperatureSetpoint": {
                "heatCelsius": 19.0,
            },
        }
    )
    await setup_platform()

    await common.async_set_temperature(hass, temperature=20.0)
    await common.async_set_temperature(hass, temperature=21.0)
    await common.async_set_temperature(hass, temperature=22.0)
    await hass.async_block_till_done()

    assert auth.captured_requests == []
    thermostat = hass.states.get("climate.my_thermostat")
    assert thermostat is not None
    assert thermostat.attributes[ATTR_TEMPERATURE] == 22.0

    await async_fire_temperature_debounce(hass)

    assert len(auth.captured_requests) == 1
    assert auth.json == {
        "command": "sdm.devices.commands.ThermostatTemperatureSetpoint.SetHeat",
        "params": {"heatCelsius": 22.0},
    }

    thermostat = hass.states.get("climate.my_thermostat")
    assert thermostat is not None
    assert thermostat.attributes[ATTR_TEMPERATURE] == 22.0

    await create_event(
        {
            "sdm.devices.traits.ThermostatTemperatureSetpoint": {
                "heatCelsius": 21.0,
            }
        }
    )
    thermostat = hass.states.get("climate.my_thermostat")
    assert thermostat is not None
    assert thermostat.attributes[ATTR_TEMPERATURE] == 22.0

    await create_event(
        {
            "sdm.devices.traits.ThermostatTemperatureSetpoint": {
                "heatCelsius": 22.0,
            }
        }
    )
    thermostat = hass.states.get("climate.my_thermostat")
    assert thermostat is not None
    assert thermostat.attributes[ATTR_TEMPERATURE] == 22.0


async def test_stale_temperature_callback_preserves_new_timer(
    hass: HomeAssistant,
    setup_platform: PlatformSetup,
    create_device: CreateDevice,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test a stale callback does not clear a newer timer's cancel handle."""
    create_device.create(
        {
            "sdm.devices.traits.ThermostatHvac": {"status": "OFF"},
            "sdm.devices.traits.ThermostatMode": {
                "availableModes": ["HEAT", "OFF"],
                "mode": "HEAT",
            },
            "sdm.devices.traits.ThermostatTemperatureSetpoint": {
                "heatCelsius": 19.0,
            },
        }
    )
    await setup_platform()

    callbacks: list[Callable[[datetime], Awaitable[None]]] = []
    cancel_timers: list[Mock] = []

    def async_call_later(
        _hass: HomeAssistant,
        delay: float,
        action: Callable[[datetime], Awaitable[None]],
    ) -> Mock:
        assert delay == nest_climate.TEMPERATURE_DEBOUNCE_SECONDS
        callbacks.append(action)
        cancel_timer = Mock()
        cancel_timers.append(cancel_timer)
        return cancel_timer

    monkeypatch.setattr(nest_climate, "async_call_later", async_call_later)

    await common.async_set_temperature(hass, temperature=20.0)
    await common.async_set_temperature(hass, temperature=21.0)
    cancel_timers[0].assert_called_once_with()

    await callbacks[0](dt_util.utcnow())
    await common.async_set_temperature(hass, temperature=22.0)

    cancel_timers[1].assert_called_once_with()


async def test_unconfirmed_temperature_times_out(
    hass: HomeAssistant,
    setup_platform: PlatformSetup,
    create_device: CreateDevice,
) -> None:
    """Test optimistic temperature expires without a matching device update."""
    create_device.create(
        {
            "sdm.devices.traits.ThermostatHvac": {"status": "OFF"},
            "sdm.devices.traits.ThermostatMode": {
                "availableModes": ["HEAT", "OFF"],
                "mode": "HEAT",
            },
            "sdm.devices.traits.ThermostatTemperatureSetpoint": {
                "heatCelsius": 19.0,
            },
        }
    )
    await setup_platform()

    await common.async_set_temperature(hass, temperature=20.0)
    await async_fire_temperature_debounce(hass)

    thermostat = hass.states.get("climate.my_thermostat")
    assert thermostat is not None
    assert thermostat.attributes[ATTR_TEMPERATURE] == 20.0

    async_fire_time_changed(
        hass,
        dt_util.utcnow()
        + timedelta(seconds=nest_climate.TEMPERATURE_CONFIRMATION_TIMEOUT_SECONDS),
    )
    await hass.async_block_till_done()

    thermostat = hass.states.get("climate.my_thermostat")
    assert thermostat is not None
    assert thermostat.attributes[ATTR_TEMPERATURE] == 19.0


async def test_stale_confirmation_callback_preserves_new_timer(
    hass: HomeAssistant,
    setup_platform: PlatformSetup,
    create_device: CreateDevice,
    create_event: CreateEvent,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test a stale confirmation callback does not orphan a newer timer."""
    create_device.create(
        {
            "sdm.devices.traits.ThermostatHvac": {"status": "OFF"},
            "sdm.devices.traits.ThermostatMode": {
                "availableModes": ["HEAT", "OFF"],
                "mode": "HEAT",
            },
            "sdm.devices.traits.ThermostatTemperatureSetpoint": {
                "heatCelsius": 19.0,
            },
        }
    )
    await setup_platform()

    confirmation_callbacks: list[Callable[[datetime], None]] = []
    confirmation_cancel_timers: list[Mock] = []
    real_async_call_later = nest_climate.async_call_later

    def async_call_later(
        timer_hass: HomeAssistant,
        delay: float,
        action: Callable[[datetime], None],
    ) -> Mock:
        if delay != nest_climate.TEMPERATURE_CONFIRMATION_TIMEOUT_SECONDS:
            return real_async_call_later(timer_hass, delay, action)
        confirmation_callbacks.append(action)
        cancel_timer = Mock()
        confirmation_cancel_timers.append(cancel_timer)
        return cancel_timer

    monkeypatch.setattr(nest_climate, "async_call_later", async_call_later)

    await common.async_set_temperature(hass, temperature=20.0)
    await async_fire_temperature_debounce(hass)
    await common.async_set_temperature(hass, temperature=21.0)
    await async_fire_temperature_debounce(hass)

    confirmation_callbacks[0](dt_util.utcnow())
    await create_event(
        {
            "sdm.devices.traits.ThermostatTemperatureSetpoint": {
                "heatCelsius": 21.0,
            }
        }
    )

    confirmation_cancel_timers[1].assert_called_once_with()


async def test_unconfirmed_temperature_clears_on_mode_update(
    hass: HomeAssistant,
    setup_platform: PlatformSetup,
    create_device: CreateDevice,
    create_event: CreateEvent,
) -> None:
    """Test a confirmed mode change clears an obsolete optimistic temperature."""
    create_device.create(
        {
            "sdm.devices.traits.ThermostatHvac": {"status": "OFF"},
            "sdm.devices.traits.ThermostatMode": {
                "availableModes": ["HEAT", "COOL", "OFF"],
                "mode": "HEAT",
            },
            "sdm.devices.traits.ThermostatTemperatureSetpoint": {
                "heatCelsius": 19.0,
                "coolCelsius": 18.0,
            },
        }
    )
    await setup_platform()

    await common.async_set_temperature(hass, temperature=20.0)
    await async_fire_temperature_debounce(hass)

    thermostat = hass.states.get("climate.my_thermostat")
    assert thermostat is not None
    assert thermostat.attributes[ATTR_TEMPERATURE] == 20.0

    await create_event(
        {
            "sdm.devices.traits.ThermostatMode": {
                "availableModes": ["HEAT", "COOL", "OFF"],
                "mode": "COOL",
            },
            "sdm.devices.traits.ThermostatTemperatureSetpoint": {
                "heatCelsius": 19.0,
                "coolCelsius": 18.0,
            },
        }
    )

    thermostat = hass.states.get("climate.my_thermostat")
    assert thermostat is not None
    assert thermostat.attributes[ATTR_TEMPERATURE] == 18.0


async def test_temperature_and_mode_commands_are_serialized(
    hass: HomeAssistant,
    setup_platform: PlatformSetup,
    create_device: CreateDevice,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test optimistic state remains while a mode command waits for temperature."""
    create_device.create(
        {
            "sdm.devices.traits.ThermostatHvac": {"status": "OFF"},
            "sdm.devices.traits.ThermostatMode": {
                "availableModes": ["HEAT", "COOL", "OFF"],
                "mode": "HEAT",
            },
            "sdm.devices.traits.ThermostatTemperatureSetpoint": {
                "heatCelsius": 19.0,
            },
        }
    )
    await setup_platform()

    temperature_started = asyncio.Event()
    release_temperature = asyncio.Event()
    mode_started = asyncio.Event()
    command_order: list[str] = []

    async def async_set_heat(
        _trait: nest_climate.ThermostatTemperatureSetpointTrait, temperature: float
    ) -> None:
        assert temperature == 20.0
        command_order.append("temperature_started")
        temperature_started.set()
        await release_temperature.wait()
        command_order.append("temperature_finished")

    async def async_set_mode(
        _trait: nest_climate.ThermostatModeTrait, mode: str
    ) -> None:
        assert mode == "COOL"
        command_order.append("mode_started")
        mode_started.set()

    monkeypatch.setattr(
        nest_climate.ThermostatTemperatureSetpointTrait, "set_heat", async_set_heat
    )
    monkeypatch.setattr(nest_climate.ThermostatModeTrait, "set_mode", async_set_mode)

    await common.async_set_temperature(hass, temperature=20.0)
    temperature_task = asyncio.create_task(async_fire_temperature_debounce(hass))
    await temperature_started.wait()

    thermostat = hass.states.get("climate.my_thermostat")
    assert thermostat is not None
    assert thermostat.attributes[ATTR_TEMPERATURE] == 20.0

    mode_task = asyncio.create_task(common.async_set_hvac_mode(hass, HVACMode.COOL))
    await asyncio.sleep(0)
    assert not mode_started.is_set()

    release_temperature.set()
    await asyncio.gather(temperature_task, mode_task)
    assert command_order == [
        "temperature_started",
        "temperature_finished",
        "mode_started",
    ]


async def test_entity_removal_during_temperature_command(
    hass: HomeAssistant,
    setup_platform: PlatformSetup,
    config_entry: MockConfigEntry,
    create_device: CreateDevice,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test command completion does not schedule a timer after entity removal."""
    create_device.create(
        {
            "sdm.devices.traits.ThermostatHvac": {"status": "OFF"},
            "sdm.devices.traits.ThermostatMode": {
                "availableModes": ["HEAT", "OFF"],
                "mode": "HEAT",
            },
            "sdm.devices.traits.ThermostatTemperatureSetpoint": {
                "heatCelsius": 19.0,
            },
        }
    )
    await setup_platform()

    temperature_started = asyncio.Event()
    release_temperature = asyncio.Event()

    async def async_set_heat(
        _trait: nest_climate.ThermostatTemperatureSetpointTrait, temperature: float
    ) -> None:
        assert temperature == 20.0
        temperature_started.set()
        await release_temperature.wait()

    monkeypatch.setattr(
        nest_climate.ThermostatTemperatureSetpointTrait, "set_heat", async_set_heat
    )

    await common.async_set_temperature(hass, temperature=20.0)
    temperature_task = asyncio.create_task(async_fire_temperature_debounce(hass))
    await temperature_started.wait()

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    mock_call_later = Mock()
    monkeypatch.setattr(nest_climate, "async_call_later", mock_call_later)

    release_temperature.set()
    await temperature_task

    mock_call_later.assert_not_called()


async def test_thermostat_set_temperature_hvac_mode(
    hass: HomeAssistant,
    setup_platform: PlatformSetup,
    auth: FakeAuth,
    create_device: CreateDevice,
) -> None:
    """Test setting HVAC mode while setting temperature."""
    create_device.create(
        {
            "sdm.devices.traits.ThermostatHvac": {"status": "OFF"},
            "sdm.devices.traits.ThermostatMode": {
                "availableModes": ["HEAT", "COOL", "HEATCOOL", "OFF"],
                "mode": "OFF",
            },
            "sdm.devices.traits.ThermostatTemperatureSetpoint": {
                "coolCelsius": 25.0,
            },
        },
    )
    await setup_platform()

    assert len(hass.states.async_all()) == 1
    thermostat = hass.states.get("climate.my_thermostat")
    assert thermostat is not None
    assert thermostat.state == HVACMode.OFF

    await common.async_set_temperature(hass, temperature=24.0, hvac_mode=HVACMode.COOL)
    await hass.async_block_till_done()
    await async_fire_temperature_debounce(hass)

    assert auth.method == "post"
    assert auth.url == DEVICE_COMMAND
    assert auth.json == {
        "command": "sdm.devices.commands.ThermostatTemperatureSetpoint.SetCool",
        "params": {"coolCelsius": 24.0},
    }

    await common.async_set_temperature(hass, temperature=26.0, hvac_mode=HVACMode.HEAT)
    await hass.async_block_till_done()
    await async_fire_temperature_debounce(hass)

    assert auth.method == "post"
    assert auth.url == DEVICE_COMMAND
    assert auth.json == {
        "command": "sdm.devices.commands.ThermostatTemperatureSetpoint.SetHeat",
        "params": {"heatCelsius": 26.0},
    }

    await common.async_set_temperature(
        hass, target_temp_low=20.0, target_temp_high=24.0, hvac_mode=HVACMode.HEAT_COOL
    )
    await hass.async_block_till_done()
    await async_fire_temperature_debounce(hass)

    assert auth.method == "post"
    assert auth.url == DEVICE_COMMAND
    assert auth.json == {
        "command": "sdm.devices.commands.ThermostatTemperatureSetpoint.SetRange",
        "params": {"heatCelsius": 20.0, "coolCelsius": 24.0},
    }


@pytest.mark.parametrize(
    ("setpoint", "target_low", "target_high", "expected_params"),
    [
        (
            {
                "heatCelsius": 19.0,
                "coolCelsius": 25.0,
            },
            19.0,
            20.0,
            # Cool is accepted and lowers heat by the min range
            {"heatCelsius": 18.33333, "coolCelsius": 20.0},
        ),
        (
            {
                "heatCelsius": 19.0,
                "coolCelsius": 25.0,
            },
            24.0,
            25.0,
            # Cool is accepted and lowers heat by the min range
            {"heatCelsius": 24.0, "coolCelsius": 25.66667},
        ),
    ],
)
async def test_thermostat_set_temperature_range_too_close(
    hass: HomeAssistant,
    setup_platform: PlatformSetup,
    auth: FakeAuth,
    create_device: CreateDevice,
    setpoint: dict[str, Any],
    target_low: float,
    target_high: float,
    expected_params: dict[str, Any],
) -> None:
    """Test setting an HVAC temperature range that is too small of a range."""
    create_device.create(
        {
            "sdm.devices.traits.ThermostatHvac": {"status": "OFF"},
            "sdm.devices.traits.ThermostatMode": {
                "availableModes": ["HEAT", "COOL", "HEATCOOL", "OFF"],
                "mode": "HEATCOOL",
            },
            "sdm.devices.traits.ThermostatTemperatureSetpoint": setpoint,
        },
    )
    await setup_platform()

    assert len(hass.states.async_all()) == 1
    thermostat = hass.states.get("climate.my_thermostat")
    assert thermostat is not None
    assert thermostat.state == HVACMode.HEAT_COOL

    # Move the target temp to be in too small of a range
    await common.async_set_temperature(
        hass,
        target_temp_low=target_low,
        target_temp_high=target_high,
    )
    await hass.async_block_till_done()
    await async_fire_temperature_debounce(hass)

    assert auth.method == "post"
    assert auth.url == DEVICE_COMMAND
    assert auth.json == {
        "command": "sdm.devices.commands.ThermostatTemperatureSetpoint.SetRange",
        "params": expected_params,
    }


async def test_thermostat_set_heat_cool(
    hass: HomeAssistant,
    setup_platform: PlatformSetup,
    auth: FakeAuth,
    create_device: CreateDevice,
) -> None:
    """Test a thermostat in heatcool mode with a temperature change."""
    create_device.create(
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
        }
    )
    await setup_platform()

    assert len(hass.states.async_all()) == 1
    thermostat = hass.states.get("climate.my_thermostat")
    assert thermostat is not None
    assert thermostat.state == HVACMode.HEAT_COOL

    await common.async_set_temperature(
        hass, target_temp_low=20.0, target_temp_high=24.0
    )
    await hass.async_block_till_done()
    await async_fire_temperature_debounce(hass)

    assert auth.method == "post"
    assert auth.url == DEVICE_COMMAND
    assert auth.json == {
        "command": "sdm.devices.commands.ThermostatTemperatureSetpoint.SetRange",
        "params": {"heatCelsius": 20.0, "coolCelsius": 24.0},
    }


async def test_thermostat_fan_off(
    hass: HomeAssistant,
    setup_platform: PlatformSetup,
    create_device: CreateDevice,
) -> None:
    """Test a thermostat with the fan not running."""
    create_device.create(
        {
            "sdm.devices.traits.Fan": {
                "timerMode": "OFF",
                "timerTimeout": "2019-05-10T03:22:54Z",
            },
            "sdm.devices.traits.ThermostatHvac": {"status": "OFF"},
            "sdm.devices.traits.ThermostatMode": {
                "availableModes": ["HEAT", "COOL", "HEATCOOL", "OFF"],
                "mode": "COOL",
            },
            "sdm.devices.traits.Temperature": {
                "ambientTemperatureCelsius": 16.2,
            },
            "sdm.devices.traits.Humidity": {
                "ambientHumidityPercent": 40.6,
            },
        }
    )
    await setup_platform()

    assert len(hass.states.async_all()) == 1
    thermostat = hass.states.get("climate.my_thermostat")
    assert thermostat is not None
    assert thermostat.state == HVACMode.COOL
    assert thermostat.attributes[ATTR_HVAC_ACTION] == HVACAction.IDLE
    assert thermostat.attributes[ATTR_CURRENT_HUMIDITY] == 40.6
    assert thermostat.attributes[ATTR_CURRENT_TEMPERATURE] == 16.2
    assert set(thermostat.attributes[ATTR_HVAC_MODES]) == {
        HVACMode.HEAT,
        HVACMode.COOL,
        HVACMode.HEAT_COOL,
        HVACMode.OFF,
    }
    assert thermostat.attributes[ATTR_FAN_MODE] == FAN_OFF
    assert thermostat.attributes[ATTR_FAN_MODES] == [FAN_ON, FAN_OFF]
    assert thermostat.attributes[ATTR_SUPPORTED_FEATURES] == (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )


async def test_thermostat_fan_on(
    hass: HomeAssistant,
    setup_platform: PlatformSetup,
    create_device: CreateDevice,
) -> None:
    """Test a thermostat with the fan running."""
    create_device.create(
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
            "sdm.devices.traits.Temperature": {
                "ambientTemperatureCelsius": 16.2,
            },
            "sdm.devices.traits.Humidity": {
                "ambientHumidityPercent": 40.6,
            },
        }
    )
    await setup_platform()

    assert len(hass.states.async_all()) == 1
    thermostat = hass.states.get("climate.my_thermostat")
    assert thermostat is not None
    assert thermostat.state == HVACMode.COOL
    assert thermostat.attributes[ATTR_HVAC_ACTION] == HVACAction.IDLE
    assert thermostat.attributes[ATTR_CURRENT_HUMIDITY] == 40.6
    assert thermostat.attributes[ATTR_CURRENT_TEMPERATURE] == 16.2
    assert set(thermostat.attributes[ATTR_HVAC_MODES]) == {
        HVACMode.HEAT,
        HVACMode.COOL,
        HVACMode.HEAT_COOL,
        HVACMode.OFF,
    }
    assert thermostat.attributes[ATTR_FAN_MODE] == FAN_ON
    assert thermostat.attributes[ATTR_FAN_MODES] == [FAN_ON, FAN_OFF]
    assert thermostat.attributes[ATTR_SUPPORTED_FEATURES] == (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )


async def test_thermostat_cool_with_fan(
    hass: HomeAssistant,
    setup_platform: PlatformSetup,
    create_device: CreateDevice,
) -> None:
    """Test a thermostat cooling while the fan is on."""
    create_device.create(
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
    await setup_platform()

    assert len(hass.states.async_all()) == 1
    thermostat = hass.states.get("climate.my_thermostat")
    assert thermostat is not None
    assert thermostat.state == HVACMode.COOL
    assert thermostat.attributes[ATTR_HVAC_ACTION] == HVACAction.IDLE
    assert set(thermostat.attributes[ATTR_HVAC_MODES]) == {
        HVACMode.HEAT,
        HVACMode.COOL,
        HVACMode.HEAT_COOL,
        HVACMode.OFF,
    }
    assert thermostat.attributes[ATTR_FAN_MODE] == FAN_ON
    assert thermostat.attributes[ATTR_FAN_MODES] == [FAN_ON, FAN_OFF]
    assert thermostat.attributes[ATTR_SUPPORTED_FEATURES] == (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )


async def test_thermostat_set_fan(
    hass: HomeAssistant,
    setup_platform: PlatformSetup,
    auth: FakeAuth,
    create_device: CreateDevice,
) -> None:
    """Test a thermostat enabling the fan."""
    create_device.create(
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
                "mode": "HEAT",
            },
        }
    )
    await setup_platform()

    assert len(hass.states.async_all()) == 1
    thermostat = hass.states.get("climate.my_thermostat")
    assert thermostat is not None
    assert thermostat.state == HVACMode.HEAT
    assert thermostat.attributes[ATTR_FAN_MODE] == FAN_ON
    assert thermostat.attributes[ATTR_FAN_MODES] == [FAN_ON, FAN_OFF]
    assert thermostat.attributes[ATTR_SUPPORTED_FEATURES] == (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )

    # Turn off fan mode
    await common.async_set_fan_mode(hass, FAN_OFF)
    await hass.async_block_till_done()

    assert auth.method == "post"
    assert auth.url == DEVICE_COMMAND
    assert auth.json == {
        "command": "sdm.devices.commands.Fan.SetTimer",
        "params": {"timerMode": "OFF"},
    }

    # Turn on fan mode
    await common.async_set_fan_mode(hass, FAN_ON)
    await hass.async_block_till_done()

    assert auth.method == "post"
    assert auth.url == DEVICE_COMMAND
    assert auth.json == {
        "command": "sdm.devices.commands.Fan.SetTimer",
        "params": {
            "duration": "43200s",
            "timerMode": "ON",
        },
    }


async def test_set_fan_timer(
    hass: HomeAssistant,
    setup_platform: PlatformSetup,
    auth: FakeAuth,
    create_device: CreateDevice,
) -> None:
    """Test the set_fan_timer service."""
    create_device.create(
        {
            "sdm.devices.traits.Fan": {
                "timerMode": "OFF",
            },
            "sdm.devices.traits.ThermostatHvac": {"status": "HEATING"},
            "sdm.devices.traits.ThermostatMode": {
                "availableModes": ["HEAT", "OFF"],
                "mode": "HEAT",
            },
            "sdm.devices.traits.TemperatureTrait": {"ambientTemperatureCelsius": 20.0},
        }
    )
    await setup_platform()

    # Call the set_fan_timer service
    await hass.services.async_call(
        DOMAIN,
        "set_fan_timer",
        {
            "entity_id": "climate.my_thermostat",
            "duration": {"minutes": 15},
        },
        blocking=True,
    )

    assert auth.method == "post"
    assert auth.url == DEVICE_COMMAND
    assert auth.json == {
        "command": "sdm.devices.commands.Fan.SetTimer",
        "params": {
            "duration": "900s",
            "timerMode": "ON",
        },
    }


async def test_set_fan_timer_hvac_off(
    hass: HomeAssistant,
    setup_platform: PlatformSetup,
    auth: FakeAuth,
    create_device: CreateDevice,
) -> None:
    """Test the set_fan_timer service when HVAC is off."""
    create_device.create(
        {
            "sdm.devices.traits.Fan": {
                "timerMode": "OFF",
            },
            "sdm.devices.traits.ThermostatHvac": {"status": "OFF"},
            "sdm.devices.traits.ThermostatMode": {
                "availableModes": ["HEAT", "OFF"],
                "mode": "OFF",
            },
        }
    )
    await setup_platform()

    with pytest.raises(HomeAssistantError, match="Cannot turn on fan"):
        await hass.services.async_call(
            DOMAIN,
            "set_fan_timer",
            {
                "entity_id": "climate.my_thermostat",
                "duration": {"minutes": 15},
            },
            blocking=True,
        )


async def test_set_fan_timer_no_fan(
    hass: HomeAssistant,
    setup_platform: PlatformSetup,
    create_device: CreateDevice,
) -> None:
    """Test the set_fan_timer service when device does not support fan."""
    create_device.create(
        {
            "sdm.devices.traits.ThermostatHvac": {"status": "HEATING"},
            "sdm.devices.traits.ThermostatMode": {
                "availableModes": ["HEAT", "OFF"],
                "mode": "HEAT",
            },
        }
    )
    await setup_platform()

    with pytest.raises(ServiceNotSupported, match="does not support action"):
        await hass.services.async_call(
            DOMAIN,
            "set_fan_timer",
            {
                "entity_id": "climate.my_thermostat",
                "duration": {"minutes": 15},
            },
            blocking=True,
        )


async def test_set_fan_timer_api_error(
    hass: HomeAssistant,
    setup_platform: PlatformSetup,
    auth: FakeAuth,
    create_device: CreateDevice,
) -> None:
    """Test the set_fan_timer service with an API error."""
    create_device.create(
        {
            "sdm.devices.traits.Fan": {
                "timerMode": "OFF",
            },
            "sdm.devices.traits.ThermostatHvac": {"status": "HEATING"},
            "sdm.devices.traits.ThermostatMode": {
                "availableModes": ["HEAT", "OFF"],
                "mode": "HEAT",
            },
        }
    )
    await setup_platform()

    auth.responses = [aiohttp.web.Response(status=HTTPStatus.INTERNAL_SERVER_ERROR)]
    with pytest.raises(HomeAssistantError, match="Error setting .* fan timer"):
        await hass.services.async_call(
            DOMAIN,
            "set_fan_timer",
            {
                "entity_id": "climate.my_thermostat",
                "duration": {"minutes": 15},
            },
            blocking=True,
        )


async def test_set_fan_timer_invalid_duration(
    hass: HomeAssistant,
    setup_platform: PlatformSetup,
    create_device: CreateDevice,
) -> None:
    """Test the set_fan_timer service with invalid durations."""
    create_device.create(
        {
            "sdm.devices.traits.Fan": {
                "timerMode": "OFF",
            },
            "sdm.devices.traits.ThermostatHvac": {"status": "HEATING"},
            "sdm.devices.traits.ThermostatMode": {
                "availableModes": ["HEAT", "OFF"],
                "mode": "HEAT",
            },
        }
    )
    await setup_platform()

    # Duration too long (over 12 hours)
    with pytest.raises(ValueError, match="must be between 1 and 43200 seconds"):
        await hass.services.async_call(
            DOMAIN,
            "set_fan_timer",
            {
                "entity_id": "climate.my_thermostat",
                "duration": {"hours": 16},
            },
            blocking=True,
        )

    # Duration zero
    with pytest.raises(ValueError, match="must be between 1 and 43200 seconds"):
        await hass.services.async_call(
            DOMAIN,
            "set_fan_timer",
            {
                "entity_id": "climate.my_thermostat",
                "duration": {"seconds": 0},
            },
            blocking=True,
        )


async def test_thermostat_set_fan_when_off(
    hass: HomeAssistant,
    setup_platform: PlatformSetup,
    auth: FakeAuth,
    create_device: CreateDevice,
) -> None:
    """Test a thermostat enabling the fan."""
    create_device.create(
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
        }
    )
    await setup_platform()

    assert len(hass.states.async_all()) == 1
    thermostat = hass.states.get("climate.my_thermostat")
    assert thermostat is not None
    assert thermostat.state == HVACMode.OFF
    assert thermostat.attributes[ATTR_FAN_MODE] == FAN_ON
    assert thermostat.attributes[ATTR_FAN_MODES] == [FAN_ON, FAN_OFF]
    assert thermostat.attributes[ATTR_SUPPORTED_FEATURES] == (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )

    # Fan cannot be turned on when HVAC is off
    with pytest.raises(ValueError):
        await common.async_set_fan_mode(hass, FAN_ON, entity_id="climate.my_thermostat")


async def test_thermostat_fan_empty(
    hass: HomeAssistant,
    setup_platform: PlatformSetup,
    create_device: CreateDevice,
) -> None:
    """Test a fan trait with an empty response."""
    create_device.create(
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
            "sdm.devices.traits.Humidity": {
                "ambientHumidityPercent": 40.6,
            },
        }
    )
    await setup_platform()

    assert len(hass.states.async_all()) == 1
    thermostat = hass.states.get("climate.my_thermostat")
    assert thermostat is not None
    assert thermostat.state == HVACMode.OFF
    assert thermostat.attributes[ATTR_HVAC_ACTION] == HVACAction.OFF
    assert thermostat.attributes[ATTR_CURRENT_HUMIDITY] == 40.6
    assert thermostat.attributes[ATTR_CURRENT_TEMPERATURE] == 16.2
    assert set(thermostat.attributes[ATTR_HVAC_MODES]) == {
        HVACMode.HEAT,
        HVACMode.COOL,
        HVACMode.HEAT_COOL,
        HVACMode.OFF,
    }
    assert ATTR_FAN_MODE not in thermostat.attributes
    assert ATTR_FAN_MODES not in thermostat.attributes
    assert thermostat.attributes[ATTR_SUPPORTED_FEATURES] == (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )

    # Ignores set_fan_mode since it is lacking SUPPORT_FAN_MODE
    await common.async_set_fan_mode(hass, FAN_ON)
    await hass.async_block_till_done()

    assert ATTR_FAN_MODE not in thermostat.attributes
    assert ATTR_FAN_MODES not in thermostat.attributes


async def test_thermostat_invalid_fan_mode(
    hass: HomeAssistant,
    setup_platform: PlatformSetup,
    create_device: CreateDevice,
) -> None:
    """Test setting a fan mode that is not supported."""
    create_device.create(
        {
            "sdm.devices.traits.Fan": {
                "timerMode": "ON",
                "timerTimeout": "2019-05-10T03:22:54Z",
            },
            "sdm.devices.traits.ThermostatHvac": {"status": "OFF"},
            "sdm.devices.traits.ThermostatMode": {
                "availableModes": ["HEAT", "COOL", "HEATCOOL", "OFF"],
                "mode": "COOL",
            },
            "sdm.devices.traits.Temperature": {
                "ambientTemperatureCelsius": 16.2,
            },
            "sdm.devices.traits.Humidity": {
                "ambientHumidityPercent": 40.6,
            },
        }
    )
    await setup_platform()

    assert len(hass.states.async_all()) == 1
    thermostat = hass.states.get("climate.my_thermostat")
    assert thermostat is not None
    assert thermostat.state == HVACMode.COOL
    assert thermostat.attributes[ATTR_HVAC_ACTION] == HVACAction.IDLE
    assert thermostat.attributes[ATTR_CURRENT_HUMIDITY] == 40.6
    assert thermostat.attributes[ATTR_CURRENT_TEMPERATURE] == 16.2
    assert set(thermostat.attributes[ATTR_HVAC_MODES]) == {
        HVACMode.HEAT,
        HVACMode.COOL,
        HVACMode.HEAT_COOL,
        HVACMode.OFF,
    }
    assert thermostat.attributes[ATTR_FAN_MODE] == FAN_ON
    assert thermostat.attributes[ATTR_FAN_MODES] == [FAN_ON, FAN_OFF]

    with pytest.raises(ServiceValidationError):
        await common.async_set_fan_mode(hass, FAN_LOW)


async def test_thermostat_target_temp(
    hass: HomeAssistant,
    setup_platform: PlatformSetup,
    create_device: CreateDevice,
    create_event: CreateEvent,
) -> None:
    """Test a thermostat changing hvac modes and affected on target temps."""
    create_device.create(
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
        }
    )
    await setup_platform()

    assert len(hass.states.async_all()) == 1
    thermostat = hass.states.get("climate.my_thermostat")
    assert thermostat is not None
    assert thermostat.state == HVACMode.HEAT
    assert thermostat.attributes[ATTR_TEMPERATURE] == 23.0
    assert thermostat.attributes[ATTR_TARGET_TEMP_LOW] is None
    assert thermostat.attributes[ATTR_TARGET_TEMP_HIGH] is None

    # Simulate pubsub message changing modes
    await create_event(
        {
            "sdm.devices.traits.ThermostatMode": {
                "availableModes": ["HEAT", "COOL", "HEATCOOL", "OFF"],
                "mode": "HEATCOOL",
            },
            "sdm.devices.traits.ThermostatTemperatureSetpoint": {
                "heatCelsius": 22.0,
                "coolCelsius": 28.0,
            },
        }
    )

    thermostat = hass.states.get("climate.my_thermostat")
    assert thermostat is not None
    assert thermostat.state == HVACMode.HEAT_COOL
    assert thermostat.attributes[ATTR_TARGET_TEMP_LOW] == 22.0
    assert thermostat.attributes[ATTR_TARGET_TEMP_HIGH] == 28.0
    assert thermostat.attributes[ATTR_TEMPERATURE] is None


async def test_thermostat_missing_mode_traits(
    hass: HomeAssistant,
    setup_platform: PlatformSetup,
    create_device: CreateDevice,
) -> None:
    """Test a thermostat missing many thermostat traits in api response."""
    create_device.create(
        {
            "sdm.devices.traits.ThermostatHvac": {"status": "OFF"},
        }
    )
    await setup_platform()

    assert len(hass.states.async_all()) == 1
    thermostat = hass.states.get("climate.my_thermostat")
    assert thermostat is not None
    assert thermostat.state == HVACMode.OFF
    assert thermostat.attributes[ATTR_HVAC_ACTION] == HVACAction.OFF
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


async def test_thermostat_missing_temperature_trait(
    hass: HomeAssistant,
    setup_platform: PlatformSetup,
    create_device: CreateDevice,
) -> None:
    """Test a thermostat missing many thermostat traits in api response."""
    create_device.create(
        {
            "sdm.devices.traits.ThermostatHvac": {"status": "OFF"},
            "sdm.devices.traits.ThermostatMode": {
                "availableModes": ["HEAT", "COOL", "HEATCOOL", "OFF"],
                "mode": "HEAT",
            },
        }
    )
    await setup_platform()

    assert len(hass.states.async_all()) == 1
    thermostat = hass.states.get("climate.my_thermostat")
    assert thermostat is not None
    assert thermostat.state == HVACMode.HEAT
    assert thermostat.attributes[ATTR_HVAC_ACTION] == HVACAction.IDLE
    assert thermostat.attributes[ATTR_CURRENT_TEMPERATURE] is None
    assert set(thermostat.attributes[ATTR_HVAC_MODES]) == {
        HVACMode.HEAT,
        HVACMode.COOL,
        HVACMode.HEAT_COOL,
        HVACMode.OFF,
    }
    assert thermostat.attributes[ATTR_TEMPERATURE] is None
    assert thermostat.attributes[ATTR_TARGET_TEMP_LOW] is None
    assert thermostat.attributes[ATTR_TARGET_TEMP_HIGH] is None
    assert ATTR_PRESET_MODE not in thermostat.attributes
    assert ATTR_PRESET_MODES not in thermostat.attributes
    assert ATTR_FAN_MODE not in thermostat.attributes
    assert ATTR_FAN_MODES not in thermostat.attributes

    with pytest.raises(HomeAssistantError) as e_info:
        await common.async_set_temperature(hass, temperature=24.0)
    await hass.async_block_till_done()
    assert "temperature" in str(e_info)
    assert "climate.my_thermostat" in str(e_info)
    assert "24.0" in str(e_info)
    assert thermostat.attributes[ATTR_TEMPERATURE] is None


async def test_thermostat_unexpected_hvac_status(
    hass: HomeAssistant,
    setup_platform: PlatformSetup,
    create_device: CreateDevice,
) -> None:
    """Test a thermostat missing many thermostat traits in api response."""
    create_device.create(
        {
            "sdm.devices.traits.ThermostatHvac": {"status": "UNEXPECTED"},
        }
    )
    await setup_platform()

    assert len(hass.states.async_all()) == 1
    thermostat = hass.states.get("climate.my_thermostat")
    assert thermostat is not None
    assert thermostat.state == HVACMode.OFF
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

    with pytest.raises(ServiceValidationError):
        await common.async_set_hvac_mode(hass, HVACMode.DRY)
    assert thermostat.state == HVACMode.OFF


async def test_thermostat_missing_set_point(
    hass: HomeAssistant,
    setup_platform: PlatformSetup,
    create_device: CreateDevice,
) -> None:
    """Test a thermostat missing many thermostat traits in api response."""
    create_device.create(
        {
            "sdm.devices.traits.ThermostatHvac": {"status": "OFF"},
            "sdm.devices.traits.ThermostatMode": {
                "availableModes": ["HEAT", "COOL", "HEATCOOL", "OFF"],
                "mode": "HEATCOOL",
            },
        },
    )
    await setup_platform()

    assert len(hass.states.async_all()) == 1
    thermostat = hass.states.get("climate.my_thermostat")
    assert thermostat is not None
    assert thermostat.state == HVACMode.HEAT_COOL
    assert thermostat.attributes[ATTR_HVAC_ACTION] == HVACAction.IDLE
    assert thermostat.attributes[ATTR_CURRENT_TEMPERATURE] is None
    assert set(thermostat.attributes[ATTR_HVAC_MODES]) == {
        HVACMode.HEAT,
        HVACMode.COOL,
        HVACMode.HEAT_COOL,
        HVACMode.OFF,
    }
    assert thermostat.attributes[ATTR_TEMPERATURE] is None
    assert thermostat.attributes[ATTR_TARGET_TEMP_LOW] is None
    assert thermostat.attributes[ATTR_TARGET_TEMP_HIGH] is None
    assert ATTR_PRESET_MODE not in thermostat.attributes
    assert ATTR_PRESET_MODES not in thermostat.attributes
    assert ATTR_FAN_MODE not in thermostat.attributes
    assert ATTR_FAN_MODES not in thermostat.attributes


async def test_thermostat_unexepected_hvac_mode(
    hass: HomeAssistant,
    setup_platform: PlatformSetup,
    create_device: CreateDevice,
) -> None:
    """Test a thermostat missing many thermostat traits in api response."""
    create_device.create(
        {
            "sdm.devices.traits.ThermostatHvac": {"status": "OFF"},
            "sdm.devices.traits.ThermostatMode": {
                "availableModes": ["HEAT", "COOL", "HEATCOOL", "OFF", "UNEXPECTED"],
                "mode": "UNEXPECTED",
            },
        }
    )
    await setup_platform()

    assert len(hass.states.async_all()) == 1
    thermostat = hass.states.get("climate.my_thermostat")
    assert thermostat is not None
    assert thermostat.state == HVACMode.OFF
    assert thermostat.attributes[ATTR_HVAC_ACTION] == HVACAction.OFF
    assert thermostat.attributes[ATTR_CURRENT_TEMPERATURE] is None
    assert set(thermostat.attributes[ATTR_HVAC_MODES]) == {
        HVACMode.HEAT,
        HVACMode.COOL,
        HVACMode.HEAT_COOL,
        HVACMode.OFF,
    }
    assert thermostat.attributes[ATTR_TEMPERATURE] is None
    assert thermostat.attributes[ATTR_TARGET_TEMP_LOW] is None
    assert thermostat.attributes[ATTR_TARGET_TEMP_HIGH] is None
    assert ATTR_PRESET_MODE not in thermostat.attributes
    assert ATTR_PRESET_MODES not in thermostat.attributes
    assert ATTR_FAN_MODE not in thermostat.attributes
    assert ATTR_FAN_MODES not in thermostat.attributes


async def test_thermostat_invalid_set_preset_mode(
    hass: HomeAssistant,
    setup_platform: PlatformSetup,
    auth: FakeAuth,
    create_device: CreateDevice,
) -> None:
    """Test a thermostat set with an invalid preset mode."""
    create_device.create(
        {
            "sdm.devices.traits.ThermostatHvac": {"status": "OFF"},
            "sdm.devices.traits.ThermostatEco": {
                "availableModes": ["MANUAL_ECO", "OFF"],
                "mode": "OFF",
                "heatCelsius": 15.0,
                "coolCelsius": 28.0,
            },
        }
    )
    await setup_platform()

    assert len(hass.states.async_all()) == 1
    thermostat = hass.states.get("climate.my_thermostat")
    assert thermostat is not None
    assert thermostat.state == HVACMode.OFF
    assert thermostat.attributes[ATTR_PRESET_MODE] == PRESET_NONE
    assert thermostat.attributes[ATTR_PRESET_MODES] == [PRESET_ECO, PRESET_NONE]

    # Set preset mode that is invalid
    with pytest.raises(ServiceValidationError):
        await common.async_set_preset_mode(hass, PRESET_SLEEP)

    # No RPC sent
    assert auth.method is None

    # Preset is unchanged
    assert thermostat.attributes[ATTR_PRESET_MODE] == PRESET_NONE
    assert thermostat.attributes[ATTR_PRESET_MODES] == [PRESET_ECO, PRESET_NONE]


async def test_thermostat_hvac_mode_failure(
    hass: HomeAssistant,
    setup_platform: PlatformSetup,
    auth: FakeAuth,
    create_device: CreateDevice,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test setting an hvac_mode that is not supported."""
    create_device.create(
        {
            "sdm.devices.traits.ThermostatHvac": {"status": "OFF"},
            "sdm.devices.traits.ThermostatMode": {
                "availableModes": ["HEAT", "COOL", "HEATCOOL", "OFF"],
                "mode": "COOL",
            },
            "sdm.devices.traits.ThermostatTemperatureSetpoint": {
                "coolCelsius": 25.0,
            },
            "sdm.devices.traits.Fan": {
                "timerMode": "OFF",
                "timerTimeout": "2019-05-10T03:22:54Z",
            },
            "sdm.devices.traits.ThermostatEco": {
                "availableModes": ["MANUAL_ECO", "OFF"],
                "mode": "OFF",
                "heatCelsius": 15.0,
                "coolCelsius": 28.0,
            },
        }
    )
    await setup_platform()

    assert len(hass.states.async_all()) == 1
    thermostat = hass.states.get("climate.my_thermostat")
    assert thermostat is not None
    assert thermostat.state == HVACMode.COOL
    assert thermostat.attributes[ATTR_HVAC_ACTION] == HVACAction.IDLE

    auth.responses = [aiohttp.web.Response(status=HTTPStatus.BAD_REQUEST)]
    with pytest.raises(HomeAssistantError) as e_info:
        await common.async_set_hvac_mode(hass, HVACMode.HEAT)
    assert "HVAC mode" in str(e_info)
    assert "climate.my_thermostat" in str(e_info)
    assert HVACMode.HEAT in str(e_info)

    auth.responses = [aiohttp.web.Response(status=HTTPStatus.BAD_REQUEST)]
    await common.async_set_temperature(hass, temperature=25.0)
    await async_fire_temperature_debounce(hass)
    assert (
        "Error sending debounced temperature command for climate.my_thermostat"
        in caplog.text
    )

    auth.responses = [aiohttp.web.Response(status=HTTPStatus.BAD_REQUEST)]
    with pytest.raises(HomeAssistantError) as e_info:
        await common.async_set_fan_mode(hass, FAN_ON)
    assert "fan mode" in str(e_info)
    assert "climate.my_thermostat" in str(e_info)
    assert FAN_ON in str(e_info)

    auth.responses = [aiohttp.web.Response(status=HTTPStatus.BAD_REQUEST)]
    with pytest.raises(HomeAssistantError) as e_info:
        await common.async_set_preset_mode(hass, PRESET_ECO)
    assert "preset mode" in str(e_info)
    assert "climate.my_thermostat" in str(e_info)
    assert PRESET_ECO in str(e_info)


async def test_thermostat_available(
    hass: HomeAssistant, setup_platform: PlatformSetup, create_device: CreateDevice
) -> None:
    """Test a thermostat that is available."""
    create_device.create(
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
            "sdm.devices.traits.Connectivity": {"status": "ONLINE"},
        },
    )
    await setup_platform()

    assert len(hass.states.async_all()) == 1
    thermostat = hass.states.get("climate.my_thermostat")
    assert thermostat is not None
    assert thermostat.state == HVACMode.COOL


async def test_thermostat_unavailable(
    hass: HomeAssistant, setup_platform: PlatformSetup, create_device: CreateDevice
) -> None:
    """Test a thermostat that is unavailable."""
    create_device.create(
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
            "sdm.devices.traits.Connectivity": {"status": "OFFLINE"},
        },
    )
    await setup_platform()

    assert len(hass.states.async_all()) == 1
    thermostat = hass.states.get("climate.my_thermostat")
    assert thermostat is not None
    assert thermostat.state == STATE_UNAVAILABLE
