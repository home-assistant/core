"""Tests for the BSB-Lan climate platform."""

from unittest.mock import AsyncMock, PropertyMock, patch

from bsblan import BSBLANError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.bsblan.climate import BSBLANClimate
from homeassistant.components.bsblan.const import ATTR_TARGET_TEMPERATURE
from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    ATTR_PRESET_MODE,
    DOMAIN as CLIMATE_DOMAIN,
    PRESET_ECO,
    PRESET_NONE,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
import homeassistant.helpers.entity_registry as er

from . import setup_with_selected_platforms

from tests.common import MockConfigEntry, snapshot_platform

ENTITY_ID = "climate.bsb_lan"


@pytest.mark.parametrize("static_file", ["static.json"])
async def test_climate_entity_properties(
    hass: HomeAssistant,
    mock_bsblan: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    static_file: str,
) -> None:
    """Test the initial parameters in Celsius."""
    await mock_bsblan.set_static_values(static_file)
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.CLIMATE])
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)

    climate_entity = hass.data[CLIMATE_DOMAIN].get_entity(ENTITY_ID)

    # Test when current_temperature is "---"
    with patch.object(
        mock_bsblan.state.return_value.current_temperature, "value", "---"
    ):
        await hass.helpers.entity_component.async_update_entity(ENTITY_ID)
        state = hass.states.get(ENTITY_ID)
        assert state.attributes["current_temperature"] is None

    # Test target_temperature
    target_temperature = 16.2
    with patch.object(
        mock_bsblan.state.return_value.target_temperature, "value", target_temperature
    ):
        await hass.helpers.entity_component.async_update_entity(ENTITY_ID)
        state = hass.states.get(ENTITY_ID)
        assert state.attributes["temperature"] == target_temperature

    # Test hvac_mode when preset_mode is ECO
    with patch.object(mock_bsblan.state.return_value.hvac_mode, "value", PRESET_ECO):
        assert climate_entity.hvac_mode == HVACMode.AUTO

    # Test hvac_mode with other values
    with patch.object(mock_bsblan.state.return_value.hvac_mode, "value", HVACMode.HEAT):
        assert climate_entity.hvac_mode == HVACMode.HEAT

    # Test preset_mode
    with patch.object(
        BSBLANClimate, "hvac_mode", new_callable=PropertyMock
    ) as mock_hvac_mode:
        mock_hvac_mode.return_value = HVACMode.AUTO
        mock_bsblan.state.return_value.hvac_mode.value = PRESET_ECO
        await hass.helpers.entity_component.async_update_entity(ENTITY_ID)
        state = hass.states.get(ENTITY_ID)
        assert state.attributes["preset_mode"] == PRESET_ECO


@pytest.mark.parametrize("static_file", ["static.json"])
@pytest.mark.parametrize(
    ("mode", "expected_call"),
    [
        (HVACMode.HEAT, HVACMode.HEAT),
        (HVACMode.COOL, HVACMode.COOL),
        (HVACMode.AUTO, HVACMode.AUTO),
        (HVACMode.OFF, HVACMode.OFF),
    ],
)
async def test_async_set_hvac_mode(
    hass: HomeAssistant,
    mock_bsblan: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    static_file: str,
    mode: str,
    expected_call: str,
) -> None:
    """Test the async_set_hvac_mode function."""
    await mock_bsblan.set_static_values(static_file)
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.CLIMATE])

    climate_entity = hass.data[CLIMATE_DOMAIN].get_entity(ENTITY_ID)

    with patch.object(climate_entity, "async_set_data") as mock_set_data:
        await climate_entity.async_set_hvac_mode(mode)
        mock_set_data.assert_called_once_with(hvac_mode=expected_call)


@pytest.mark.parametrize("static_file", ["static.json"])
@pytest.mark.parametrize(
    ("hvac_mode", "preset_mode", "expected_call"),
    [
        (HVACMode.AUTO, PRESET_ECO, PRESET_ECO),
        (HVACMode.AUTO, PRESET_NONE, PRESET_NONE),
        (HVACMode.HEAT, PRESET_ECO, None),
    ],
)
async def test_async_set_preset_mode(
    hass: HomeAssistant,
    mock_bsblan: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    static_file: str,
    hvac_mode: str,
    preset_mode: str,
    expected_call: str | None,
) -> None:
    """Test the async_set_preset_mode function."""
    await mock_bsblan.set_static_values(static_file)
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.CLIMATE])

    climate_entity = hass.data[CLIMATE_DOMAIN].get_entity(ENTITY_ID)

    with patch(
        "homeassistant.components.bsblan.climate.BSBLANClimate.hvac_mode",
        new_callable=PropertyMock,
    ) as mock_hvac_mode:
        mock_hvac_mode.return_value = hvac_mode

        if expected_call is None:
            with pytest.raises(ServiceValidationError) as exc_info:
                await climate_entity.async_set_preset_mode(preset_mode)
            assert exc_info.value.translation_key == "set_preset_mode_error"
        else:
            with patch.object(climate_entity, "async_set_data") as mock_set_data:
                await climate_entity.async_set_preset_mode(preset_mode)
                mock_set_data.assert_called_once_with(preset_mode=expected_call)


