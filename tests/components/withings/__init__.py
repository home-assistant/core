"""Tests for the withings component."""

from dataclasses import dataclass
from datetime import timedelta
from typing import Any
from urllib.parse import urlparse

from aiohttp.test_utils import TestClient
from aiowithings import Activity, Device, Goals, MeasurementGroup, SleepSummary, Workout
from freezegun.api import FrozenDateTimeFactory

from homeassistant.components.webhook import async_generate_url
from homeassistant.config import async_process_ha_core_config
from homeassistant.core import HomeAssistant

from tests.common import (
    MockConfigEntry,
    async_fire_time_changed,
    load_json_array_fixture,
    load_json_object_fixture,
)


@dataclass
class WebhookResponse:
    """Response data from a webhook."""

    message: str
    message_code: int


async def call_webhook(
    hass: HomeAssistant, webhook_id: str, data: dict[str, Any], client: TestClient
) -> WebhookResponse:
    """Call the webhook."""
    webhook_url = async_generate_url(hass, webhook_id)

    resp = await client.post(
        urlparse(webhook_url).path,
        data=data,
    )

    # Wait for remaining tasks to complete.
    await hass.async_block_till_done()

    data = await resp.json()
    resp.close()

    return WebhookResponse(message=data["message"], message_code=data["code"])


async def setup_integration(
    hass: HomeAssistant, config_entry: MockConfigEntry, enable_webhooks: bool = True
) -> None:
    """Fixture for setting up the component."""
    config_entry.add_to_hass(hass)

    if enable_webhooks:
        await async_process_ha_core_config(
            hass,
            {"external_url": "https://example.com"},
        )

    await hass.config_entries.async_setup(config_entry.entry_id)


async def prepare_webhook_setup(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Prepare webhooks are registered by waiting a second."""
    freezer.tick(timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


def load_goals_fixture(fixture: str = "withings/goals.json") -> Goals:
    """Return goals from fixture."""
    goals_json = load_json_object_fixture(fixture)
    return Goals.from_api(goals_json)


def load_measurements_fixture(
    fixture: str = "withings/measurements.json",
) -> list[MeasurementGroup]:
    """Return measurement from fixture."""
    meas_json = load_json_array_fixture(fixture)
    return [MeasurementGroup.from_api(measurement) for measurement in meas_json]


def load_activity_fixture(
    fixture: str = "withings/activity.json",
) -> list[Activity]:
    """Return activities from fixture."""
    activity_json = load_json_array_fixture(fixture)
    return [Activity.from_api(activity) for activity in activity_json]


def load_workout_fixture(
    fixture: str = "withings/workouts.json",
) -> list[Workout]:
    """Return workouts from fixture."""
    workouts_json = load_json_array_fixture(fixture)
    return [Workout.from_api(workout) for workout in workouts_json]


def load_sleep_fixture(
    fixture: str = "withings/sleep_summaries.json",
) -> list[SleepSummary]:
    """Return sleep summaries from fixture."""
    sleep_json = load_json_array_fixture("withings/sleep_summaries.json")
    return [SleepSummary.from_api(sleep_summary) for sleep_summary in sleep_json]


def load_device_fixture(
    fixture: str = "withings/devices.json",
) -> list[Device]:
    """Return sleep summaries from fixture."""
    devices_json = load_json_array_fixture(fixture)
    return [Device.from_api(device) for device in devices_json]
