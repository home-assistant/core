"""Test Control4 Climate."""

from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    ATTR_TEMPERATURE,
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_TEMPERATURE,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform

ENTITY_ID = "climate.test_controller_residential_thermostat_v2"


@pytest.fixture
def platforms() -> list[str]:
    """Override platforms fixture to only load climate."""
    return ["climate"]


@pytest.mark.usefixtures(
    "mock_c4_account", "mock_c4_director", "mock_climate_update_variables"
)
async def test_climate_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test climate entities are set up correctly with proper attributes."""
    hass.config.units = US_CUSTOMARY_SYSTEM
    await setup_integration(hass, mock_config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures(
    "mock_c4_account", "mock_c4_director", "mock_climate_update_variables"
)
async def test_climate_setup(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test climate entity is set up correctly."""
    hass.config.units = US_CUSTOMARY_SYSTEM
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == HVACMode.HEAT
    assert state.attributes["current_temperature"] == 72
    assert state.attributes["current_humidity"] == 45
    assert state.attributes["temperature"] == 68
    assert state.attributes["hvac_action"] == HVACAction.IDLE


@pytest.mark.usefixtures("mock_c4_account", "mock_c4_director")
async def test_climate_off_state(
    hass: HomeAssistant,
    mock_config_entry,
    platforms,
) -> None:
    """Test climate entity in off state."""
    hass.config.units = US_CUSTOMARY_SYSTEM
    mock_config_entry.add_to_hass(hass)

    climate_vars = {
        123: {
            "HVAC_STATE": "off",
            "HVAC_MODE": "Off",
            "TEMPERATURE_F": 72.0,
            "HUMIDITY": 50,
            "COOL_SETPOINT_F": 75.0,
            "HEAT_SETPOINT_F": 68.0,
        }
    }

    async def mock_update_vars(*args, **kwargs):
        return climate_vars

    with (
        patch(
            "homeassistant.components.control4.climate.update_variables_for_config_entry",
            new=mock_update_vars,
        ),
        patch("homeassistant.components.control4.PLATFORMS", platforms),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.state == HVACMode.OFF
    assert state.attributes["hvac_action"] == HVACAction.OFF
    assert state.attributes["temperature"] is None


@pytest.mark.usefixtures("mock_c4_account", "mock_c4_director")
async def test_climate_cool_state(
    hass: HomeAssistant,
    mock_config_entry,
    platforms,
) -> None:
    """Test climate entity in cool state."""
    hass.config.units = US_CUSTOMARY_SYSTEM
    mock_config_entry.add_to_hass(hass)

    climate_vars = {
        123: {
            "HVAC_STATE": "cooling",
            "HVAC_MODE": "Cool",
            "TEMPERATURE_F": 74.0,
            "HUMIDITY": 55,
            "COOL_SETPOINT_F": 72.0,
            "HEAT_SETPOINT_F": 68.0,
        }
    }

    async def mock_update_vars(*args, **kwargs):
        return climate_vars

    with (
        patch(
            "homeassistant.components.control4.climate.update_variables_for_config_entry",
            new=mock_update_vars,
        ),
        patch("homeassistant.components.control4.PLATFORMS", platforms),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.state == HVACMode.COOL
    assert state.attributes["hvac_action"] == HVACAction.COOLING
    assert state.attributes["temperature"] == 72.0


@pytest.mark.usefixtures("mock_c4_account", "mock_c4_director")
async def test_climate_auto_state(
    hass: HomeAssistant,
    mock_config_entry,
    platforms,
) -> None:
    """Test climate entity in auto state."""
    hass.config.units = US_CUSTOMARY_SYSTEM
    mock_config_entry.add_to_hass(hass)

    climate_vars = {
        123: {
            "HVAC_STATE": "heating",
            "HVAC_MODE": "Auto",
            "TEMPERATURE_F": 65.0,
            "HUMIDITY": 40,
            "COOL_SETPOINT_F": 75.0,
            "HEAT_SETPOINT_F": 68.0,
        }
    }

    async def mock_update_vars(*args, **kwargs):
        return climate_vars

    with (
        patch(
            "homeassistant.components.control4.climate.update_variables_for_config_entry",
            new=mock_update_vars,
        ),
        patch("homeassistant.components.control4.PLATFORMS", platforms),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.state == HVACMode.HEAT_COOL
    assert state.attributes["hvac_action"] == HVACAction.HEATING
    assert state.attributes["target_temp_high"] == 75.0
    assert state.attributes["target_temp_low"] == 68.0


@pytest.mark.usefixtures(
    "mock_c4_account", "mock_c4_director", "mock_climate_update_variables"
)
async def test_set_hvac_mode(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test setting HVAC mode."""
    hass.config.units = US_CUSTOMARY_SYSTEM
    await setup_integration(hass, mock_config_entry)

    with patch(
        "pyControl4.climate.C4Climate.setHvacMode", new_callable=AsyncMock
    ) as mock_set:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_HVAC_MODE: HVACMode.COOL},
            blocking=True,
        )
        mock_set.assert_called_once_with("Cool")


@pytest.mark.usefixtures(
    "mock_c4_account", "mock_c4_director", "mock_climate_update_variables"
)
async def test_set_hvac_mode_to_off(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test setting HVAC mode to off."""
    hass.config.units = US_CUSTOMARY_SYSTEM
    await setup_integration(hass, mock_config_entry)

    with patch(
        "pyControl4.climate.C4Climate.setHvacMode", new_callable=AsyncMock
    ) as mock_set:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_HVAC_MODE: HVACMode.OFF},
            blocking=True,
        )
        mock_set.assert_called_once_with("Off")


@pytest.mark.usefixtures(
    "mock_c4_account", "mock_c4_director", "mock_climate_update_variables"
)
async def test_set_temperature_heat_mode(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test setting temperature in heat mode."""
    hass.config.units = US_CUSTOMARY_SYSTEM
    await setup_integration(hass, mock_config_entry)

    with patch(
        "pyControl4.climate.C4Climate.setHeatSetpointF", new_callable=AsyncMock
    ) as mock_set:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: 70.0},
            blocking=True,
        )
        mock_set.assert_called_once_with(70.0)


@pytest.mark.usefixtures("mock_c4_account", "mock_c4_director")
async def test_set_temperature_cool_mode(
    hass: HomeAssistant,
    mock_config_entry,
    platforms,
) -> None:
    """Test setting temperature in cool mode."""
    hass.config.units = US_CUSTOMARY_SYSTEM
    mock_config_entry.add_to_hass(hass)

    climate_vars = {
        123: {
            "HVAC_STATE": "idle",
            "HVAC_MODE": "Cool",
            "TEMPERATURE_F": 74.0,
            "HUMIDITY": 50,
            "COOL_SETPOINT_F": 72.0,
            "HEAT_SETPOINT_F": 68.0,
        }
    }

    async def mock_update_vars(*args, **kwargs):
        return climate_vars

    with (
        patch(
            "homeassistant.components.control4.climate.update_variables_for_config_entry",
            new=mock_update_vars,
        ),
        patch("homeassistant.components.control4.PLATFORMS", platforms),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    with patch(
        "pyControl4.climate.C4Climate.setCoolSetpointF", new_callable=AsyncMock
    ) as mock_set:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: 70.0},
            blocking=True,
        )
        mock_set.assert_called_once_with(70.0)


@pytest.mark.usefixtures("mock_c4_account", "mock_c4_director")
async def test_set_temperature_range_auto_mode(
    hass: HomeAssistant,
    mock_config_entry,
    platforms,
) -> None:
    """Test setting temperature range in auto mode."""
    hass.config.units = US_CUSTOMARY_SYSTEM
    mock_config_entry.add_to_hass(hass)

    climate_vars = {
        123: {
            "HVAC_STATE": "idle",
            "HVAC_MODE": "Auto",
            "TEMPERATURE_F": 70.0,
            "HUMIDITY": 50,
            "COOL_SETPOINT_F": 75.0,
            "HEAT_SETPOINT_F": 68.0,
        }
    }

    async def mock_update_vars(*args, **kwargs):
        return climate_vars

    with (
        patch(
            "homeassistant.components.control4.climate.update_variables_for_config_entry",
            new=mock_update_vars,
        ),
        patch("homeassistant.components.control4.PLATFORMS", platforms),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    with (
        patch(
            "pyControl4.climate.C4Climate.setHeatSetpointF", new_callable=AsyncMock
        ) as mock_heat,
        patch(
            "pyControl4.climate.C4Climate.setCoolSetpointF", new_callable=AsyncMock
        ) as mock_cool,
    ):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                "target_temp_low": 65.0,
                "target_temp_high": 78.0,
            },
            blocking=True,
        )
        mock_heat.assert_called_once_with(65.0)
        mock_cool.assert_called_once_with(78.0)


@pytest.mark.usefixtures("mock_c4_account", "mock_c4_director")
async def test_climate_not_created_when_no_initial_data(
    hass: HomeAssistant,
    mock_config_entry,
    platforms,
) -> None:
    """Test climate entity is not created when coordinator has no initial data."""
    hass.config.units = US_CUSTOMARY_SYSTEM
    mock_config_entry.add_to_hass(hass)

    async def mock_update_vars(*args, **kwargs):
        return {}

    with (
        patch(
            "homeassistant.components.control4.climate.update_variables_for_config_entry",
            new=mock_update_vars,
        ),
        patch("homeassistant.components.control4.PLATFORMS", platforms),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Entity should not be created if there's no data during initial setup
    state = hass.states.get(ENTITY_ID)
    assert state is None


@pytest.mark.usefixtures("mock_c4_account", "mock_c4_director")
async def test_climate_missing_variables(
    hass: HomeAssistant,
    mock_config_entry,
    platforms,
) -> None:
    """Test climate entity handles missing variables gracefully."""
    hass.config.units = US_CUSTOMARY_SYSTEM
    mock_config_entry.add_to_hass(hass)

    climate_vars = {
        123: {
            "HVAC_STATE": "idle",
            "HVAC_MODE": "Heat",
            # Missing TEMPERATURE_F and HUMIDITY
            "COOL_SETPOINT_F": 75.0,
            "HEAT_SETPOINT_F": 68.0,
        }
    }

    async def mock_update_vars(*args, **kwargs):
        return climate_vars

    with (
        patch(
            "homeassistant.components.control4.climate.update_variables_for_config_entry",
            new=mock_update_vars,
        ),
        patch("homeassistant.components.control4.PLATFORMS", platforms),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == HVACMode.HEAT
    assert state.attributes.get("current_temperature") is None
    assert state.attributes.get("current_humidity") is None
    assert state.attributes["temperature"] == 68.0


@pytest.mark.usefixtures("mock_c4_account", "mock_c4_director")
async def test_climate_unknown_hvac_mode(
    hass: HomeAssistant,
    mock_config_entry,
    platforms,
) -> None:
    """Test climate entity handles unknown HVAC mode."""
    hass.config.units = US_CUSTOMARY_SYSTEM
    mock_config_entry.add_to_hass(hass)

    climate_vars = {
        123: {
            "HVAC_STATE": "idle",
            "HVAC_MODE": "UnknownMode",
            "TEMPERATURE_F": 72.0,
            "HUMIDITY": 50,
            "COOL_SETPOINT_F": 75.0,
            "HEAT_SETPOINT_F": 68.0,
        }
    }

    async def mock_update_vars(*args, **kwargs):
        return climate_vars

    with (
        patch(
            "homeassistant.components.control4.climate.update_variables_for_config_entry",
            new=mock_update_vars,
        ),
        patch("homeassistant.components.control4.PLATFORMS", platforms),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == HVACMode.OFF  # Defaults to OFF for unknown modes


@pytest.mark.usefixtures("mock_c4_account", "mock_c4_director")
async def test_climate_unknown_hvac_state(
    hass: HomeAssistant,
    mock_config_entry,
    platforms,
) -> None:
    """Test climate entity handles unknown HVAC state."""
    hass.config.units = US_CUSTOMARY_SYSTEM
    mock_config_entry.add_to_hass(hass)

    climate_vars = {
        123: {
            "HVAC_STATE": "unknown_state",
            "HVAC_MODE": "Heat",
            "TEMPERATURE_F": 72.0,
            "HUMIDITY": 50,
            "COOL_SETPOINT_F": 75.0,
            "HEAT_SETPOINT_F": 68.0,
        }
    }

    async def mock_update_vars(*args, **kwargs):
        return climate_vars

    with (
        patch(
            "homeassistant.components.control4.climate.update_variables_for_config_entry",
            new=mock_update_vars,
        ),
        patch("homeassistant.components.control4.PLATFORMS", platforms),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes.get("hvac_action") is None
