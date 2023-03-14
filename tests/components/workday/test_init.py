"""Tests for workday __init__."""
from typing import Any
from unittest.mock import MagicMock, patch

# from homeassistant.components.workday.const import DOMAIN
from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant, State
from homeassistant.setup import async_setup_component

from .fixtures import ASSUMED_DATE, SENSOR_DATA, USER_INPUT


@patch(
    "homeassistant.components.workday.binary_sensor.get_date",
    return_value=ASSUMED_DATE,
)
@patch("homeassistant.components.workday.util.get_date", return_value=ASSUMED_DATE)
async def test_async_setup(
    mock_get_date: MagicMock, mock_sensor_get_date: MagicMock, hass: HomeAssistant
) -> None:
    """Test async_setup."""
    config: dict[str, Any] = {"binary_sensor": [{"platform": "workday"}]}
    config["binary_sensor"][0].update(SENSOR_DATA)
    config["binary_sensor"][0].update(USER_INPUT)

    await async_setup_component(hass, "binary_sensor", config)
    await hass.async_block_till_done()

    sensor: State | None = hass.states.get("binary_sensor.workday_sensor")
    assert sensor is not None
    # On the assumed date, today is not a holiday and it is a work day
    assert sensor.state == STATE_ON


async def test_async_setup_empty(hass: HomeAssistant) -> None:
    """Test async_setup with a config not including a workday sensor."""
    config: dict[str, Any] = {"binary_sensor": [{"platform": "fake"}]}

    await async_setup_component(hass, "binary_sensor", config)
    await hass.async_block_till_done()

    binary_sensor_id_count = hass.states.async_entity_ids_count("binary_sensor")
    assert binary_sensor_id_count == 0
