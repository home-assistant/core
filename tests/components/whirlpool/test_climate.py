"""Test the Whirlpool Sixth Sense climate domain."""

from unittest.mock import MagicMock

import pytest
from syrupy import SnapshotAssertion
import whirlpool

from homeassistant.components.climate import (
    ATTR_CURRENT_HUMIDITY,
    ATTR_CURRENT_TEMPERATURE,
    ATTR_FAN_MODE,
    ATTR_HVAC_MODE,
    ATTR_SWING_MODE,
    DOMAIN as CLIMATE_DOMAIN,
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_MIDDLE,
    FAN_OFF,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_SWING_MODE,
    SERVICE_SET_TEMPERATURE,
    SWING_HORIZONTAL,
    SWING_OFF,
    HVACMode,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er

from . import init_integration, snapshot_whirlpool_entities, trigger_attr_callback


@pytest.fixture(
    params=[
        ("climate.aircon_said1", "mock_aircon1_api"),
        ("climate.aircon_said2", "mock_aircon2_api"),
    ]
)
def multiple_climate_entities(request: pytest.FixtureRequest) -> tuple[str, str]:
    """Fixture for multiple climate entities."""
    entity_id, mock_fixture = request.param
    return entity_id, mock_fixture


async def update_ac_state(
    hass: HomeAssistant,
    entity_id: str,
    mock_aircon_api_instance: MagicMock,
):
    """Simulate an update trigger from the API."""
    await trigger_attr_callback(hass, mock_aircon_api_instance)
    return hass.states.get(entity_id)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    await init_integration(hass)
    snapshot_whirlpool_entities(hass, entity_registry, snapshot, Platform.CLIMATE)


async def test_dynamic_attributes(
    hass: HomeAssistant,
    multiple_climate_entities: tuple[str, str],
    request: pytest.FixtureRequest,
) -> None:
    """Test dynamic attributes."""
    entity_id, mock_fixture = multiple_climate_entities
    mock_instance = request.getfixturevalue(mock_fixture)
    await init_integration(hass)

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == HVACMode.COOL

    mock_instance.get_power_on.return_value = False
    state = await update_ac_state(hass, entity_id, mock_instance)
    assert state.state == HVACMode.OFF

    mock_instance.get_online.return_value = False
    state = await update_ac_state(hass, entity_id, mock_instance)
    assert state.state == STATE_UNAVAILABLE

    mock_instance.get_power_on.return_value = True
    mock_instance.get_online.return_value = True
    state = await update_ac_state(hass, entity_id, mock_instance)
    assert state.state == HVACMode.COOL

    mock_instance.get_mode.return_value = whirlpool.aircon.Mode.Heat
    state = await update_ac_state(hass, entity_id, mock_instance)
    assert state.state == HVACMode.HEAT

    mock_instance.get_mode.return_value = whirlpool.aircon.Mode.Fan
    state = await update_ac_state(hass, entity_id, mock_instance)
    assert state.state == HVACMode.FAN_ONLY

    mock_instance.get_fanspeed.return_value = whirlpool.aircon.FanSpeed.Auto
    state = await update_ac_state(hass, entity_id, mock_instance)
    assert state.attributes[ATTR_FAN_MODE] == HVACMode.AUTO

    mock_instance.get_fanspeed.return_value = whirlpool.aircon.FanSpeed.Low
    state = await update_ac_state(hass, entity_id, mock_instance)
    assert state.attributes[ATTR_FAN_MODE] == FAN_LOW

    mock_instance.get_fanspeed.return_value = whirlpool.aircon.FanSpeed.Medium
    state = await update_ac_state(hass, entity_id, mock_instance)
    assert state.attributes[ATTR_FAN_MODE] == FAN_MEDIUM

    mock_instance.get_fanspeed.return_value = whirlpool.aircon.FanSpeed.High
    state = await update_ac_state(hass, entity_id, mock_instance)
    assert state.attributes[ATTR_FAN_MODE] == FAN_HIGH

    mock_instance.get_fanspeed.return_value = whirlpool.aircon.FanSpeed.Off
    state = await update_ac_state(hass, entity_id, mock_instance)
    assert state.attributes[ATTR_FAN_MODE] == FAN_OFF

    mock_instance.get_current_temp.return_value = 15
    mock_instance.get_temp.return_value = 20
    mock_instance.get_current_humidity.return_value = 80
    mock_instance.get_h_louver_swing.return_value = True
    attributes = (await update_ac_state(hass, entity_id, mock_instance)).attributes
    assert attributes[ATTR_CURRENT_TEMPERATURE] == 15
    assert attributes[ATTR_TEMPERATURE] == 20
    assert attributes[ATTR_CURRENT_HUMIDITY] == 80
    assert attributes[ATTR_SWING_MODE] == SWING_HORIZONTAL

    mock_instance.get_current_temp.return_value = 16
    mock_instance.get_temp.return_value = 21
    mock_instance.get_current_humidity.return_value = 70
    mock_instance.get_h_louver_swing.return_value = False
    attributes = (await update_ac_state(hass, entity_id, mock_instance)).attributes
    assert attributes[ATTR_CURRENT_TEMPERATURE] == 16
    assert attributes[ATTR_TEMPERATURE] == 21
    assert attributes[ATTR_CURRENT_HUMIDITY] == 70
    assert attributes[ATTR_SWING_MODE] == SWING_OFF


@pytest.mark.parametrize(
    ("service", "service_data", "expected_call", "expected_args"),
    [
        (SERVICE_TURN_OFF, {}, "set_power_on", [False]),
        (SERVICE_TURN_ON, {}, "set_power_on", [True]),
        (
            SERVICE_SET_HVAC_MODE,
            {ATTR_HVAC_MODE: HVACMode.COOL},
            "set_mode",
            [whirlpool.aircon.Mode.Cool],
        ),
        (
            SERVICE_SET_HVAC_MODE,
            {ATTR_HVAC_MODE: HVACMode.HEAT},
            "set_mode",
            [whirlpool.aircon.Mode.Heat],
        ),
        (
            SERVICE_SET_HVAC_MODE,
            {ATTR_HVAC_MODE: HVACMode.FAN_ONLY},
            "set_mode",
            [whirlpool.aircon.Mode.Fan],
        ),
        (
            SERVICE_SET_HVAC_MODE,
            {ATTR_HVAC_MODE: HVACMode.OFF},
            "set_power_on",
            [False],
        ),
        (SERVICE_SET_TEMPERATURE, {ATTR_TEMPERATURE: 20}, "set_temp", [20]),
        (
            SERVICE_SET_FAN_MODE,
            {ATTR_FAN_MODE: FAN_AUTO},
            "set_fanspeed",
            [whirlpool.aircon.FanSpeed.Auto],
        ),
        (
            SERVICE_SET_FAN_MODE,
            {ATTR_FAN_MODE: FAN_LOW},
            "set_fanspeed",
            [whirlpool.aircon.FanSpeed.Low],
        ),
        (
            SERVICE_SET_FAN_MODE,
            {ATTR_FAN_MODE: FAN_MEDIUM},
            "set_fanspeed",
            [whirlpool.aircon.FanSpeed.Medium],
        ),
        (
            SERVICE_SET_FAN_MODE,
            {ATTR_FAN_MODE: FAN_HIGH},
            "set_fanspeed",
            [whirlpool.aircon.FanSpeed.High],
        ),
        (
            SERVICE_SET_SWING_MODE,
            {ATTR_SWING_MODE: SWING_HORIZONTAL},
            "set_h_louver_swing",
            [True],
        ),
        (
            SERVICE_SET_SWING_MODE,
            {ATTR_SWING_MODE: SWING_OFF},
            "set_h_louver_swing",
            [False],
        ),
    ],
)
async def test_service_calls(
    hass: HomeAssistant,
    service: str,
    service_data: dict,
    expected_call: str,
    expected_args: list,
    multiple_climate_entities: tuple[str, str],
    request: pytest.FixtureRequest,
) -> None:
    """Test controlling the entity through service calls."""
    await init_integration(hass)
    entity_id, mock_fixture = multiple_climate_entities
    mock_instance = request.getfixturevalue(mock_fixture)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        service,
        {ATTR_ENTITY_ID: entity_id, **service_data},
        blocking=True,
    )
    assert getattr(mock_instance, expected_call).call_count == 1
    getattr(mock_instance, expected_call).assert_called_once_with(*expected_args)


