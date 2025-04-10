"""Test Volvo sensors."""

from unittest.mock import patch

import pytest

from homeassistant.components.volvo.const import (
    OPT_FUEL_CONSUMPTION_UNIT,
    OPT_FUEL_UNIT_LITER_PER_100KM,
    OPT_FUEL_UNIT_MPG_UK,
    OPT_FUEL_UNIT_MPG_US,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .conftest import model

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("unit", "value", "unit_of_measurement"),
    [
        (
            OPT_FUEL_UNIT_LITER_PER_100KM,
            "7.2",
            "L/100 km",
        ),
        (
            OPT_FUEL_UNIT_MPG_UK,
            "39.07",
            "mpg",
        ),
        (
            OPT_FUEL_UNIT_MPG_US,
            "32.53",
            "mpg",
        ),
    ],
)
@model("xc90_petrol_2019")
async def test_fuel_unit_conversion(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    unit: str,
    value: str,
    unit_of_measurement: str,
) -> None:
    """Test fuel unit conversion."""

    entity_id = "sensor.volvo_xc90_petrol_2019_tm_avg_fuel_consumption"

    with patch("homeassistant.components.volvo.PLATFORMS", [Platform.SENSOR]):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        hass.config_entries.async_update_entry(
            mock_config_entry,
            options={OPT_FUEL_CONSUMPTION_UNIT: unit},
        )
        await hass.async_block_till_done()

        entity = hass.states.get(entity_id)
        assert entity
        assert entity.state == value
        assert entity.attributes.get("unit_of_measurement") == unit_of_measurement


@pytest.mark.parametrize(
    ("expected_state"),
    [
        pytest.param(23 * 30, marks=model("xc40_electric_2024")),
        pytest.param(17, marks=model("s90_diesel_2018")),
    ],
)
async def test_time_to_service(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    model_from_marker: str,
    expected_state: int,
) -> None:
    """Test time to service."""

    entity_id = f"sensor.volvo_{model_from_marker}_time_to_service"

    with patch("homeassistant.components.volvo.PLATFORMS", [Platform.SENSOR]):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        entity = hass.states.get(entity_id)
        assert entity
        assert entity.state == f"{expected_state}"
