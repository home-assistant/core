"""Test generic_thermostat restore state."""
import pytest

from homeassistant import core as ha
from homeassistant.components import input_boolean
from homeassistant.components.climate import (
    ATTR_PRESET_MODE,
    DOMAIN,
    PRESET_AWAY,
    PRESET_NONE,
    HVACMode,
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
)
from homeassistant.core import DOMAIN as HASS_DOMAIN, CoreState, HomeAssistant, State
from homeassistant.setup import async_setup_component

from tests.common import async_mock_service, mock_restore_cache
from tests.components.generic_thermostat.const import ENT_SENSOR, ENT_SWITCH, ENTITY
from tests.components.generic_thermostat.shared import _setup_sensor, _setup_switch


@pytest.mark.parametrize("hvac_mode", [HVACMode.OFF, HVACMode.HEAT, HVACMode.COOL])
async def test_restore_state(hass: HomeAssistant, hvac_mode) -> None:
    """Ensure states are restored on startup."""
    mock_restore_cache(
        hass,
        (
            State(
                "climate.test_thermostat",
                hvac_mode,
                {ATTR_TEMPERATURE: "20", ATTR_PRESET_MODE: PRESET_AWAY},
            ),
        ),
    )

    hass.state = CoreState.starting

    await async_setup_component(
        hass,
        DOMAIN,
        {
            "climate": {
                "platform": "generic_thermostat",
                "name": "test_thermostat",
                "heater": ENT_SWITCH,
                "target_sensor": ENT_SENSOR,
                "away_temp": 14,
            }
        },
    )
    await hass.async_block_till_done()
    state = hass.states.get("climate.test_thermostat")
    assert state.attributes[ATTR_TEMPERATURE] == 20
    assert state.attributes[ATTR_PRESET_MODE] == PRESET_AWAY
    assert state.state == hvac_mode


async def test_no_restore_state(hass: HomeAssistant) -> None:
    """Ensure states are restored on startup if they exist.

    Allows for graceful reboot.
    """
    mock_restore_cache(
        hass,
        (
            State(
                "climate.test_thermostat",
                HVACMode.OFF,
                {ATTR_TEMPERATURE: "20", ATTR_PRESET_MODE: PRESET_AWAY},
            ),
        ),
    )

    hass.state = CoreState.starting

    await async_setup_component(
        hass,
        DOMAIN,
        {
            "climate": {
                "platform": "generic_thermostat",
                "name": "test_thermostat",
                "heater": ENT_SWITCH,
                "target_sensor": ENT_SENSOR,
                "target_temp": 22,
            }
        },
    )
    await hass.async_block_till_done()
    state = hass.states.get("climate.test_thermostat")
    assert state.attributes[ATTR_TEMPERATURE] == 22
    assert state.state == HVACMode.OFF


async def test_restore_will_turn_off_(hass: HomeAssistant) -> None:
    """Ensure that restored state is coherent with real situation.

    Thermostat status must trigger heater event if temp raises the target .
    """
    heater_switch = "input_boolean.test"
    mock_restore_cache(
        hass,
        (
            State(
                "climate.test_thermostat",
                HVACMode.HEAT,
                {ATTR_TEMPERATURE: "18", ATTR_PRESET_MODE: PRESET_NONE},
            ),
            State(heater_switch, STATE_ON, {}),
        ),
    )

    hass.state = CoreState.starting

    assert await async_setup_component(
        hass, input_boolean.DOMAIN, {"input_boolean": {"test": None}}
    )
    await hass.async_block_till_done()
    assert hass.states.get(heater_switch).state == STATE_ON

    _setup_sensor(hass, 22)

    await async_setup_component(
        hass,
        DOMAIN,
        {
            "climate": {
                "platform": "generic_thermostat",
                "name": "test_thermostat",
                "heater": heater_switch,
                "target_sensor": ENT_SENSOR,
                "target_temp": 20,
            }
        },
    )
    await hass.async_block_till_done()
    state = hass.states.get("climate.test_thermostat")
    assert state.attributes[ATTR_TEMPERATURE] == 20
    assert state.state == HVACMode.HEAT
    assert hass.states.get(heater_switch).state == STATE_ON


async def test_restore_will_turn_off_when_loaded_second(hass: HomeAssistant) -> None:
    """Ensure that restored state is coherent with real situation.

    Switch is not available until after component is loaded
    """
    heater_switch = "input_boolean.test"
    mock_restore_cache(
        hass,
        (
            State(
                "climate.test_thermostat",
                HVACMode.HEAT,
                {ATTR_TEMPERATURE: "18", ATTR_PRESET_MODE: PRESET_NONE},
            ),
            State(heater_switch, STATE_ON, {}),
        ),
    )

    hass.state = CoreState.starting

    await hass.async_block_till_done()
    assert hass.states.get(heater_switch) is None

    _setup_sensor(hass, 16)

    await async_setup_component(
        hass,
        DOMAIN,
        {
            "climate": {
                "platform": "generic_thermostat",
                "name": "test_thermostat",
                "heater": heater_switch,
                "target_sensor": ENT_SENSOR,
                "target_temp": 20,
                "initial_hvac_mode": HVACMode.OFF,
            }
        },
    )
    await hass.async_block_till_done()
    state = hass.states.get("climate.test_thermostat")
    assert state.attributes[ATTR_TEMPERATURE] == 20
    assert state.state == HVACMode.OFF

    calls_on = async_mock_service(hass, ha.DOMAIN, SERVICE_TURN_ON)
    calls_off = async_mock_service(hass, ha.DOMAIN, SERVICE_TURN_OFF)

    assert await async_setup_component(
        hass, input_boolean.DOMAIN, {"input_boolean": {"test": None}}
    )
    await hass.async_block_till_done()
    # heater must be switched off
    assert len(calls_on) == 0
    assert len(calls_off) == 1
    call = calls_off[0]
    assert call.domain == HASS_DOMAIN
    assert call.service == SERVICE_TURN_OFF
    assert call.data["entity_id"] == "input_boolean.test"


async def test_restore_state_uncoherence_case(hass: HomeAssistant) -> None:
    """Test restore from a strange state.

    - Turn the generic thermostat off
    - Restart HA and restore state from DB
    """
    _mock_restore_cache(hass, temperature=20)

    calls = _setup_switch(hass, False)
    _setup_sensor(hass, 15)
    await _setup_climate(hass)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY)
    assert state.attributes[ATTR_TEMPERATURE] == 20
    assert state.state == HVACMode.OFF
    assert len(calls) == 0

    calls = _setup_switch(hass, False)
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY)
    assert state.state == HVACMode.OFF


async def _setup_climate(hass):
    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            "climate": {
                "platform": "generic_thermostat",
                "name": "test",
                "cold_tolerance": 2,
                "hot_tolerance": 4,
                "away_temp": 30,
                "heater": ENT_SWITCH,
                "target_sensor": ENT_SENSOR,
                "ac_mode": True,
            }
        },
    )


def _mock_restore_cache(hass, temperature=20, hvac_mode=HVACMode.OFF):
    mock_restore_cache(
        hass,
        (
            State(
                ENTITY,
                hvac_mode,
                {ATTR_TEMPERATURE: str(temperature), ATTR_PRESET_MODE: PRESET_AWAY},
            ),
        ),
    )
