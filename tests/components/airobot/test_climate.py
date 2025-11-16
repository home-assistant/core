"""Test the Airobot climate platform."""

from unittest.mock import AsyncMock

from pyairobotrest.const import MODE_AWAY, MODE_HOME
from pyairobotrest.exceptions import AirobotError
from pyairobotrest.models import ThermostatSettings, ThermostatStatus
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.airobot.climate import AirobotClimate
from homeassistant.components.climate import (
    ATTR_PRESET_MODE,
    ATTR_TEMPERATURE,
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_TEMPERATURE,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.entity_registry as er

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("init_integration")
async def test_climate_entity_setup(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test climate entity is set up correctly."""
    # Check entity is registered
    entity = entity_registry.async_get("climate.test_thermostat")
    assert entity
    assert entity.unique_id == "T01XXXXXX"


@pytest.mark.usefixtures("init_integration")
async def test_climate_entity_state(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
) -> None:
    """Test climate entity state."""
    state = hass.states.get("climate.test_thermostat")
    assert state
    assert state == snapshot


@pytest.mark.parametrize(
    ("mode", "temperature", "method"),
    [
        (1, 24.0, "set_home_temperature"),  # Home mode
        (0, 18.0, "set_away_temperature"),  # Away mode
    ],
)
async def test_climate_set_temperature(
    hass: HomeAssistant,
    mock_airobot_client: AsyncMock,
    mock_airobot_config_flow_client: AsyncMock,
    mock_settings: ThermostatSettings,
    mock_config_entry: MockConfigEntry,
    mode: int,
    temperature: float,
    method: str,
) -> None:
    """Test setting temperature in different modes."""
    # Set device mode
    mock_settings.mode = mode

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: "climate.test_thermostat",
            ATTR_TEMPERATURE: temperature,
        },
        blocking=True,
    )

    getattr(mock_airobot_client, method).assert_called_once_with(temperature)


@pytest.mark.usefixtures("init_integration")
async def test_climate_set_temperature_error(
    hass: HomeAssistant,
    mock_airobot_client: AsyncMock,
) -> None:
    """Test error handling when setting temperature fails."""
    mock_airobot_client.set_home_temperature.side_effect = AirobotError("Device error")

    with pytest.raises(HomeAssistantError, match="Failed to set temperature"):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {
                ATTR_ENTITY_ID: "climate.test_thermostat",
                ATTR_TEMPERATURE: 24.0,
            },
            blocking=True,
        )


@pytest.mark.parametrize(
    ("preset_mode", "expected_calls"),
    [
        ("home", [("set_mode", MODE_HOME)]),
        ("away", [("set_mode", MODE_AWAY)]),
        ("boost", [("set_boost_mode", True)]),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_climate_set_preset_mode(
    hass: HomeAssistant,
    mock_airobot_client: AsyncMock,
    preset_mode: str,
    expected_calls: list[tuple[str, int | bool]],
) -> None:
    """Test setting different preset modes."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {
            ATTR_ENTITY_ID: "climate.test_thermostat",
            ATTR_PRESET_MODE: preset_mode,
        },
        blocking=True,
    )

    for method, arg in expected_calls:
        getattr(mock_airobot_client, method).assert_called_once_with(arg)


async def test_climate_set_preset_mode_from_boost_to_home(
    hass: HomeAssistant,
    mock_airobot_client: AsyncMock,
    mock_airobot_config_flow_client: AsyncMock,
    mock_settings: ThermostatSettings,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test disabling boost when switching to home mode."""
    # Set boost mode enabled
    mock_settings.setting_flags.boost_enabled = True

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {
            ATTR_ENTITY_ID: "climate.test_thermostat",
            ATTR_PRESET_MODE: "home",
        },
        blocking=True,
    )

    # Should disable boost first, then set mode to home
    mock_airobot_client.set_boost_mode.assert_called_once_with(False)
    mock_airobot_client.set_mode.assert_called_once_with(MODE_HOME)


@pytest.mark.usefixtures("init_integration")
async def test_climate_set_preset_mode_error(
    hass: HomeAssistant,
    mock_airobot_client: AsyncMock,
) -> None:
    """Test error handling when setting preset mode fails."""
    mock_airobot_client.set_boost_mode.side_effect = AirobotError("Device error")

    with pytest.raises(HomeAssistantError, match="Failed to set preset mode"):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_PRESET_MODE,
            {
                ATTR_ENTITY_ID: "climate.test_thermostat",
                ATTR_PRESET_MODE: "boost",
            },
            blocking=True,
        )


async def test_climate_heating_state(
    hass: HomeAssistant,
    mock_airobot_client: AsyncMock,
    mock_airobot_config_flow_client: AsyncMock,
    mock_status: ThermostatStatus,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test climate entity shows heating action when heating."""
    # Set heating on
    mock_status.status_flags.heating_on = True

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("climate.test_thermostat")
    assert state
    assert state.attributes.get("hvac_action") == "heating"


@pytest.mark.usefixtures("init_integration")
async def test_climate_set_temperature_no_change(
    hass: HomeAssistant,
    mock_airobot_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that calling set_temperature with None temperature returns early."""
    # Get the coordinator
    coordinator = mock_config_entry.runtime_data

    # Create entity instance directly
    climate_entity = AirobotClimate(coordinator)

    # Call with no temperature - should return early without API calls
    await climate_entity.async_set_temperature()

    # Verify no API calls were made
    mock_airobot_client.set_home_temperature.assert_not_called()
    mock_airobot_client.set_away_temperature.assert_not_called()
