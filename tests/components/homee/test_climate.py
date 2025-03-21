"""Test homee climate entities."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components.climate import ClimateEntityFeature, HVACMode
from homeassistant.core import HomeAssistant

from . import build_mock_node, setup_integration

from tests.common import MockConfigEntry


async def setup_mock_climate(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_homee: MagicMock,
    file: str,
) -> None:
    """Setups a climate node for the tests."""
    mock_homee.nodes = [build_mock_node(file)]
    mock_homee.get_node_by_id.return_value = mock_homee.nodes[0]
    await setup_integration(hass, mock_config_entry)


@pytest.mark.parametrize(
    ("file", "entity_id", "features", "hvac_modes"),
    [
        (
            "thermostat_only_targettemp.json",
            "climate.test_thermostat_1",
            ClimateEntityFeature.TARGET_TEMPERATURE,
            [HVACMode.HEAT],
        ),
        (
            "thermostat_with_currenttemp.json",
            "climate.test_thermostat_2",
            ClimateEntityFeature.TARGET_TEMPERATURE,
            [HVACMode.HEAT],
        ),
        (
            "thermostat_with_heating_mode.json",
            "climate.test_thermostat_3",
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.TURN_ON
            | ClimateEntityFeature.TURN_OFF,
            [HVACMode.HEAT, HVACMode.OFF],
        ),
        (
            "thermostat_with_preset.json",
            "climate.test_thermostat_4",
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.TURN_ON
            | ClimateEntityFeature.TURN_OFF
            | ClimateEntityFeature.PRESET_MODE,
            [HVACMode.HEAT, HVACMode.OFF],
        ),
    ],
)
async def test_climate_features(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_homee: MagicMock,
    file: str,
    entity_id: str,
    features: ClimateEntityFeature,
    hvac_modes: list[HVACMode],
) -> None:
    """Test available features of cliamte entities."""
    await setup_mock_climate(hass, mock_config_entry, mock_homee, file)

    attributes = hass.states.get(entity_id).attributes
    assert attributes["supported_features"] == features
    assert attributes["hvac_modes"] == hvac_modes


async def test_climate_preset_modes(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_homee: MagicMock,
) -> None:
    """Test available preset modes of climate entities."""
    await setup_mock_climate(
        hass, mock_config_entry, mock_homee, "thermostat_with_preset.json"
    )

    attributes = hass.states.get("climate.test_thermostat_4").attributes
    assert attributes["preset_modes"] == ["boost", "eco", "manual", "none"]
