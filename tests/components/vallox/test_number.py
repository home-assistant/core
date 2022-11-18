"""Tests for Vallox number platform."""
import pytest

from homeassistant.components.number.const import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

from .conftest import patch_metrics, patch_metrics_set

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    "entity_id, metric_key, value",
    [
        (
            "number.vallox_supply_air_temperature_home",
            "A_CYC_HOME_AIR_TEMP_TARGET",
            19.0,
        ),
        (
            "number.vallox_supply_air_temperature_away",
            "A_CYC_AWAY_AIR_TEMP_TARGET",
            18.0,
        ),
    ],
)
async def test_temperature_number_entities(
    entity_id: str,
    metric_key: str,
    value: float,
    mock_entry: MockConfigEntry,
    hass: HomeAssistant,
) -> None:
    """Test temperature entities."""
    # Arrange
    metrics = {metric_key: value}

    # Act
    with patch_metrics(metrics=metrics):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    # Assert
    sensor = hass.states.get(entity_id)
    assert sensor.state == str(value)
    assert sensor.attributes["unit_of_measurement"] == "°C"


@pytest.mark.parametrize(
    "entity_id, metric_key, value",
    [
        ("number.vallox_fan_speed_home", "A_CYC_HOME_SPEED_SETTING", 60),
        ("number.vallox_fan_speed_away", "A_CYC_AWAY_SPEED_SETTING", 30),
        ("number.vallox_fan_speed_boost", "A_CYC_BOOST_SPEED_SETTING", 100),
    ],
)
async def test_fan_speed_number_entities(
    entity_id: str,
    metric_key: str,
    value: int,
    mock_entry: MockConfigEntry,
    hass: HomeAssistant,
) -> None:
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


async def test_fan_speed_number_entitity_set(
    mock_entry: MockConfigEntry,
    hass: HomeAssistant,
) -> None:
    """Test fan speed set."""
    # Act
    with patch_metrics(metrics={}), patch_metrics_set() as metrics_set:
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            service_data={
                ATTR_ENTITY_ID: "number.vallox_fan_speed_home",
                ATTR_VALUE: 10,
            },
        )
        await hass.async_block_till_done()
        metrics_set.assert_called_once_with({"A_CYC_HOME_SPEED_SETTING": 10.0})
