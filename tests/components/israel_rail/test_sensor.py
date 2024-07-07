"""Tests for the israel_rail sensor."""

from __future__ import annotations

from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory

from homeassistant.core import HomeAssistant

from . import goto_future, init_integration
from .conftest import trains, trains_wrong_format

from tests.common import MockConfigEntry


async def test_valid_config(
    hass: HomeAssistant,
    mock_israelrail: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Ensure everything starts correctly."""
    await init_integration(hass, mock_config_entry)
    assert len(hass.states.async_entity_ids()) == 7
    assert hass.states.get("sensor.mock_title_departure")
    assert hass.states.get("sensor.mock_title_departure_1")
    assert hass.states.get("sensor.mock_title_departure_2")
    assert hass.states.get("sensor.mock_title_duration")
    assert hass.states.get("sensor.mock_title_transfers")
    assert hass.states.get("sensor.mock_title_platform")
    assert hass.states.get("sensor.mock_title_train_number")


async def test_invalid_config(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Ensure nothing is created when config is wrong."""
    await init_integration(hass, mock_config_entry)
    assert not hass.states.async_entity_ids("sensor")


async def test_update_train(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_israelrail: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Ensure the train data is updated."""
    await init_integration(hass, mock_config_entry)
    assert len(hass.states.async_entity_ids()) == 7
    departure_sensor = hass.states.get("sensor.mock_title_departure")
    assert departure_sensor.state == "2021-10-10T07:10:10+00:00"

    mock_israelrail.return_value.query.return_value = trains[1:]

    await goto_future(hass, freezer)

    assert len(hass.states.async_entity_ids()) == 7
    departure_sensor = hass.states.get("sensor.mock_title_departure")
    assert departure_sensor.state == "2021-10-10T07:20:10+00:00"


async def test_no_duration_wrong_date_format(
    hass: HomeAssistant,
    mock_israelrail: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Ensure the duration is not set when there is no departure time."""
    mock_israelrail.return_value.query.return_value = trains_wrong_format
    await init_integration(hass, mock_config_entry)
    assert len(hass.states.async_entity_ids()) == 7
    departure_sensor = hass.states.get("sensor.mock_title_train_number")
    assert departure_sensor.state == "1234"
    duration_sensor = hass.states.get("sensor.mock_title_duration")
    assert duration_sensor.state == "unknown"


async def test_fail_query(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_israelrail: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Ensure the integration handles query failures."""
    await init_integration(hass, mock_config_entry)
    assert len(hass.states.async_entity_ids()) == 7
    mock_israelrail.return_value.query.side_effect = Exception("error")
    await goto_future(hass, freezer)
    assert len(hass.states.async_entity_ids()) == 7
    departure_sensor = hass.states.get("sensor.mock_title_departure")
    assert departure_sensor.state == "unavailable"
