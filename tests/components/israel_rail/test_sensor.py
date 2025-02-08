"""Tests for the israel_rail sensor."""

from __future__ import annotations

from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from syrupy import SnapshotAssertion

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import goto_future, init_integration
from .conftest import TRAINS, get_time

from tests.common import MockConfigEntry, snapshot_platform


async def test_valid_config(
    hass: HomeAssistant,
    mock_israelrail: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Ensure everything starts correctly."""
    await init_integration(hass, mock_config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_update_train(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_israelrail: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Ensure the train data is updated."""
    await init_integration(hass, mock_config_entry)
    assert len(hass.states.async_entity_ids()) == 6
    departure_sensor = hass.states.get("sensor.mock_title_departure")
    expected_time = get_time(10, 10)
    assert departure_sensor.state == expected_time

    mock_israelrail.query.return_value = TRAINS[1:]

    await goto_future(hass, freezer)

    assert len(hass.states.async_entity_ids()) == 6
    departure_sensor = hass.states.get("sensor.mock_title_departure")
    expected_time = get_time(10, 20)
    assert departure_sensor.state == expected_time


async def test_fail_query(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_israelrail: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Ensure the integration handles query failures."""
    await init_integration(hass, mock_config_entry)
    assert len(hass.states.async_entity_ids()) == 6
    mock_israelrail.query.side_effect = Exception("error")
    await goto_future(hass, freezer)
    assert len(hass.states.async_entity_ids()) == 6
    departure_sensor = hass.states.get("sensor.mock_title_departure")
    assert departure_sensor.state == STATE_UNAVAILABLE
