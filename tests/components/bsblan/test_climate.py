"""Tests for the BSB-Lan climate platform."""

from datetime import timedelta
import json
from unittest.mock import AsyncMock, MagicMock, patch

from bsblan import BSBLANError, StaticState
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.bsblan.const import DOMAIN
from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    ATTR_PRESET_MODE,
    DOMAIN as CLIMATE_DOMAIN,
    PRESET_ECO,
    PRESET_NONE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_TEMPERATURE,
    HVACMode,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    Platform,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
import homeassistant.helpers.entity_registry as er

from . import setup_with_selected_platforms

from tests.common import (
    MockConfigEntry,
    async_fire_time_changed,
    load_fixture,
    snapshot_platform,
)

ENTITY_ID = "climate.bsb_lan"


@pytest.mark.parametrize(
    ("static_file", "temperature_unit"),
    [
        ("static.json", UnitOfTemperature.CELSIUS),
        ("static_F.json", UnitOfTemperature.FAHRENHEIT),
    ],
)
async def test_celsius_fahrenheit(
    hass: HomeAssistant,
    mock_bsblan: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    static_file: str,
    temperature_unit: str,
) -> None:
    """Test Celsius and Fahrenheit temperature units."""
    # Load static data from fixture
    static_data = json.loads(load_fixture(static_file, DOMAIN))

    # Patch the static_values method to return our test data
    with patch.object(
        mock_bsblan, "static_values", return_value=StaticState.from_dict(static_data)
    ):
        # Set up the climate platform
        await setup_with_selected_platforms(hass, mock_config_entry, [Platform.CLIMATE])

        # Take a snapshot of the entity registry
        await snapshot_platform(
            hass, entity_registry, snapshot, mock_config_entry.entry_id
        )


async def test_climate_entity_properties(
    hass: HomeAssistant,
    mock_bsblan: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the climate entity properties."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.CLIMATE])
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)

    # Test when current_temperature is "---"
    mock_current_temp = MagicMock()
    mock_current_temp.value = "---"
    mock_bsblan.state.return_value.current_temperature = mock_current_temp

    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.attributes["current_temperature"] is None

    # Test target_temperature
    mock_target_temp = MagicMock()
    mock_target_temp.value = "23.5"
    mock_bsblan.state.return_value.target_temperature = mock_target_temp

    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.attributes["temperature"] == 23.5

    # Test hvac_mode
    mock_hvac_mode = MagicMock()
    mock_hvac_mode.value = HVACMode.AUTO
    mock_bsblan.state.return_value.hvac_mode = mock_hvac_mode

    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.state == HVACMode.AUTO

    # Test preset_mode
    mock_hvac_mode.value = PRESET_ECO

    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.attributes["preset_mode"] == PRESET_ECO


@pytest.mark.parametrize("static_file", ["static.json"])
@pytest.mark.parametrize(
    "mode",
    [HVACMode.HEAT, HVACMode.AUTO, HVACMode.OFF],
)
async def test_async_set_hvac_mode(
    hass: HomeAssistant,
    mock_bsblan: AsyncMock,
    mock_config_entry: MockConfigEntry,
    static_file: str,
    mode: HVACMode,
) -> None:
    """Test setting HVAC mode via service call."""
    static_data = json.loads(load_fixture(static_file, DOMAIN))
    with patch.object(
        mock_bsblan, "static_values", return_value=StaticState.from_dict(static_data)
    ):
        await setup_with_selected_platforms(hass, mock_config_entry, [Platform.CLIMATE])

    # Call the service to set HVAC mode
    await hass.services.async_call(
        domain=CLIMATE_DOMAIN,
        service=SERVICE_SET_HVAC_MODE,
        service_data={ATTR_ENTITY_ID: ENTITY_ID, ATTR_HVAC_MODE: mode},
        blocking=True,
    )

    # Assert that the thermostat method was called
    mock_bsblan.thermostat.assert_called_once_with(hvac_mode=mode)
    mock_bsblan.thermostat.reset_mock()


