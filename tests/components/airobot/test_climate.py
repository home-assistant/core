"""Test the Airobot climate platform."""

from datetime import timedelta
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from pyairobotrest.const import MODE_AWAY, MODE_HOME
from pyairobotrest.exceptions import AirobotConnectionError, AirobotError
from pyairobotrest.models import ThermostatSettings, ThermostatStatus
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.climate import (
    ATTR_PRESET_MODE,
    ATTR_TEMPERATURE,
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_TEMPERATURE,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
import homeassistant.helpers.entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.usefixtures("init_integration")
async def test_climate_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test climate entities."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


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

    with pytest.raises(ServiceValidationError, match="Failed to set temperature"):
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
    ("preset_mode", "method", "arg"),
    [
        ("home", "set_mode", MODE_HOME),
        ("away", "set_mode", MODE_AWAY),
        ("boost", "set_boost_mode", True),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_climate_set_preset_mode(
    hass: HomeAssistant,
    mock_airobot_client: AsyncMock,
    preset_mode: str,
    method: str,
    arg: int | bool,
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

    getattr(mock_airobot_client, method).assert_called_once_with(arg)


async def test_climate_set_preset_mode_from_boost_to_home(
    hass: HomeAssistant,
    mock_airobot_client: AsyncMock,
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

    with pytest.raises(ServiceValidationError, match="Failed to set preset mode"):
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
async def test_climate_unavailable_on_update_failure(
    hass: HomeAssistant,
    mock_airobot_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test climate entity becomes unavailable when coordinator update fails."""
    # Initially available
    state = hass.states.get("climate.test_thermostat")
    assert state
    assert state.state != "unavailable"

    # Simulate connection error during update
    mock_airobot_client.get_statuses.side_effect = AirobotConnectionError(
        "Connection lost"
    )
    mock_airobot_client.get_settings.side_effect = AirobotConnectionError(
        "Connection lost"
    )

    # Advance time to trigger coordinator update (30 second interval)
    freezer.tick(timedelta(seconds=35))
    await hass.async_block_till_done()

    # Entity should now be unavailable
    state = hass.states.get("climate.test_thermostat")
    assert state
    assert state.state == "unavailable"


@pytest.mark.parametrize(
    ("temp_floor", "temp_air", "expected_temp"),
    [
        (25.0, 22.0, 25.0),  # Floor sensor available - should use floor temp
        (None, 22.0, 22.0),  # Floor sensor not available - should use air temp
    ],
)
async def test_climate_current_temperature(
    hass: HomeAssistant,
    mock_airobot_client: AsyncMock,
    mock_status: ThermostatStatus,
    mock_config_entry: MockConfigEntry,
    temp_floor: float | None,
    temp_air: float,
    expected_temp: float,
) -> None:
    """Test current temperature prioritizes floor sensor when available."""
    mock_status.temp_floor = temp_floor
    mock_status.temp_air = temp_air

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("climate.test_thermostat")
    assert state
    assert state.attributes.get("current_temperature") == expected_temp
