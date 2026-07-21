"""Tests for Poolside TEMPERATURE controls exposed as climate entities."""

import pytest

from homeassistant.components.climate import (
    ATTR_CURRENT_TEMPERATURE,
    ATTR_TEMPERATURE,
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_TEMPERATURE,
    HVACMode,
)
from homeassistant.components.poolside.const import ControlType
from homeassistant.components.poolside.models import PoolsideControl
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF
from homeassistant.core import HomeAssistant
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM

from .conftest import TEST_BODY_OF_WATER_UUID, FakePoolsideClient, make_control

HEATER_UUID = "heater-1"
ENTITY_ID = "climate.pool_heater"


@pytest.fixture
def controls(hass: HomeAssistant) -> list[PoolsideControl]:
    """A single TEMPERATURE control.

    Uses imperial units so the entity's Fahrenheit native unit matches the
    test hass's unit system and service calls need no conversion.
    """
    hass.config.units = US_CUSTOMARY_SYSTEM
    return [
        make_control(
            HEATER_UUID,
            "Heater",
            ControlType.TEMPERATURE,
            MinSetPoint=40,
            MaxSetPoint=104,
        )
    ]


@pytest.mark.usefixtures("setup_integration")
async def test_state_reflects_status(
    hass: HomeAssistant,
    fake_client: FakePoolsideClient,
) -> None:
    """Status/SetPoint/ControlMode are optimistic; Temperature is confirmed by the body."""
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF

    # Optimistic desired-state fields are keyed by the control's own UUID.
    fake_client.set_status(HEATER_UUID, "Status", "ON")
    fake_client.set_status(HEATER_UUID, "SetPoint", 88)
    # Confirmed body telemetry is keyed by the group's BodyOfWaterUUID.
    fake_client.set_status(TEST_BODY_OF_WATER_UUID, "Temperature", 79)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == HVACMode.HEAT
    assert state.attributes[ATTR_TEMPERATURE] == 88
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 79


@pytest.mark.usefixtures("setup_integration")
async def test_state_tolerates_stringly_typed_temperatures(
    hass: HomeAssistant,
    fake_client: FakePoolsideClient,
) -> None:
    """Temperature/SetPoint values may arrive as strings; they must still render."""
    fake_client.set_status(HEATER_UUID, "SetPoint", "88")
    fake_client.set_status(TEST_BODY_OF_WATER_UUID, "Temperature", "76")
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes[ATTR_TEMPERATURE] == 88.0
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 76.0


@pytest.mark.usefixtures("setup_integration")
async def test_hvac_modes_built_from_body_capabilities(
    hass: HomeAssistant,
    fake_client: FakePoolsideClient,
) -> None:
    """hvac_modes reflects the body's confirmed ControlModesSupported, not a fixed list."""
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes["hvac_modes"] == [HVACMode.OFF, HVACMode.HEAT]

    fake_client.set_status(
        TEST_BODY_OF_WATER_UUID, "ControlModesSupported", ["HEAT", "COOL", "AUTO"]
    )
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert set(state.attributes["hvac_modes"]) == {
        HVACMode.OFF,
        HVACMode.HEAT,
        HVACMode.COOL,
        HVACMode.HEAT_COOL,
    }


@pytest.mark.usefixtures("setup_integration")
async def test_set_hvac_mode_heat(
    hass: HomeAssistant,
    fake_client: FakePoolsideClient,
) -> None:
    """Setting HVAC mode to heat writes Status and the matching ControlMode."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, "hvac_mode": HVACMode.HEAT},
        blocking=True,
    )
    fake_client.async_set_desired_state.assert_awaited_with(
        HEATER_UUID, Status="ON", ControlMode="HEAT"
    )


@pytest.mark.usefixtures("setup_integration")
async def test_set_hvac_mode_off(
    hass: HomeAssistant,
    fake_client: FakePoolsideClient,
) -> None:
    """Setting HVAC mode to off writes only Status=OFF."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, "hvac_mode": HVACMode.OFF},
        blocking=True,
    )
    fake_client.async_set_desired_state.assert_awaited_with(HEATER_UUID, Status="OFF")


@pytest.mark.usefixtures("setup_integration")
async def test_set_temperature_writes_integer_setpoint(
    hass: HomeAssistant,
    fake_client: FakePoolsideClient,
) -> None:
    """Setting the target temperature writes an integer-string SetPoint."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: 90.4},
        blocking=True,
    )
    fake_client.async_set_desired_state.assert_awaited_with(HEATER_UUID, SetPoint="90")


@pytest.mark.usefixtures("setup_integration")
async def test_disabled_control_is_unavailable(
    hass: HomeAssistant,
    fake_client: FakePoolsideClient,
) -> None:
    """A control reporting Status=DISABLED becomes unavailable."""
    fake_client.set_status(HEATER_UUID, "Status", "DISABLED")
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == "unavailable"
