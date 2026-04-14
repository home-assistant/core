"""Test the eurotronic_cometblue climate platform."""

from unittest.mock import patch
import uuid

from eurotronic_cometblue_ha import const as cometblue_const
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.climate import (
    ATTR_CURRENT_TEMPERATURE,
    ATTR_HVAC_MODE,
    ATTR_PRESET_MODE,
    DOMAIN as CLIMATE_DOMAIN,
    PRESET_AWAY,
    PRESET_BOOST,
    PRESET_COMFORT,
    PRESET_ECO,
    PRESET_NONE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_TEMPERATURE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    HVACMode,
)
from homeassistant.components.eurotronic_cometblue.climate import MAX_TEMP, MIN_TEMP
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er

from .conftest import setup_with_selected_platforms

from tests.common import MockConfigEntry, snapshot_platform

ENTITY_ID = "climate.comet_blue_aa_bb_cc_dd_ee_ff"


async def test_climate_state(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test climate entity state and registry data."""

    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.CLIMATE])
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("temperature_values", "expected_hvac_mode", "expected_preset"),
    [
        ([47, 15, 34, 42, 0, 4, 10], HVACMode.OFF, PRESET_NONE),
        ([47, 40, 34, 42, 0, 4, 10], HVACMode.AUTO, PRESET_NONE),
        ([47, 42, 34, 42, 0, 4, 10], HVACMode.AUTO, PRESET_COMFORT),
        ([47, 34, 34, 42, 0, 4, 10], HVACMode.AUTO, PRESET_ECO),
        ([47, 57, 57, 57, 0, 4, 10], HVACMode.HEAT, PRESET_BOOST),
    ],
)
async def test_climate_hvac_and_preset_states(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_gatt_characteristics: dict[uuid.UUID, bytearray],
    temperature_values: list[int],
    expected_hvac_mode: HVACMode,
    expected_preset: str,
) -> None:
    """Test climate state mapping from device temperatures."""
    mock_gatt_characteristics[cometblue_const.CHARACTERISTIC_TEMPERATURE] = bytearray(
        temperature_values
    )

    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.CLIMATE])

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == expected_hvac_mode
    assert state.attributes[ATTR_PRESET_MODE] == expected_preset


async def test_set_temperature(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting target temperature."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.CLIMATE])

    assert (state := hass.states.get(ENTITY_ID))
    assert state.attributes[ATTR_TEMPERATURE] == 20.0
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 20.5

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: 21.0},
        blocking=True,
    )

    assert (state := hass.states.get(ENTITY_ID))
    assert state.attributes[ATTR_TEMPERATURE] == 21.0
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 20.5


async def test_climate_preset_away_active(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_gatt_characteristics: dict[uuid.UUID, bytearray],
) -> None:
    """Test away preset detection from holiday data."""
    # Holiday active if start hour >= 128 and end hour < 128
    mock_gatt_characteristics[cometblue_const.CHARACTERISTIC_HOLIDAY_1] = bytearray(
        [128, 1, 1, 26, 10, 2, 1, 26, 34]
    )
    # Current target temperature must match holiday temperature for away preset to be active
    mock_gatt_characteristics[cometblue_const.CHARACTERISTIC_TEMPERATURE] = bytearray(
        [47, 34, 34, 42, 0, 4, 10]
    )

    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.CLIMATE])

    assert (state := hass.states.get(ENTITY_ID))
    assert state.attributes[ATTR_PRESET_MODE] == PRESET_AWAY

    with pytest.raises(
        ServiceValidationError,
        match="Cannot adjust TRV remotely",
    ):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: 21.0},
            blocking=True,
        )


@pytest.mark.parametrize(
    ("preset_mode", "expected_temperature", "expected_state"),
    [
        (PRESET_ECO, 17.0, HVACMode.AUTO),
        (PRESET_COMFORT, 21.0, HVACMode.AUTO),
        (PRESET_BOOST, MAX_TEMP, HVACMode.HEAT),
    ],
)
async def test_set_preset_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    preset_mode: str,
    expected_temperature: float,
    expected_state: HVACMode,
) -> None:
    """Test setting preset modes."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.CLIMATE])

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_PRESET_MODE: preset_mode},
        blocking=True,
    )
    assert (state := hass.states.get(ENTITY_ID))
    assert state.attributes[ATTR_TEMPERATURE] == expected_temperature
    assert state.attributes[ATTR_PRESET_MODE] == preset_mode
    assert state.state == expected_state


