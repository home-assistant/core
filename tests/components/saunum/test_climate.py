"""Test the Saunum climate platform."""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, patch

from pysaunum import SaunumData
import pytest

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

from tests.common import MockConfigEntry


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return [Platform.CLIMATE]


@pytest.mark.usefixtures("init_integration")
async def test_climate_entity_creation(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test climate entity creation."""
    # Check climate entity is created
    entity_id = "climate.saunum_leil"
    entity_entry = entity_registry.async_get(entity_id)
    assert entity_entry is not None

    state = hass.states.get(entity_id)
    assert state is not None


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


@pytest.mark.usefixtures("init_integration")
async def test_climate_set_hvac_mode_heat(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting HVAC mode to HEAT."""
    entity_id = "climate.saunum_leil"

    coordinator = mock_config_entry.runtime_data
    coordinator.async_start_session = AsyncMock(return_value=True)
    coordinator.async_request_refresh = AsyncMock()

    # Turn on heating
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_HVAC_MODE: HVACMode.HEAT},
        blocking=True,
    )
    await hass.async_block_till_done()

    coordinator.async_start_session.assert_called_once()


@pytest.mark.usefixtures("init_integration")
async def test_climate_set_hvac_mode_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting HVAC mode to OFF."""
    entity_id = "climate.saunum_leil"

    coordinator = mock_config_entry.runtime_data
    coordinator.async_stop_session = AsyncMock(return_value=True)
    coordinator.async_request_refresh = AsyncMock()

    # Turn off heating
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_HVAC_MODE: HVACMode.OFF},
        blocking=True,
    )
    await hass.async_block_till_done()

    coordinator.async_stop_session.assert_called_once()


@pytest.mark.usefixtures("init_integration")
async def test_climate_set_temperature(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting target temperature."""
    entity_id = "climate.saunum_leil"

    coordinator = mock_config_entry.runtime_data
    coordinator.async_set_target_temperature = AsyncMock(return_value=True)
    coordinator.async_request_refresh = AsyncMock()

    # Set temperature to 85°C
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: entity_id, ATTR_TEMPERATURE: 85},
        blocking=True,
    )
    await hass.async_block_till_done()

    coordinator.async_set_target_temperature.assert_called_once_with(85)


@pytest.mark.usefixtures("init_integration")
async def test_climate_device_info(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test climate device info."""
    entity_id = "climate.saunum_leil"
    entity_entry = entity_registry.async_get(entity_id)
    assert entity_entry is not None

    state = hass.states.get(entity_id)
    assert state is not None

    # Check friendly name (should be just the device name since _attr_name = None)
    assert state.attributes.get("friendly_name") == "Saunum Leil"


@pytest.mark.usefixtures("init_integration")
async def test_climate_unique_id(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test climate unique ID."""
    entity_id = "climate.saunum_leil"
    entity_entry = entity_registry.async_get(entity_id)
    assert entity_entry is not None

    expected_unique_id = f"{mock_config_entry.entry_id}_climate"
    assert entity_entry.unique_id == expected_unique_id


async def test_climate_hvac_mode_heat(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_saunum_client,
) -> None:
    """Test climate HVAC mode when session is active."""
    # Update mock to return active session
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
            heater_elements_active=3,
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

    # Session is active
    assert state.state == HVACMode.HEAT
    assert state.attributes.get(ATTR_HVAC_ACTION) == HVACAction.HEATING


async def test_climate_hvac_action_idle(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_saunum_client,
) -> None:
    """Test climate HVAC action when session is active but heater is off."""
    # Update mock to return active session but heater off
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
            heater_elements_active=0,  # Heater off
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

    # Session is active but heater is off (target temp reached)
    assert state.state == HVACMode.HEAT
    assert state.attributes.get(ATTR_HVAC_ACTION) == HVACAction.IDLE


async def test_climate_none_temperature(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_saunum_client,
) -> None:
    """Test climate with None current temperature."""
    # Update mock to return None temperature
    mock_saunum_client.async_get_data = AsyncMock(
        return_value=SaunumData(
            session_active=False,
            sauna_type=0,
            sauna_duration=60,
            fan_duration=10,
            target_temperature=80,
            fan_speed=2,
            light_on=False,
            current_temperature=None,  # Sensor failure
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

    # Current temperature should be None
    assert state.attributes.get(ATTR_CURRENT_TEMPERATURE) is None


async def test_climate_target_temp_below_minimum(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_saunum_client,
) -> None:
    """Test climate with target temperature below minimum."""
    # Update mock to return low target temperature
    mock_saunum_client.async_get_data = AsyncMock(
        return_value=SaunumData(
            session_active=False,
            sauna_type=0,
            sauna_duration=60,
            fan_duration=10,
            target_temperature=30,  # Below minimum
            fan_speed=2,
            light_on=False,
            current_temperature=35.0,
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

    # Target temperature should be None when below minimum
    assert state.attributes.get(ATTR_TEMPERATURE) is None


@pytest.mark.usefixtures("init_integration")
async def test_climate_set_hvac_mode_heat_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting HVAC mode to HEAT when operation fails."""
    entity_id = "climate.saunum_leil"

    coordinator = mock_config_entry.runtime_data
    coordinator.async_start_session = AsyncMock(return_value=False)
    coordinator.async_request_refresh = AsyncMock()

    # Turn on heating
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_HVAC_MODE: HVACMode.HEAT},
        blocking=True,
    )
    await hass.async_block_till_done()

    coordinator.async_start_session.assert_called_once()


@pytest.mark.usefixtures("init_integration")
async def test_climate_set_temperature_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting target temperature when operation fails."""
    entity_id = "climate.saunum_leil"

    coordinator = mock_config_entry.runtime_data
    coordinator.async_set_target_temperature = AsyncMock(return_value=False)
    coordinator.async_request_refresh = AsyncMock()

    # Set temperature to 85°C
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: entity_id, ATTR_TEMPERATURE: 85},
        blocking=True,
    )
    await hass.async_block_till_done()

    coordinator.async_set_target_temperature.assert_called_once_with(85)


@pytest.mark.usefixtures("init_integration")
async def test_climate_set_unsupported_hvac_mode(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test setting unsupported HVAC mode directly on entity."""
    entity_id = "climate.saunum_leil"

    # Set log level to WARNING to capture the warning message
    caplog.set_level(logging.WARNING)

    # Get the climate entity directly from hass.data
    climate_entity = hass.data["entity_components"]["climate"].get_entity(entity_id)
    assert climate_entity is not None

    # Call the method directly with an unsupported mode
    await climate_entity.async_set_hvac_mode(HVACMode.COOL)

    # Check that warning was logged
    assert "Unsupported HVAC mode: cool" in caplog.text


@pytest.mark.usefixtures("init_integration")
async def test_climate_set_temperature_no_value(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting temperature without providing a temperature value."""
    entity_id = "climate.saunum_leil"

    coordinator = mock_config_entry.runtime_data
    coordinator.async_set_target_temperature = AsyncMock(return_value=True)
    coordinator.async_request_refresh = AsyncMock()

    # Get the climate entity directly from hass.data
    climate_entity = hass.data["entity_components"]["climate"].get_entity(entity_id)
    assert climate_entity is not None

    # Call async_set_temperature without temperature parameter (should return early)
    await climate_entity.async_set_temperature()  # No kwargs

    # Should not call the coordinator method
    coordinator.async_set_target_temperature.assert_not_called()
