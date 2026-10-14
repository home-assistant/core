"""The test for the Nord Pool coordinator."""

from datetime import timedelta
from http import HTTPStatus
from typing import Any
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from pynordpool import (
    API,
    NordPoolAuthenticationError,
    NordPoolClient,
    NordPoolConnectionError,
    NordPoolEmptyResponseError,
    NordPoolError,
    NordPoolResponseError,
)
import pytest

from homeassistant.components.nordpool.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant

from . import ENTRY_CONFIG

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.mark.freeze_time("2025-10-01T10:00:00+02:00")
async def test_coordinator_happy_path(
    hass: HomeAssistant,
    get_client: NordPoolClient,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
    load_int: MockConfigEntry,
) -> None:
    """Test the Nord Pool coordinator's happy path."""

    state = hass.states.get("sensor.nord_pool_se3_current_price")
    assert state.state == "1.03744"

    caplog.clear()
    with (
        patch(
            "homeassistant.components.nordpool.coordinator.NordPoolClient.async_get_delivery_period",
            wraps=get_client.async_get_delivery_period,
        ) as mock_data,
    ):
        freezer.tick(timedelta(minutes=15))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)
        assert mock_data.call_count == 0
        state = hass.states.get("sensor.nord_pool_se3_current_price")
        assert state.state == "0.95013"

        freezer.tick(timedelta(minutes=2))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)
        assert mock_data.call_count == 0
        state = hass.states.get("sensor.nord_pool_se3_current_price")
        assert state.state == "0.95013"

        freezer.tick(timedelta(minutes=13))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)
        assert mock_data.call_count == 0
        state = hass.states.get("sensor.nord_pool_se3_current_price")
        assert state.state == "0.82613"
        state = hass.states.get("binary_sensor.nord_pool_se3_tomorrow_price_available")
        assert state.state == "on"

        freezer.tick(timedelta(days=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)
        assert mock_data.call_count == 1
        state = hass.states.get("sensor.nord_pool_se3_current_price")
        assert state.state == "0.86614"
        state = hass.states.get("binary_sensor.nord_pool_se3_tomorrow_price_available")
        assert state.state == "off"


@pytest.mark.freeze_time("2025-10-01T10:00:00+02:00")
@pytest.mark.parametrize(
    "exc",
    [
        NordPoolAuthenticationError("Could not authenticate"),
        NordPoolConnectionError("Could not connect"),
        NordPoolEmptyResponseError("Empty response fetching today's data"),
        NordPoolResponseError("Response error fetching today's data"),
        NordPoolError("Error fetching today's data"),
    ],
)
async def test_coordinator_setup_errors_today(
    hass: HomeAssistant,
    get_client: NordPoolClient,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
    aioclient_mock: AiohttpClientMocker,
    load_json: list[dict[str, Any]],
    exc: Exception,
) -> None:
    """Test the Nord Pool coordinator setup with errors.

    Can not fetch today's data
    """

    responses = list(load_json)
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
    request = aioclient_mock.request(
        "GET",
        url=API + "/DayAheadPrices",
        params={
            "date": "2025-10-01",
            "market": "DayAhead",
            "deliveryArea": "SE3,SE4",
            "currency": "SEK",
        },
        json=responses[0],
        exc=exc,
    )
    aioclient_mock.request(
        "GET",
        url=API + "/DayAheadPrices",
        params={
            "date": "2025-10-02",
            "market": "DayAhead",
            "deliveryArea": "SE3,SE4",
            "currency": "SEK",
        },
        json=responses[2],
    )

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        data=ENTRY_CONFIG,
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert config_entry.state is ConfigEntryState.SETUP_RETRY

    assert str(exc) in caplog.text

    request.exc = None

    freezer.tick(timedelta(minutes=15))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert config_entry.state is ConfigEntryState.LOADED
    state = hass.states.get("sensor.nord_pool_se3_current_price")
    assert state.state == "0.95013"


@pytest.mark.freeze_time("2025-10-01T10:00:00+02:00")
@pytest.mark.parametrize(
    "exc",
    [
        NordPoolAuthenticationError("Could not authenticate"),
        NordPoolConnectionError("Could not connect"),
        NordPoolEmptyResponseError("Empty response fetching tomorrow's data"),
        NordPoolResponseError("Response error fetching tomorrow's data"),
        NordPoolError("Error fetching tomorrow's data"),
    ],
)
async def test_coordinator_setup_errors_tomorrow(
    hass: HomeAssistant,
    get_client: NordPoolClient,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
    aioclient_mock: AiohttpClientMocker,
    load_json: list[dict[str, Any]],
    exc: Exception,
) -> None:
    """Test the Nord Pool coordinator setup.

    Can not fetch tomorrow's data, continues.
    """

    responses = list(load_json)
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
    request = aioclient_mock.request(
        "GET",
        url=API + "/DayAheadPrices",
        params={
            "date": "2025-10-02",
            "market": "DayAhead",
            "deliveryArea": "SE3,SE4",
            "currency": "SEK",
        },
        json=responses[2],
        exc=exc,
    )

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        data=ENTRY_CONFIG,
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert config_entry.state is ConfigEntryState.LOADED

    state = hass.states.get("sensor.nord_pool_se3_current_price")
    assert state.state == "1.03744"
    state = hass.states.get("binary_sensor.nord_pool_se3_tomorrow_price_available")
    assert state.state == "off"

    assert str(exc) in caplog.text

    request.exc = None

    freezer.tick(timedelta(minutes=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert config_entry.state is ConfigEntryState.LOADED
    state = hass.states.get("sensor.nord_pool_se3_current_price")
    assert state.state == "0.8616"
    state = hass.states.get("binary_sensor.nord_pool_se3_tomorrow_price_available")
    assert state.state == "on"


@pytest.mark.freeze_time("2025-10-01T00:05:00+02:00")
async def test_coordinator_update_data(
    hass: HomeAssistant,
    get_client: NordPoolClient,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
    aioclient_mock: AiohttpClientMocker,
    load_json: list[dict[str, Any]],
) -> None:
    """Test the Nord Pool coordinator with errors."""
    responses = list(load_json)
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
    request_today = aioclient_mock.request(
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
    request_tomorrow = aioclient_mock.request(
        "GET",
        url=API + "/DayAheadPrices",
        params={
            "date": "2025-10-02",
            "market": "DayAhead",
            "deliveryArea": "SE3,SE4",
            "currency": "SEK",
        },
        status=HTTPStatus.NO_CONTENT,
        json=responses[2],
    )
    aioclient_mock.request(
        "GET",
        url=API + "/DayAheadPrices",
        params={
            "date": "2025-10-03",
            "market": "DayAhead",
            "deliveryArea": "SE3,SE4",
            "currency": "SEK",
        },
        status=HTTPStatus.NO_CONTENT,
    )

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        data=ENTRY_CONFIG,
    )

    with (
        patch(
            "homeassistant.components.nordpool.coordinator.NordPoolClient.async_get_delivery_period",
            wraps=get_client.async_get_delivery_period,
        ) as mock_data,
    ):
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

        # 3 calls from setup, 1 from refresh as tomorrow was not available
        assert mock_data.call_count == 4
        mock_data.reset_mock()
        assert "Next listener update at 2025-10-01 00:15:00+02:00" in caplog.text

        state = hass.states.get("sensor.nord_pool_se3_previous_price")
        assert state.state == "0.69717"
        state = hass.states.get("sensor.nord_pool_se3_current_price")
        assert state.state == "0.55668"
        state = hass.states.get("sensor.nord_pool_se3_next_price")
        assert state.state == "0.51988"

        freezer.tick(timedelta(minutes=15))  # "2025-10-01T00:20:00+02:00"
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)
        # No callers, only listener update
        assert mock_data.call_count == 0
        assert "Next listener update at 2025-10-01 00:30:00+02:00" in caplog.text

        state = hass.states.get("sensor.nord_pool_se3_previous_price")
        assert state.state == "0.55668"
        state = hass.states.get("sensor.nord_pool_se3_current_price")
        assert state.state == "0.51988"
        state = hass.states.get("sensor.nord_pool_se3_next_price")
        assert state.state == "0.50828"

        freezer.tick(timedelta(minutes=45))  # "2025-10-01T01:05:00+02:00"
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)
        # Calls for tomorrow as data was not available
        assert mock_data.call_count == 1
        assert "Next listener update at 2025-10-01 01:15:00+02:00" in caplog.text

        state = hass.states.get("sensor.nord_pool_se3_previous_price")
        assert state.state == "0.50993"
        state = hass.states.get("sensor.nord_pool_se3_current_price")
        assert state.state == "0.50164"
        state = hass.states.get("sensor.nord_pool_se3_next_price")
        assert state.state == "0.50905"

        request_today.json = None
        request_today.exc = NordPoolError("Error fetching today's data")

        freezer.tick(timedelta(hours=1))  # "2025-10-01T02:05:00+02:00"
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)
        # Calls for tomorrow as data was not available
        assert mock_data.call_count == 2
        assert "Next listener update at 2025-10-01 02:15:00+02:00" in caplog.text

        state = hass.states.get("sensor.nord_pool_se3_previous_price")
        assert state.state == "0.44207"
        state = hass.states.get("sensor.nord_pool_se3_current_price")
        assert state.state == "0.50408"
        state = hass.states.get("sensor.nord_pool_se3_next_price")
        assert state.state == "0.50485"

        request_today.exc = None
        request_tomorrow.status = None
        request_tomorrow.exc = NordPoolError("Error fetching tomorrow's data")

        freezer.tick(timedelta(hours=1))  # "2025-10-01T03:05:00+02:00"
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)
        # Calls for tomorrow as data was not available
        # Exception only for today which is not called
        assert mock_data.call_count == 3
        assert "Next listener update at 2025-10-01 03:15:00+02:00" in caplog.text

        state = hass.states.get("sensor.nord_pool_se3_previous_price")
        assert state.state == "0.50629"
        state = hass.states.get("sensor.nord_pool_se3_current_price")
        assert state.state == "0.44207"
        state = hass.states.get("sensor.nord_pool_se3_next_price")
        assert state.state == "0.44196"

        freezer.move_to("2025-10-01T23:55:00+02:00")  # "2025-10-01T23:55:00+02:00"
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)
        # Calls for tomorrow as data was not available
        assert mock_data.call_count == 4
        assert "Next listener update at 2025-10-02 00:00:00+02:00" in caplog.text

        state = hass.states.get("sensor.nord_pool_se3_previous_price")
        assert state.state == "0.82005"
        state = hass.states.get("sensor.nord_pool_se3_current_price")
        assert state.state == "0.78568"
        state = hass.states.get("sensor.nord_pool_se3_next_price")
        assert state.state == STATE_UNKNOWN

        request_tomorrow.status = HTTPStatus.NO_CONTENT
        request_tomorrow.exc = None

        freezer.tick(timedelta(hours=1))  # "2025-10-02T00:55:00+02:00"
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)
        # Calls for tomorrow as data was not available
        assert mock_data.call_count == 5
        assert "Next listener update at 2025-10-02 01:00:00+02:00" in caplog.text

        state = hass.states.get("sensor.nord_pool_se3_previous_price")
        assert state.state == STATE_UNAVAILABLE
        state = hass.states.get("sensor.nord_pool_se3_current_price")
        assert state.state == STATE_UNAVAILABLE
        state = hass.states.get("sensor.nord_pool_se3_next_price")
        assert state.state == STATE_UNAVAILABLE

        request_tomorrow.status = HTTPStatus.OK
        request_tomorrow.exc = None

        freezer.tick(timedelta(hours=1))  # "2025-10-02T01:55:00+02:00"
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)
        # Calls for today and tomorrow as data was not available
        assert mock_data.call_count == 7
        assert "Next listener update at 2025-10-02 02:00:00+02:00" in caplog.text

        state = hass.states.get("sensor.nord_pool_se3_previous_price")
        assert state.state == "0.79663"
        state = hass.states.get("sensor.nord_pool_se3_current_price")
        assert state.state == "0.7067"
        state = hass.states.get("sensor.nord_pool_se3_next_price")
        assert state.state == "0.69523"

        freezer.move_to("2025-10-02T23:55:00+02:00")  # "2025-10-02T23:55:00+02:00"
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)
        # Calls for tomorrow as data was not available
        assert mock_data.call_count == 8
        assert "Next listener update at 2025-10-03 00:00:00+02:00" in caplog.text

        state = hass.states.get("sensor.nord_pool_se3_previous_price")
        assert state.state == "0.87364"
        state = hass.states.get("sensor.nord_pool_se3_current_price")
        assert state.state == "0.6469"
        state = hass.states.get("sensor.nord_pool_se3_next_price")
        assert state.state == STATE_UNKNOWN