@pytest.mark.parametrize(
    ("hvac_mode", "preset_mode", "expected_success"),
    [
        (HVACMode.AUTO, PRESET_ECO, True),
        (HVACMode.AUTO, PRESET_NONE, True),
        (HVACMode.HEAT, PRESET_ECO, False),
    ],
)
async def test_async_set_preset_mode(
    hass: HomeAssistant,
    mock_bsblan: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    hvac_mode: HVACMode,
    preset_mode: str,
    expected_success: bool,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test setting preset mode via service call."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.CLIMATE])

    # patch hvac_mode
    mock_hvac_mode = MagicMock()
    mock_hvac_mode.value = hvac_mode
    mock_bsblan.state.return_value.hvac_mode = mock_hvac_mode

    # Attempt to set the preset mode
    if not expected_success:
        with pytest.raises(HomeAssistantError) as exc_info:
            await hass.services.async_call(
                CLIMATE_DOMAIN,
                SERVICE_SET_PRESET_MODE,
                {ATTR_ENTITY_ID: ENTITY_ID, ATTR_PRESET_MODE: preset_mode},
                blocking=True,
            )
        assert "set_preset_mode_error" in str(exc_info.value)
    else:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_PRESET_MODE,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_PRESET_MODE: preset_mode},
            blocking=True,
        )
        await hass.async_block_till_done()

    # Reset the mock for the next iteration
    mock_bsblan.thermostat.reset_mock()


@pytest.mark.parametrize(
    ("target_temp", "expected_result"),
    [
        (8.0, "success"),  # Min temperature
        (15.0, "success"),  # Mid-range temperature
        (20.0, "success"),  # Max temperature
        (7.9, "failure"),  # Just below min
        (20.1, "failure"),  # Just above max
    ],
)
async def test_async_set_temperature(
    hass: HomeAssistant,
    mock_bsblan: AsyncMock,
    mock_config_entry: MockConfigEntry,
    target_temp: float,
    expected_result: str,
) -> None:
    """Test setting temperature via service call."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.CLIMATE])

    if expected_result == "success":
        # Call the service to set temperature
        await hass.services.async_call(
            domain=CLIMATE_DOMAIN,
            service=SERVICE_SET_TEMPERATURE,
            service_data={ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: target_temp},
            blocking=True,
        )
        # Assert that the thermostat method was called with the correct temperature
        mock_bsblan.thermostat.assert_called_once_with(target_temperature=target_temp)
    else:
        # Expect a ServiceValidationError for temperatures out of range
        with pytest.raises(ServiceValidationError) as exc_info:
            await hass.services.async_call(
                domain=CLIMATE_DOMAIN,
                service=SERVICE_SET_TEMPERATURE,
                service_data={ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: target_temp},
                blocking=True,
            )
        assert exc_info.value.translation_key == "temp_out_of_range"

    mock_bsblan.thermostat.reset_mock()


async def test_async_set_data(
    hass: HomeAssistant,
    mock_bsblan: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting data via service calls."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.CLIMATE])

    # Test setting temperature
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: 19},
        blocking=True,
    )
    mock_bsblan.thermostat.assert_called_once_with(target_temperature=19)
    mock_bsblan.thermostat.reset_mock()

    # Test setting HVAC mode
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_HVAC_MODE: HVACMode.HEAT},
        blocking=True,
    )
    mock_bsblan.thermostat.assert_called_once_with(hvac_mode=HVACMode.HEAT)
    mock_bsblan.thermostat.reset_mock()

    # Patch HVAC mode to AUTO
    mock_hvac_mode = MagicMock()
    mock_hvac_mode.value = HVACMode.AUTO
    mock_bsblan.state.return_value.hvac_mode = mock_hvac_mode

    # Test setting preset mode to ECO
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_PRESET_MODE: PRESET_ECO},
        blocking=True,
    )
    mock_bsblan.thermostat.assert_called_once_with(hvac_mode=PRESET_ECO)
    mock_bsblan.thermostat.reset_mock()

    # Test setting preset mode to NONE
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_PRESET_MODE: PRESET_NONE},
        blocking=True,
    )
    mock_bsblan.thermostat.assert_called_once()
    mock_bsblan.thermostat.reset_mock()

    # Test error handling
    mock_bsblan.thermostat.side_effect = BSBLANError("Test error")
    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: 20},
            blocking=True,
        )
    assert "An error occurred while updating the BSBLAN device" in str(exc_info.value)
    assert exc_info.value.translation_key == "set_data_error"
