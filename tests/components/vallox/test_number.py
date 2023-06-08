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

TEST_TEMPERATURE_ENTITIES_DATA = [
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
    (
        "number.vallox_supply_air_temperature_boost",
        "A_CYC_BOOST_AIR_TEMP_TARGET",
        17.0,
    ),
]


@pytest.mark.parametrize(
    ("entity_id", "metric_key", "value"), TEST_TEMPERATURE_ENTITIES_DATA
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
    ("entity_id", "metric_key", "value"), TEST_TEMPERATURE_ENTITIES_DATA
)
async def test_temperature_number_entity_set(
    entity_id: str,
    metric_key: str,
    value: float,
    mock_entry: MockConfigEntry,
    hass: HomeAssistant,
) -> None:
    """Test temperature set."""
    # Act
    with patch_metrics(metrics={}), patch_metrics_set() as metrics_set:
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            service_data={
                ATTR_ENTITY_ID: entity_id,
                ATTR_VALUE: value,
            },
        )
        await hass.async_block_till_done()
        metrics_set.assert_called_once_with({metric_key: value})
