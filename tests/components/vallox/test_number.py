"""Tests for Vallox number platform."""
import pytest

from homeassistant.core import HomeAssistant

from .conftest import patch_metrics

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    "entity_id,metric_key, value",
    [
        ("number.vallox_supply_air_temperature_home", "A_CYC_HOME_AIR_TEMP_TARGET", 19),
        ("number.vallox_supply_air_temperature_away", "A_CYC_AWAY_AIR_TEMP_TARGET", 18),
    ],
)
async def test_temperature_number_entities(
    entity_id, metric_key, value, mock_entry: MockConfigEntry, hass: HomeAssistant
):
    """Test temperature entities."""
    # Arrange
    metrics = {metric_key: value}

    # Act
    with patch_metrics(metrics=metrics):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    # Assert
    sensor = hass.states.get(entity_id)
    assert sensor.state == str(float(value))
    assert sensor.attributes["unit_of_measurement"] == "°C"


@pytest.mark.parametrize(
    "entity_id,metric_key, value",
    [
        ("number.vallox_fan_speed_home", "A_CYC_HOME_SPEED_SETTING", 60),
        ("number.vallox_fan_speed_away", "A_CYC_AWAY_SPEED_SETTING", 30),
        ("number.vallox_fan_speed_boost", "A_CYC_BOOST_SPEED_SETTING", 100),
    ],
)
async def test_fan_speed_number_entities(
    entity_id, metric_key, value, mock_entry: MockConfigEntry, hass: HomeAssistant
):
    """Test fan speed entities."""
    # Arrange
    metrics = {metric_key: value}

    # Act
    with patch_metrics(metrics=metrics):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    # Assert
    sensor = hass.states.get(entity_id)
    assert sensor.state == str(float(value))
    assert sensor.attributes["unit_of_measurement"] == "%"