@pytest.mark.parametrize("static_file", ["static.json"])
async def test_async_set_temperature(
    hass: HomeAssistant,
    mock_bsblan: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    static_file: str,
) -> None:
    """Test the async_set_temperature function."""
    await mock_bsblan.set_static_values(static_file)
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.CLIMATE])

    climate_entity = hass.data[CLIMATE_DOMAIN].get_entity(ENTITY_ID)

    # Test setting temperature within the allowed range
    with patch.object(climate_entity, "async_set_data") as mock_set_data:
        test_temp = (climate_entity.min_temp + climate_entity.max_temp) / 2
        await climate_entity.async_set_temperature(**{ATTR_TEMPERATURE: test_temp})
        mock_set_data.assert_called_once_with(**{ATTR_TEMPERATURE: test_temp})

    # Test setting temperature to the minimum allowed value
    with patch.object(climate_entity, "async_set_data") as mock_set_data:
        await climate_entity.async_set_temperature(
            **{ATTR_TEMPERATURE: climate_entity.min_temp}
        )
        mock_set_data.assert_called_once_with(
            **{ATTR_TEMPERATURE: climate_entity.min_temp}
        )

    # Test setting temperature to the maximum allowed value
    with patch.object(climate_entity, "async_set_data") as mock_set_data:
        await climate_entity.async_set_temperature(
            **{ATTR_TEMPERATURE: climate_entity.max_temp}
        )
        mock_set_data.assert_called_once_with(
            **{ATTR_TEMPERATURE: climate_entity.max_temp}
        )

    # Test setting temperature with additional parameters
    with patch.object(climate_entity, "async_set_data") as mock_set_data:
        test_temp = (climate_entity.min_temp + climate_entity.max_temp) / 2
        additional_param = "test_param"
        await climate_entity.async_set_temperature(
            **{ATTR_TEMPERATURE: test_temp, additional_param: "value"}
        )
        mock_set_data.assert_called_once_with(
            **{ATTR_TEMPERATURE: test_temp, additional_param: "value"}
        )


@pytest.mark.parametrize("static_file", ["static.json"])
async def test_async_set_data(
    hass: HomeAssistant,
    mock_bsblan: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    static_file: str,
) -> None:
    """Test the async_set_data function."""
    await mock_bsblan.set_static_values(static_file)
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.CLIMATE])

    climate_entity = hass.data[CLIMATE_DOMAIN].get_entity(ENTITY_ID)

    # Test setting temperature
    with (
        patch.object(
            climate_entity.coordinator.client, "thermostat"
        ) as mock_thermostat,
        patch.object(
            climate_entity.coordinator, "async_request_refresh"
        ) as mock_refresh,
    ):
        await climate_entity.async_set_data(**{ATTR_TEMPERATURE: 22})
        mock_thermostat.assert_called_once_with(**{ATTR_TARGET_TEMPERATURE: 22})
        mock_refresh.assert_called_once()

    # Test setting HVAC mode
    with (
        patch.object(
            climate_entity.coordinator.client, "thermostat"
        ) as mock_thermostat,
        patch.object(
            climate_entity.coordinator, "async_request_refresh"
        ) as mock_refresh,
    ):
        await climate_entity.async_set_data(**{ATTR_HVAC_MODE: HVACMode.HEAT})
        mock_thermostat.assert_called_once_with(**{ATTR_HVAC_MODE: HVACMode.HEAT})
        mock_refresh.assert_called_once()

    # Test setting preset mode to NONE
    with (
        patch.object(
            climate_entity.coordinator.client, "thermostat"
        ) as mock_thermostat,
        patch.object(
            climate_entity.coordinator, "async_request_refresh"
        ) as mock_refresh,
    ):
        await climate_entity.async_set_data(**{ATTR_PRESET_MODE: PRESET_NONE})
        mock_thermostat.assert_called_once_with(**{ATTR_HVAC_MODE: HVACMode.AUTO})
        mock_refresh.assert_called_once()

    # Test setting preset mode to a non-NONE value
    with (
        patch.object(
            climate_entity.coordinator.client, "thermostat"
        ) as mock_thermostat,
        patch.object(
            climate_entity.coordinator, "async_request_refresh"
        ) as mock_refresh,
    ):
        await climate_entity.async_set_data(**{ATTR_PRESET_MODE: "eco"})
        mock_thermostat.assert_called_once_with(**{ATTR_HVAC_MODE: "eco"})
        mock_refresh.assert_called_once()

    # Test setting multiple parameters
    with (
        patch.object(
            climate_entity.coordinator.client, "thermostat"
        ) as mock_thermostat,
        patch.object(
            climate_entity.coordinator, "async_request_refresh"
        ) as mock_refresh,
    ):
        await climate_entity.async_set_data(
            **{ATTR_TEMPERATURE: 23, ATTR_HVAC_MODE: HVACMode.COOL}
        )
        mock_thermostat.assert_called_once_with(
            **{ATTR_TARGET_TEMPERATURE: 23, ATTR_HVAC_MODE: HVACMode.COOL}
        )
        mock_refresh.assert_called_once()

    # Test error handling
    with (
        patch.object(
            climate_entity.coordinator.client,
            "thermostat",
            side_effect=BSBLANError("Test error"),
        ),
        pytest.raises(HomeAssistantError) as exc_info,
    ):
        await climate_entity.async_set_data(**{ATTR_TEMPERATURE: 24})

    assert "An error occurred while updating the BSBLAN device" in str(exc_info.value)
    assert exc_info.value.translation_key == "set_data_error"
