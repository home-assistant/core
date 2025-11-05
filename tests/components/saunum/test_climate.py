"""Test the Saunum climate platform."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from pysaunum import SaunumData
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.climate import (
    ATTR_CURRENT_TEMPERATURE,
    ATTR_HVAC_ACTION,
    ATTR_HVAC_MODE,
    ATTR_MAX_TEMP,
    ATTR_MIN_TEMP,
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_TEMPERATURE,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return [Platform.CLIMATE]


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("init_integration")
async def test_climate_hvac_mode_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test climate HVAC mode when session is off."""
    entity_id = "climate.saunum_leil"
    state = hass.states.get(entity_id)
    assert state is not None

    # Mock data has session_active = False
    assert state.state == HVACMode.OFF
    assert state.attributes.get(ATTR_HVAC_ACTION) == HVACAction.OFF


@pytest.mark.usefixtures("init_integration")
async def test_climate_temperatures_celsius(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test climate temperatures in Celsius."""
    entity_id = "climate.saunum_leil"
    state = hass.states.get(entity_id)
    assert state is not None

    # Check temperatures from mock data
    assert state.attributes.get(ATTR_CURRENT_TEMPERATURE) == 75
    assert state.attributes.get(ATTR_TEMPERATURE) == 80
    assert state.attributes.get(ATTR_MIN_TEMP) == 40
    assert state.attributes.get(ATTR_MAX_TEMP) == 100


@pytest.mark.parametrize(
    ("service", "service_data", "client_method", "expected_args"),
    [
        (
            SERVICE_SET_HVAC_MODE,
            {ATTR_HVAC_MODE: HVACMode.HEAT},
            "async_start_session",
            (),
        ),
        (
            SERVICE_SET_HVAC_MODE,
            {ATTR_HVAC_MODE: HVACMode.OFF},
            "async_stop_session",
            (),
        ),
        (
            SERVICE_SET_TEMPERATURE,
            {ATTR_TEMPERATURE: 85},
            "async_set_target_temperature",
            (85,),
        ),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_climate_service_calls(
    hass: HomeAssistant,
    mock_saunum_client,
    service: str,
    service_data: dict,
    client_method: str,
    expected_args: tuple,
) -> None:
    """Test climate service calls."""
    entity_id = "climate.saunum_leil"

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        service,
        {ATTR_ENTITY_ID: entity_id, **service_data},
        blocking=True,
    )

    getattr(mock_saunum_client, client_method).assert_called_once_with(*expected_args)


@pytest.mark.parametrize(
    ("heater_elements_active", "expected_hvac_action"),
    [
        (3, HVACAction.HEATING),
        (0, HVACAction.IDLE),
    ],
)
async def test_climate_hvac_actions(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_saunum_client,
    heater_elements_active: int,
    expected_hvac_action: HVACAction,
) -> None:
    """Test climate HVAC actions when session is active."""
    mock_saunum_client.async_get_data = AsyncMock(
        return_value=SaunumData(
            session_active=True,
            sauna_type=0,
            sauna_duration=60,
            fan_duration=10,
            target_temperature=80,
            fan_speed=2,
            light_on=False,
            current_temperature=75.0,
            on_time=1234,
            heater_elements_active=heater_elements_active,
            door_open=False,
            alarm_door_open=False,
            alarm_door_sensor=False,
            alarm_thermal_cutoff=False,
            alarm_internal_temp=False,
            alarm_temp_sensor_short=False,
            alarm_temp_sensor_open=False,
        )
    )

    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.saunum.PLATFORMS", [Platform.CLIMATE]):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    entity_id = "climate.saunum_leil"
    state = hass.states.get(entity_id)
    assert state is not None

    assert state.state == HVACMode.HEAT
    assert state.attributes.get(ATTR_HVAC_ACTION) == expected_hvac_action


@pytest.mark.parametrize(
    (
        "current_temperature",
        "target_temperature",
        "expected_current",
        "expected_target",
    ),
    [
        (None, 80, None, 80),
        (35.0, 30, 35, 30),
    ],
)
async def test_climate_temperature_edge_cases(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_saunum_client,
    current_temperature: float | None,
    target_temperature: int,
    expected_current: float | None,
    expected_target: int,
) -> None:
    """Test climate with edge case temperature values."""
    mock_saunum_client.async_get_data = AsyncMock(
        return_value=SaunumData(
            session_active=False,
            sauna_type=0,
            sauna_duration=60,
            fan_duration=10,
            target_temperature=target_temperature,
            fan_speed=2,
            light_on=False,
            current_temperature=current_temperature,
            on_time=1234,
            heater_elements_active=0,
            door_open=False,
            alarm_door_open=False,
            alarm_door_sensor=False,
            alarm_thermal_cutoff=False,
            alarm_internal_temp=False,
            alarm_temp_sensor_short=False,
            alarm_temp_sensor_open=False,
        )
    )

    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.saunum.PLATFORMS", [Platform.CLIMATE]):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    entity_id = "climate.saunum_leil"
    state = hass.states.get(entity_id)
    assert state is not None

    assert state.attributes.get(ATTR_CURRENT_TEMPERATURE) == expected_current
    assert state.attributes.get(ATTR_TEMPERATURE) == expected_target
