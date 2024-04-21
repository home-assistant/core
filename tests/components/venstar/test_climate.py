"""The climate tests for the venstar integration."""

from unittest.mock import patch

from homeassistant.components.climate import ClimateEntityFeature
from homeassistant.core import HomeAssistant

from .util import async_init_integration, mock_venstar_devices

EXPECTED_BASE_SUPPORTED_FEATURES = (
    ClimateEntityFeature.TARGET_TEMPERATURE
    | ClimateEntityFeature.FAN_MODE
    | ClimateEntityFeature.PRESET_MODE
    | ClimateEntityFeature.TURN_OFF
    | ClimateEntityFeature.TURN_ON
)


@mock_venstar_devices
async def test_colortouch(hass: HomeAssistant) -> None:
    """Test interfacing with a venstar colortouch with attached humidifier."""

    with patch("homeassistant.components.venstar.VENSTAR_SLEEP", new=0):
        await async_init_integration(hass)

    state = hass.states.get("climate.colortouch")
    assert state.state == "heat"

    expected_attributes = {
        "hvac_modes": ["heat", "cool", "off", "auto"],
        "min_temp": 7,
        "max_temp": 35,
        "min_humidity": 0,
        "max_humidity": 60,
        "fan_modes": ["on", "auto"],
        "preset_modes": ["none", "away", "temperature"],
        "current_temperature": 21.0,
        "temperature": 20.5,
        "current_humidity": 41,
        "humidity": 30,
        "fan_mode": "auto",
        "hvac_action": "idle",
        "preset_mode": "temperature",
        "fan_state": 0,
        "hvac_mode": 0,
        "friendly_name": "COLORTOUCH",
        "supported_features": EXPECTED_BASE_SUPPORTED_FEATURES
        | ClimateEntityFeature.TARGET_HUMIDITY,
    }
    # Only test for a subset of attributes in case
    # HA changes the implementation and a new one appears
    assert all(item in state.attributes.items() for item in expected_attributes.items())


@mock_venstar_devices
async def test_t2000(hass: HomeAssistant) -> None:
    """Test interfacing with a venstar T2000 presently turned off."""

    with patch("homeassistant.components.venstar.VENSTAR_SLEEP", new=0):
        await async_init_integration(hass)

    state = hass.states.get("climate.t2000")
    assert state.state == "off"

    expected_attributes = {
        "hvac_modes": ["heat", "cool", "off", "auto"],
        "min_temp": 7,
        "max_temp": 35,
        "fan_modes": ["on", "auto"],
        "preset_modes": ["none", "away", "temperature"],
        "current_temperature": 14.0,
        "temperature": None,
        "fan_mode": "auto",
        "hvac_action": "idle",
        "preset_mode": "temperature",
        "fan_state": 0,
        "hvac_mode": 0,
        "friendly_name": "T2000",
        "supported_features": EXPECTED_BASE_SUPPORTED_FEATURES,
    }
    # Only test for a subset of attributes in case
    # HA changes the implementation and a new one appears
    assert all(item in state.attributes.items() for item in expected_attributes.items())