@pytest.mark.parametrize("preset_mode", [PRESET_NONE, PRESET_AWAY])
async def test_set_preset_mode_display_only_raises(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    preset_mode: str,
) -> None:
    """Test display-only presets cannot be set."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.CLIMATE])

    with pytest.raises(ServiceValidationError, match="Unable to set preset"):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_PRESET_MODE,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_PRESET_MODE: preset_mode},
            blocking=True,
        )


@pytest.mark.parametrize(
    ("hvac_mode", "expected_temperature", "expected_preset"),
    [
        (HVACMode.OFF, MIN_TEMP, PRESET_NONE),
        (HVACMode.HEAT, MAX_TEMP, PRESET_BOOST),
        (HVACMode.AUTO, 17.0, PRESET_ECO),
    ],
)
async def test_set_hvac_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    hvac_mode: HVACMode,
    expected_temperature: float,
    expected_preset: str,
) -> None:
    """Test setting HVAC modes."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.CLIMATE])

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_HVAC_MODE: hvac_mode},
        blocking=True,
    )

    assert (state := hass.states.get(ENTITY_ID))
    assert state.attributes[ATTR_TEMPERATURE] == expected_temperature
    assert state.attributes[ATTR_PRESET_MODE] == expected_preset
    assert state.state == hvac_mode


@pytest.mark.parametrize(
    ("service", "expected_temperature"),
    [
        (SERVICE_TURN_OFF, MIN_TEMP),
        (SERVICE_TURN_ON, 17.0),
    ],
)
async def test_turn_on_turn_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    service: str,
    expected_temperature: float,
) -> None:
    """Test turn_on and turn_off services."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.CLIMATE])

    assert (state := hass.states.get(ENTITY_ID))
    assert state.attributes[ATTR_TEMPERATURE] == 20.0

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        service,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    assert (state := hass.states.get(ENTITY_ID))
    assert state.attributes[ATTR_TEMPERATURE] == expected_temperature


@pytest.mark.parametrize(
    ("raise_exception", "raised_exception"),
    [
        (TimeoutError, HomeAssistantError),
        (ValueError, ServiceValidationError),
    ],
)
async def test_set_temperature_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    raise_exception: type[Exception],
    raised_exception: type[Exception],
) -> None:
    """Test setting target temperature."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.CLIMATE])

    # raise exceptions to test error handling
    with (
        pytest.raises(raised_exception),
        patch(
            "homeassistant.components.eurotronic_cometblue.coordinator.AsyncCometBlue.set_temperature_async",
            side_effect=raise_exception(),
        ),
    ):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: 21.0},
            blocking=True,
        )


async def test_update_data_error_handling(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that update data errors are handled and retried."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.CLIMATE])

    assert (state := hass.states.get(ENTITY_ID))
    assert state.attributes[ATTR_TEMPERATURE] == 20.0

    # Fail with TimeoutError (expected) and raise UpdateFailed after 3 retries
    with patch.object(
        mock_config_entry.runtime_data.device,
        "get_temperature_async",
        side_effect=TimeoutError(),
    ) as mock_get_temperature:
        await mock_config_entry.runtime_data.async_refresh()
        await hass.async_block_till_done()

        assert mock_get_temperature.call_count == 3
        assert mock_config_entry.runtime_data.last_update_success is False
        assert (state := hass.states.get(ENTITY_ID))
        assert state.attributes[ATTR_TEMPERATURE] == 20.0

    # Fail with OSError (unexpected) and raise UpdateFailed directly
    with patch.object(
        mock_config_entry.runtime_data.device,
        "get_temperature_async",
        side_effect=OSError(),
    ) as mock_get_temperature:
        await mock_config_entry.runtime_data.async_refresh()
        await hass.async_block_till_done()

        assert mock_get_temperature.call_count == 1
        assert mock_config_entry.runtime_data.last_update_success is False
        assert (state := hass.states.get(ENTITY_ID))
        assert state.attributes[ATTR_TEMPERATURE] == 20.0

    # Fail once with TimeoutError and then succeed, verify that data is updated
    updated_temperatures = dict(mock_config_entry.runtime_data.data.temperatures)
    updated_temperatures["manualTemp"] = 27.0

    with patch.object(
        mock_config_entry.runtime_data.device,
        "get_temperature_async",
        side_effect=[TimeoutError(), updated_temperatures],
    ) as mock_get_temperature:
        await mock_config_entry.runtime_data.async_refresh()
        await hass.async_block_till_done()

        assert mock_get_temperature.call_count == 2
        assert mock_config_entry.runtime_data.last_update_success is True
        assert (state := hass.states.get(ENTITY_ID))
        assert state.attributes[ATTR_TEMPERATURE] == 27.0
