"""Test DoorBird device."""

from copy import deepcopy
from http import HTTPStatus
from typing import Any

from doorbirdpy import DoorBirdScheduleEntry
import pytest

from homeassistant.components.doorbird.const import (
    CONF_EVENTS,
    DEFAULT_DOORBELL_EVENT,
    DEFAULT_MOTION_EVENT,
    DOMAIN,
)
from homeassistant.core import HomeAssistant

from . import VALID_CONFIG
from .conftest import DoorbirdMockerType

from tests.common import MockConfigEntry


@pytest.fixture
def doorbird_favorites_with_stale() -> dict[str, dict[str, Any]]:
    """Return favorites fixture with stale favorites from another HA instance.

    Creates favorites where identifier "2" has the same event name as "0"
    (mydoorbird_doorbell) but points to a different HA instance URL.
    These stale favorites should be filtered out.
    """
    return {
        "http": {
            "0": {
                "title": "Home Assistant (mydoorbird_doorbell)",
                "value": "http://127.0.0.1:8123/api/doorbird/mydoorbird_doorbell?token=test-token",
            },
            # Stale favorite from a different HA instance - should be filtered out
            "2": {
                "title": "Home Assistant (mydoorbird_doorbell)",
                "value": "http://old-ha-instance:8123/api/doorbird/mydoorbird_doorbell?token=old-token",
            },
            "5": {
                "title": "Home Assistant (mydoorbird_motion)",
                "value": "http://127.0.0.1:8123/api/doorbird/mydoorbird_motion?token=test-token",
            },
        }
    }


@pytest.fixture
def doorbird_schedule_with_stale() -> list[DoorBirdScheduleEntry]:
    """Return schedule fixture with outputs referencing stale favorites.

    Both param "0" and "2" map to doorbell input, but "2" is a stale favorite.
    """
    schedule_data = [
        {
            "input": "doorbell",
            "param": "1",
            "output": [
                {
                    "event": "http",
                    "param": "0",
                    "schedule": {"weekdays": [{"to": "107999", "from": "108000"}]},
                },
                {
                    "event": "http",
                    "param": "2",
                    "schedule": {"weekdays": [{"to": "107999", "from": "108000"}]},
                },
            ],
        },
        {
            "input": "motion",
            "param": "",
            "output": [
                {
                    "event": "http",
                    "param": "5",
                    "schedule": {"weekdays": [{"to": "107999", "from": "108000"}]},
                },
            ],
        },
    ]
    return DoorBirdScheduleEntry.parse_all(schedule_data)


async def test_stale_favorites_filtered_by_url(
    hass: HomeAssistant,
    doorbird_mocker: DoorbirdMockerType,
    doorbird_favorites_with_stale: dict[str, dict[str, Any]],
    doorbird_schedule_with_stale: list[DoorBirdScheduleEntry],
) -> None:
    """Test that stale favorites from other HA instances are filtered out."""
    await doorbird_mocker(
        favorites=doorbird_favorites_with_stale,
        schedule=doorbird_schedule_with_stale,
    )
    # Should have 2 event entities - stale favorite "2" is filtered out
    # because its URL doesn't match the current HA instance
    event_entities = hass.states.async_all("event")
    assert len(event_entities) == 2


async def test_custom_url_used_for_favorites(
    hass: HomeAssistant,
    doorbird_mocker: DoorbirdMockerType,
) -> None:
    """Test that custom URL override is used instead of get_url."""
    custom_url = "https://my-custom-url.example.com:8443"
    favorites = {
        "http": {
            "1": {
                "title": "Home Assistant (mydoorbird_doorbell)",
                "value": f"{custom_url}/api/doorbird/mydoorbird_doorbell?token=test-token",
            },
            "2": {
                "title": "Home Assistant (mydoorbird_motion)",
                "value": f"{custom_url}/api/doorbird/mydoorbird_motion?token=test-token",
            },
        }
    }
    config_with_custom_url = {
        **VALID_CONFIG,
        "hass_url_override": custom_url,
    }
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="1CCAE3AAAAAA",
        data=config_with_custom_url,
        options={CONF_EVENTS: [DEFAULT_DOORBELL_EVENT, DEFAULT_MOTION_EVENT]},
    )
    await doorbird_mocker(entry=entry, favorites=favorites)

    # Should have 2 event entities using the custom URL
    event_entities = hass.states.async_all("event")
    assert len(event_entities) == 2


async def test_no_configured_events(
    hass: HomeAssistant,
    doorbird_mocker: DoorbirdMockerType,
) -> None:
    """Test a doorbird with no events configured."""
    await doorbird_mocker(options={CONF_EVENTS: []})
    assert not hass.states.async_all("event")


async def test_change_schedule_success(
    doorbird_mocker: DoorbirdMockerType,
    doorbird_schedule_wrong_param: list[DoorBirdScheduleEntry],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a doorbird when change_schedule fails."""
    schedule_copy = deepcopy(doorbird_schedule_wrong_param)
    mock_doorbird = await doorbird_mocker(schedule=schedule_copy)
    assert "Unable to update schedule entry mydoorbird" not in caplog.text
    assert mock_doorbird.api.change_schedule.call_count == 1
    new_schedule: list[DoorBirdScheduleEntry] = (
        mock_doorbird.api.change_schedule.call_args[0]
    )
    # Ensure the attempt to update the schedule to fix the incorrect
    # param is made
    assert new_schedule[-1].output[-1].param == "1"


async def test_change_schedule_fails(
    doorbird_mocker: DoorbirdMockerType,
    doorbird_schedule_wrong_param: list[DoorBirdScheduleEntry],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a doorbird when change_schedule fails."""
    schedule_copy = deepcopy(doorbird_schedule_wrong_param)
    mock_doorbird = await doorbird_mocker(
        schedule=schedule_copy, change_schedule=(False, HTTPStatus.UNAUTHORIZED)
    )
    assert "Unable to update schedule entry mydoorbird" in caplog.text
    assert mock_doorbird.api.change_schedule.call_count == 1
    new_schedule: list[DoorBirdScheduleEntry] = (
        mock_doorbird.api.change_schedule.call_args[0]
    )
    # Ensure the attempt to update the schedule to fix the incorrect
    # param is made
    assert new_schedule[-1].output[-1].param == "1"
