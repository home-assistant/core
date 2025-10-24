"""The test for the Nord Pool sensor platform."""

from __future__ import annotations

from datetime import timedelta
from http import HTTPStatus
from typing import Any

from freezegun.api import FrozenDateTimeFactory
from pynordpool import API
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import async_fire_time_changed, snapshot_platform
from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.mark.freeze_time("2025-10-01T18:00:00+00:00")
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor(
    hass: HomeAssistant,
    load_int: ConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the Nord Pool sensor."""

    await snapshot_platform(hass, entity_registry, snapshot, load_int.entry_id)


@pytest.mark.freeze_time("2025-10-01T18:00:00+00:00")
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_current_price_is_0(
    hass: HomeAssistant, load_int: ConfigEntry
) -> None:
    """Test the Nord Pool sensor working if price is 0."""

    current_price = hass.states.get("sensor.nord_pool_se4_current_price")

    assert current_price is not None
    assert current_price.state == "0.0"  # SE4 2025-10-01T18:00:00Z


@pytest.mark.freeze_time("2025-10-01T21:45:00+00:00")
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_no_next_price(hass: HomeAssistant, load_int: ConfigEntry) -> None:
    """Test the Nord Pool sensor."""

    current_price = hass.states.get("sensor.nord_pool_se3_current_price")
    last_price = hass.states.get("sensor.nord_pool_se3_previous_price")
    next_price = hass.states.get("sensor.nord_pool_se3_next_price")

    assert current_price is not None
    assert last_price is not None
    assert next_price is not None
    assert current_price.state == "0.78568"  # SE3 2025-10-01T21:45:00Z
    assert last_price.state == "0.82171"  # SE3 2025-10-01T21:30:00Z
    assert next_price.state == "0.81174"  # SE3 2025-10-01T22:00:00Z


@pytest.mark.freeze_time("2025-10-02T00:00:00+02:00")
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_no_previous_price(
    hass: HomeAssistant, load_int: ConfigEntry
) -> None:
    """Test the Nord Pool sensor."""

    current_price = hass.states.get("sensor.nord_pool_se3_current_price")
    last_price = hass.states.get("sensor.nord_pool_se3_previous_price")
    next_price = hass.states.get("sensor.nord_pool_se3_next_price")

    assert current_price is not None
    assert last_price is not None
    assert next_price is not None
    assert current_price.state == "0.93322"  # SE3 2025-10-01T22:00:00Z
    assert last_price.state == "0.8605"  # SE3 2025-10-01T21:45:00Z
    assert next_price.state == "0.83513"  # SE3 2025-10-01T22:15:00Z


@pytest.mark.freeze_time("2025-10-01T11:00:01+01:00")
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_empty_response(
    hass: HomeAssistant,
    load_int: ConfigEntry,
    load_json: list[dict[str, Any]],
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the Nord Pool sensor with empty response."""

    responses = list(load_json)

    current_price = hass.states.get("sensor.nord_pool_se3_current_price")
    last_price = hass.states.get("sensor.nord_pool_se3_previous_price")
    next_price = hass.states.get("sensor.nord_pool_se3_next_price")
    assert current_price is not None
    assert last_price is not None
    assert next_price is not None
    assert current_price.state == "0.67405"
    assert last_price.state == "0.8616"
    assert next_price.state == "0.63736"

    aioclient_mock.clear_requests()
    aioclient_mock.request(
        "GET",
        url=API + "/DayAheadPrices",
        params={
            "date": "2025-09-30",
            "market": "DayAhead",
            "deliveryArea": "SE3,SE4",
            "currency": "SEK",
        },
        json=responses[1],
    )
    aioclient_mock.request(
        "GET",
        url=API + "/DayAheadPrices",
        params={
            "date": "2025-10-01",
            "market": "DayAhead",
            "deliveryArea": "SE3,SE4",
            "currency": "SEK",
        },
        json=responses[0],
    )
    # Future date without data should return 204
    aioclient_mock.request(
        "GET",
        url=API + "/DayAheadPrices",
        params={
            "date": "2025-10-02",
            "market": "DayAhead",
            "deliveryArea": "SE3,SE4",
            "currency": "SEK",
        },
        status=HTTPStatus.NO_CONTENT,
    )

    freezer.tick(timedelta(hours=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    # All prices should be known as tomorrow is not loaded by sensors

    current_price = hass.states.get("sensor.nord_pool_se3_current_price")
    last_price = hass.states.get("sensor.nord_pool_se3_previous_price")
    next_price = hass.states.get("sensor.nord_pool_se3_next_price")
    assert current_price is not None
    assert last_price is not None
    assert next_price is not None
    assert current_price.state == "0.63736"
    assert last_price.state == "0.67405"
    assert next_price.state == "0.62233"

    aioclient_mock.clear_requests()
    aioclient_mock.request(
        "GET",
        url=API + "/DayAheadPrices",
        params={
            "date": "2025-09-30",
            "market": "DayAhead",
            "deliveryArea": "SE3,SE4",
            "currency": "SEK",
        },
        json=responses[1],
    )
    aioclient_mock.request(
        "GET",
        url=API + "/DayAheadPrices",
        params={
            "date": "2025-10-01",
            "market": "DayAhead",
            "deliveryArea": "SE3,SE4",
            "currency": "SEK",
        },
        json=responses[0],
    )
    # Future date without data should return 204
    aioclient_mock.request(
        "GET",
        url=API + "/DayAheadPrices",
        params={
            "date": "2025-10-02",
            "market": "DayAhead",
            "deliveryArea": "SE3,SE4",
            "currency": "SEK",
        },
        status=HTTPStatus.NO_CONTENT,
    )

    freezer.move_to("2025-10-01T21:45:01+00:00")
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    # Current and last price should be known, next price should be unknown
    # as api responds with empty data (204)

    current_price = hass.states.get("sensor.nord_pool_se3_current_price")
    last_price = hass.states.get("sensor.nord_pool_se3_previous_price")
    next_price = hass.states.get("sensor.nord_pool_se3_next_price")
    assert current_price is not None
    assert last_price is not None
    assert next_price is not None
    assert current_price.state == "0.78568"
    assert last_price.state == "0.82171"
    assert next_price.state == STATE_UNKNOWN
