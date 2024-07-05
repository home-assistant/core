"""Tests for the israel_rail sensor."""

from __future__ import annotations

from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from israelrailapi.api import TrainRoute

from homeassistant.core import HomeAssistant

from . import goto_future, init_integration

from tests.common import MockConfigEntry


async def test_valid_config(
    hass: HomeAssistant,
    mock_israelrail: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Ensure everything starts correctly."""
    await init_integration(hass, mock_config_entry)
    assert len(hass.states.async_entity_ids()) == 6


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
    assert len(hass.states.async_entity_ids()) == 6

    mock_israelrail.return_value.query.return_value = [
        TrainRoute(
            [
                {
                    "orignStation": "3500",
                    "destinationStation": "3700",
                    "departureTime": "2021-10-10T10:10:10",
                    "arrivalTime": "2021-10-10T10:10:10",
                    "originPlatform": "1",
                    "destPlatform": "2",
                    "trainNumber": "1234",
                }
            ]
        ),
        TrainRoute(
            [
                {
                    "orignStation": "3500",
                    "destinationStation": "3700",
                    "departureTime": "2021-10-10T10:10:10",
                    "arrivalTime": "2021-10-10T10:10:10",
                    "originPlatform": "1",
                    "destPlatform": "2",
                    "trainNumber": "1234",
                }
            ]
        ),
        TrainRoute(
            [
                {
                    "orignStation": "3500",
                    "destinationStation": "3700",
                    "departureTime": "2021-10-10T10:10:10",
                    "arrivalTime": "2021-10-10T10:10:10",
                    "originPlatform": "1",
                    "destPlatform": "2",
                    "trainNumber": "1234",
                }
            ]
        ),
        TrainRoute(
            [
                {
                    "orignStation": "3500",
                    "destinationStation": "3700",
                    "departureTime": "2021-10-10T10:10:10",
                    "arrivalTime": "2021-10-10T10:10:10",
                    "originPlatform": "1",
                    "destPlatform": "2",
                    "trainNumber": "1234",
                }
            ]
        ),
        TrainRoute(
            [
                {
                    "orignStation": "3500",
                    "destinationStation": "3700",
                    "departureTime": "2021-10-10T10:10:10",
                    "arrivalTime": "2021-10-10T10:10:10",
                    "originPlatform": "1",
                    "destPlatform": "2",
                    "trainNumber": "1234",
                }
            ]
        ),
    ]

    await goto_future(hass, freezer)

    assert len(hass.states.async_entity_ids()) == 6