@pytest.mark.parametrize(
    ("service", "service_data"),
    [
        (
            SERVICE_SET_HVAC_MODE,
            {ATTR_HVAC_MODE: HVACMode.COOL},
        ),
        (
            SERVICE_SET_HVAC_MODE,
            {ATTR_HVAC_MODE: HVACMode.HEAT},
        ),
        (
            SERVICE_SET_HVAC_MODE,
            {ATTR_HVAC_MODE: HVACMode.FAN_ONLY},
        ),
    ],
)
async def test_service_hvac_mode_turn_on(
    hass: HomeAssistant,
    service: str,
    service_data: dict,
    multiple_climate_entities: tuple[str, str],
    request: pytest.FixtureRequest,
) -> None:
    """Test that the HVAC mode service call turns on the entity, if it is off."""
    await init_integration(hass)
    entity_id, mock_fixture = multiple_climate_entities
    mock_instance = request.getfixturevalue(mock_fixture)

    mock_instance.get_power_on.return_value = False
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        service,
        {ATTR_ENTITY_ID: entity_id, **service_data},
        blocking=True,
    )
    mock_instance.set_power_on.assert_called_once_with(True)

    # Test that set_power_on is not called if the device is already on
    mock_instance.set_power_on.reset_mock()
    mock_instance.get_power_on.return_value = True

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        service,
        {ATTR_ENTITY_ID: entity_id, **service_data},
        blocking=True,
    )
    mock_instance.set_power_on.assert_not_called()


@pytest.mark.parametrize(
    ("service", "service_data", "exception"),
    [
        (
            SERVICE_SET_HVAC_MODE,
            {ATTR_HVAC_MODE: HVACMode.DRY},
            ValueError,
        ),
        (
            SERVICE_SET_FAN_MODE,
            {ATTR_FAN_MODE: FAN_MIDDLE},
            ServiceValidationError,
        ),
    ],
)
async def test_service_unsupported(
    hass: HomeAssistant,
    service: str,
    service_data: dict,
    exception: type[Exception],
    multiple_climate_entities: tuple[str, str],
) -> None:
    """Test that unsupported service calls are handled properly."""
    await init_integration(hass)
    entity_id, _ = multiple_climate_entities

    with pytest.raises(exception):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            service,
            {ATTR_ENTITY_ID: entity_id, **service_data},
            blocking=True,
        )
