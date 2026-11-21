"""Test EcoNet thermostat states and controls."""

from collections.abc import Awaitable, Callable
from unittest.mock import MagicMock, call

from pyeconet.equipment import Equipment
import pytest

from homeassistant.components import climate
from homeassistant.components.climate import ClimateEntityFeature, HVACMode
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM

pytestmark = [
    pytest.mark.parametrize("platform", [Platform.CLIMATE]),
    pytest.mark.parametrize("equipment_data", ["thermostat_controls"], indirect=True),
]

ENTITY_ID = "climate.thermostat"


@pytest.fixture(autouse=True)
def use_fahrenheit(hass: HomeAssistant) -> None:
    """Use the thermostat's native temperature unit for state and service tests."""
    hass.config.units = US_CUSTOMARY_SYSTEM


@pytest.mark.parametrize(
    ("mode", "expected_mode", "temperature", "low", "high"),
    [
        pytest.param(0, HVACMode.OFF, None, None, None, id="off"),
        pytest.param(1, HVACMode.HEAT, 68, None, None, id="heat"),
        pytest.param(2, HVACMode.COOL, 76, None, None, id="cool"),
        pytest.param(3, HVACMode.HEAT_COOL, None, 68, 76, id="auto"),
        pytest.param(4, HVACMode.FAN_ONLY, None, None, None, id="fan_only"),
        pytest.param(5, HVACMode.HEAT, 68, None, None, id="emergency_heat"),
    ],
)
async def test_thermostat_state(
    hass: HomeAssistant,
    setup_integration: Callable[[], Awaitable[None]],
    equipment_data: dict,
    mode: int,
    expected_mode: HVACMode,
    temperature: int | None,
    low: int | None,
    high: int | None,
) -> None:
    """Expose thermostat modes, temperatures, fan speeds, and humidity."""
    equipment_data["@MODE"]["value"] = mode
    await setup_integration()

    state = hass.states.get(ENTITY_ID)
    assert state.state == expected_mode
    assert state.attributes[ATTR_TEMPERATURE] == temperature
    assert state.attributes[climate.ATTR_TARGET_TEMP_LOW] == low
    assert state.attributes[climate.ATTR_TARGET_TEMP_HIGH] == high
    assert state.attributes[climate.ATTR_CURRENT_TEMPERATURE] == 73
    assert state.attributes[climate.ATTR_CURRENT_HUMIDITY] == 45
    assert state.attributes[climate.ATTR_HUMIDITY] == 50
    assert state.attributes[climate.ATTR_MIN_HUMIDITY] == 30
    assert state.attributes[climate.ATTR_MAX_HUMIDITY] == 60
    assert state.attributes[climate.ATTR_HVAC_MODES] == [
        HVACMode.OFF,
        HVACMode.HEAT,
        HVACMode.COOL,
        HVACMode.HEAT_COOL,
        HVACMode.FAN_ONLY,
    ]
    assert state.attributes[climate.ATTR_FAN_MODES] == [
        climate.FAN_AUTO,
        climate.FAN_LOW,
        climate.FAN_MEDIUM,
        climate.FAN_HIGH,
        climate.FAN_TOP,
    ]
    assert state.attributes[climate.ATTR_FAN_MODE] == climate.FAN_AUTO


@pytest.mark.parametrize("speed", [2, 4], ids=["medium_low", "medium_high"])
async def test_medium_fan_speed(
    hass: HomeAssistant,
    setup_integration: Callable[[], Awaitable[None]],
    equipment_data: dict,
    speed: int,
) -> None:
    """Map the intermediate fan speeds to Home Assistant's medium speed."""
    equipment_data["@FANSPEED"]["value"] = speed
    await setup_integration()
    assert (
        hass.states.get(ENTITY_ID).attributes[climate.ATTR_FAN_MODE]
        == climate.FAN_MEDIUM
    )


async def test_no_humidifier(
    hass: HomeAssistant,
    setup_integration: Callable[[], Awaitable[None]],
    equipment_data: dict,
) -> None:
    """Do not advertise humidity control when the device does not support it."""
    del equipment_data["@DEHUMENABLE"]
    await setup_integration()
    state = hass.states.get(ENTITY_ID)
    assert (
        not state.attributes["supported_features"]
        & ClimateEntityFeature.TARGET_HUMIDITY
    )
    assert climate.ATTR_HUMIDITY not in state.attributes


@pytest.mark.parametrize(
    ("service", "service_data", "payload"),
    [
        pytest.param(
            climate.SERVICE_SET_HVAC_MODE,
            {climate.ATTR_HVAC_MODE: HVACMode.COOL},
            {"@MODE": 2},
            id="mode",
        ),
        pytest.param(
            climate.SERVICE_SET_FAN_MODE,
            {climate.ATTR_FAN_MODE: climate.FAN_HIGH},
            {"@FANSPEED": 5},
            id="fan",
        ),
        pytest.param(
            climate.SERVICE_SET_HUMIDITY,
            {climate.ATTR_HUMIDITY: 55},
            {"@DEHUMSETPOINT": 55},
            id="humidity",
        ),
        pytest.param(
            climate.SERVICE_SET_TEMPERATURE,
            {ATTR_TEMPERATURE: 70},
            {"@HEATSETPOINT": 70},
            id="temperature",
        ),
    ],
)
async def test_thermostat_controls(
    hass: HomeAssistant,
    setup_integration: Callable[[], Awaitable[None]],
    mock_api: MagicMock,
    service: str,
    service_data: dict,
    payload: dict,
) -> None:
    """Send thermostat service calls to the library's API."""
    await setup_integration()
    await hass.services.async_call(
        climate.DOMAIN,
        service,
        {ATTR_ENTITY_ID: ENTITY_ID, **service_data},
        blocking=True,
    )
    mock_api.publish.assert_called_once_with(payload, "thermostat_1", "serial_2")


async def test_temperature_range(
    hass: HomeAssistant,
    setup_integration: Callable[[], Awaitable[None]],
    equipment_data: dict,
    mock_api: MagicMock,
) -> None:
    """Send both setpoints when setting the automatic mode temperature range."""
    equipment_data["@MODE"]["value"] = 3
    await setup_integration()
    await hass.services.async_call(
        climate.DOMAIN,
        climate.SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            climate.ATTR_TARGET_TEMP_LOW: 65,
            climate.ATTR_TARGET_TEMP_HIGH: 78,
        },
        blocking=True,
    )
    assert mock_api.publish.call_args_list == [
        call({"@COOLSETPOINT": 78}, "thermostat_1", "serial_2"),
        call({"@HEATSETPOINT": 65}, "thermostat_1", "serial_2"),
    ]


async def test_thermostat_update(
    hass: HomeAssistant,
    setup_integration: Callable[[], Awaitable[None]],
    mock_equipment: Equipment,
) -> None:
    """Apply thermostat state changes received from MQTT."""
    await setup_integration()
    mock_equipment.update_equipment_info(
        {"device_name": "thermostat_1", "@SETPOINT": {"value": 74}}
    )
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).attributes[climate.ATTR_CURRENT_TEMPERATURE] == 74
