"""Test consumption requests in Home Assistant's configured timezone."""

from datetime import timedelta
from unittest.mock import patch

from aioflo.errors import RequestError
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM

CONSUMPTION_ENTITY = "sensor.smart_water_shutoff_today_s_water_usage"


def consumption_queries(aioclient_mock: AiohttpClientMocker) -> list[dict[str, str]]:
    """Return the actual query parameters serialized by aioflo."""
    return [
        dict(url.query)
        for method, url, _, _ in aioclient_mock.mock_calls
        if method == "get" and url.path == "/api/v2/water/consumption"
    ]


def assert_consumption_queries(
    aioclient_mock: AiohttpClientMocker, timezone: str, day: str
) -> None:
    """Both devices retain their MAC and use the same local calendar day."""
    assert sorted(
        consumption_queries(aioclient_mock), key=lambda query: query["macAddress"]
    ) == [
        {
            "startDate": f"{day}T00:00:00",
            "endDate": f"{day}T23:59:59.999000",
            "interval": "1h",
            "locationId": "mmnnoopp",
            "macAddress": mac,
            "tz": timezone,
        }
        for mac in ("111111111111", "1a2b3c4d5e6f")
    ]


@pytest.mark.parametrize(
    ("timezone", "utc_time", "day"),
    [
        pytest.param("UTC", "2026-01-01T00:00:00Z", "2026-01-01", id="utc"),
        pytest.param(
            "America/Los_Angeles",
            "2026-01-01T07:59:59Z",
            "2025-12-31",
            id="negative-offset-previous-year",
        ),
        pytest.param(
            "Asia/Kathmandu",
            "2026-01-01T18:15:00Z",
            "2026-01-02",
            id="fractional-positive-offset-next-day",
        ),
        pytest.param(
            "America/New_York",
            "2026-03-08T06:59:59Z",
            "2026-03-08",
            id="before-spring-forward",
        ),
        pytest.param(
            "America/New_York",
            "2026-03-08T07:00:00Z",
            "2026-03-08",
            id="after-spring-forward",
        ),
        pytest.param(
            "America/New_York",
            "2026-11-01T05:30:00Z",
            "2026-11-01",
            id="first-fall-back-hour",
        ),
        pytest.param(
            "America/New_York",
            "2026-11-01T06:30:00Z",
            "2026-11-01",
            id="second-fall-back-hour",
        ),
    ],
)
@pytest.mark.usefixtures("aioclient_mock_fixture")
async def test_consumption_local_day(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
    timezone: str,
    utc_time: str,
    day: str,
) -> None:
    """HA local dates and timezone reach the API without changing sensor IDs/units."""
    freezer.move_to(utc_time)
    await hass.config.async_set_time_zone(timezone)
    hass.config.units = US_CUSTOMARY_SYSTEM
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert_consumption_queries(aioclient_mock, timezone, day)
    assert hass.states.get(CONSUMPTION_ENTITY).state == "3.7"
    assert hass.states.get("sensor.kitchen_sink_temperature").state == "61"


@pytest.mark.usefixtures("aioclient_mock_fixture")
async def test_consumption_rollover_timezone_change_and_unload(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Polling follows local midnight and config changes, then stops on unload."""
    freezer.move_to("2026-03-08T04:59:30Z")
    await hass.config.async_set_time_zone("America/New_York")
    hass.config.units = US_CUSTOMARY_SYSTEM
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert_consumption_queries(aioclient_mock, "America/New_York", "2026-03-07")

    aioclient_mock.mock_calls.clear()
    freezer.tick(timedelta(seconds=65))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert_consumption_queries(aioclient_mock, "America/New_York", "2026-03-08")
    assert hass.states.get(CONSUMPTION_ENTITY).state == "3.7"

    aioclient_mock.mock_calls.clear()
    await hass.config.async_update(time_zone="America/Los_Angeles")
    freezer.tick(timedelta(seconds=65))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert_consumption_queries(aioclient_mock, "America/Los_Angeles", "2026-03-07")
    assert hass.states.get(CONSUMPTION_ENTITY).state == "3.7"

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    aioclient_mock.mock_calls.clear()
    freezer.tick(timedelta(seconds=90))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert aioclient_mock.call_count == 0
    assert hass.states.get(CONSUMPTION_ENTITY).state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("aioclient_mock_fixture")
async def test_consumption_failure_isolated_and_recovers(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A failed consumption request preserves buffering and other device updates."""
    freezer.move_to("2026-11-01T05:59:30Z")
    await hass.config.async_set_time_zone("America/New_York")
    hass.config.units = US_CUSTOMARY_SYSTEM
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    water = config_entry.runtime_data.client.water
    request = water._request

    async def fail_valve_consumption(
        method: str, url: str, *, params: dict[str, str]
    ) -> dict:
        if params["macAddress"] == "111111111111":
            raise RequestError("Consumption unavailable")
        return await request(method, url, params=params)

    with patch.object(water, "_request", side_effect=fail_valve_consumption):
        for expected in ("3.7", "3.7", "3.7", STATE_UNAVAILABLE):
            aioclient_mock.mock_calls.clear()
            freezer.tick(timedelta(seconds=65))
            async_fire_time_changed(hass)
            await hass.async_block_till_done()
            assert hass.states.get(CONSUMPTION_ENTITY).state == expected
            assert hass.states.get("sensor.kitchen_sink_temperature").state == "61"
            assert consumption_queries(aioclient_mock) == [
                {
                    "startDate": "2026-11-01T00:00:00",
                    "endDate": "2026-11-01T23:59:59.999000",
                    "interval": "1h",
                    "locationId": "mmnnoopp",
                    "macAddress": "1a2b3c4d5e6f",
                    "tz": "America/New_York",
                }
            ]

    aioclient_mock.mock_calls.clear()
    freezer.tick(timedelta(seconds=65))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert_consumption_queries(aioclient_mock, "America/New_York", "2026-11-01")
    assert hass.states.get(CONSUMPTION_ENTITY).state == "3.7"
