"""The tests for the Islamic prayer times sensor platform."""
from datetime import timedelta
import json

from freezegun import freeze_time
import pytest
import requests_mock

from homeassistant.components.islamic_prayer_times.const import DOMAIN
from homeassistant.components.islamic_prayer_times.sensor import SENSOR_TYPES
from homeassistant.core import HomeAssistant
from homeassistant.util import slugify

from . import NOW, REQUEST_URL

from tests.common import MockConfigEntry, async_fire_time_changed, load_fixture


@pytest.fixture(autouse=True)
def set_utc(hass: HomeAssistant) -> None:
    """Set timezone to UTC."""
    hass.config.set_time_zone("UTC")


async def test_islamic_prayer_times_sensors(
    hass: HomeAssistant, requests_mock: requests_mock.Mocker
) -> None:
    """Test minimum Islamic prayer times configuration."""
    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)

    prayer_times_json = load_fixture("prayer_times.json", "islamic_prayer_times")
    prayer_times = json.loads(prayer_times_json)
    new_prayer_times_json = load_fixture(
        "new_prayer_times.json", "islamic_prayer_times"
    )
    new_prayer_times = json.loads(new_prayer_times_json)

    requests_mock.register_uri(
        "GET",
        REQUEST_URL,
        [
            {"text": prayer_times_json},
            {"text": new_prayer_times_json},
        ],
    )
    with freeze_time(NOW):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    for prayer in SENSOR_TYPES:
        assert (
            hass.states.get(f"sensor.{DOMAIN}_{slugify(prayer.name)}").state
            == prayer_times["data"]["timings"][prayer.key]
        )

    # trigger an update and ensure new times are fetched
    with freeze_time(NOW + timedelta(days=1)):
        async_fire_time_changed(hass, NOW + timedelta(days=1))
        await hass.async_block_till_done()

    for prayer in SENSOR_TYPES:
        assert (
            hass.states.get(f"sensor.{DOMAIN}_{slugify(prayer.name)}").state
            == new_prayer_times["data"]["timings"][prayer.key]
        )
