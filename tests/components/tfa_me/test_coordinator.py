"""Test the TFA.me integration: test of coordinator.py."""

# For test run: "pytest ./tests/components/tfa_me/ --cov=homeassistant.components.tfa_me --cov-report term-missing -vv"

from datetime import timedelta
from http import HTTPStatus
from unittest.mock import patch

import pytest
from tfa_me_ha_local.client import (
    TFAmeConnectionError,
    TFAmeException,
    TFAmeHTTPError,
    TFAmeJSONError,
    TFAmeTimeoutError,
)

from homeassistant.components.hassio import datetime
from homeassistant.components.tfa_me.const import CONF_NAME_WITH_STATION_ID, DOMAIN
from homeassistant.components.tfa_me.coordinator import TFAmeDataCoordinator
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import UpdateFailed

from tests.common import AsyncMock, MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.fixture
def tfa_me_mock_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return a mock config entry for tfa_me integration."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_IP_ADDRESS: "127.0.0.1",
            CONF_NAME_WITH_STATION_ID: False,
        },
        unique_id="test-1234",
    )
    entry.add_to_hass(hass)
    return entry


@pytest.mark.asyncio
async def test_update_data_with_ip(hass: HomeAssistant, tfa_me_mock_entry) -> None:
    """Test normal update (with IP) with some sensor types."""
    now = datetime.now().timestamp()

    # Create dummy JSON reply
    dummy_json = {
        "gateway_id": "017654321",
        "sensors": [
            {
                "sensor_id": "a21234567",
                "name": "A21234567",
                "timestamp": "2025-09-04T12:21:41Z",
                "ts": int(now),
                "measurements": {
                    "rssi": {"value": "221", "unit": "/255"},
                    "lowbatt": {"value": "0", "unit": "No"},
                    "wind_direction": {"value": "8", "unit": ""},
                    "wind_speed": {"value": "0.0", "unit": "m/s"},
                    "wind_gust": {"value": "0.0", "unit": "m/s"},
                },
            },
            {
                "sensor_id": "a12345678",
                "name": "A12345678",
                "timestamp": "2025-09-05T06:46:31Z",
                "ts": int(now),
                "measurements": {
                    "rssi": {"value": "216", "unit": "/255"},
                    "lowbatt": {"value": "0", "unit": "No"},
                    "rain": {"value": "29.2", "unit": "mm"},
                },
            },
        ],
    }

    coordinator = TFAmeDataCoordinator(
        hass,
        tfa_me_mock_entry,
        "127.0.0.1",
        timedelta(seconds=30),
        name_with_station_id=True,
    )
    coordinator.first_init = 1

    # Patch TFAmeClient delivers JSON directly
    with patch(
        "homeassistant.components.tfa_me.coordinator.TFAmeClient",
        autospec=True,
    ) as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.async_get_sensors.return_value = dummy_json
        mock_client_cls.return_value = mock_client

        # Request data
        result = await coordinator._async_update_data()

    # Asserts wind sensor
    assert "sensor.017654321_a21234567_wind_direction" in result
    assert "sensor.017654321_a21234567_wind_direction_txt" in result
    assert "sensor.017654321_a21234567_wind_direction_deg" in result
    assert "sensor.017654321_a21234567_wind_speed" in result
    assert "sensor.017654321_a21234567_wind_gust" in result
    assert "sensor.017654321_a21234567_rssi" in result
    assert "sensor.017654321_a21234567_lowbatt" in result
    assert "sensor.017654321_a21234567_lowbatt_txt" in result

    # Asserts rain sensor
    assert "sensor.017654321_a12345678_rain" in result
    assert "sensor.017654321_a12345678_rssi" in result
    assert "sensor.017654321_a12345678_lowbatt" in result
    assert "sensor.017654321_a12345678_lowbatt_txt" in result

    # Asserts others
    assert coordinator.gateway_id == "017654321"
    assert coordinator.first_init == 2


@pytest.mark.asyncio
async def test_update_data_with_mdns(
    hass: HomeAssistant,
    tfa_me_mock_entry,
) -> None:
    """Test normal update (with MDNS name) with some sensor types."""
    now = datetime.now().timestamp()

    # Create dummy JSON reply
    dummy_json = {
        "gateway_id": "017654321",
        "sensors": [
            {
                "sensor_id": "a21234567",
                "name": "A21234567",
                "timestamp": "2025-09-04T12:21:41Z",
                "ts": int(now),
                "measurements": {
                    "rssi": {"value": "221", "unit": "/255"},
                    "lowbatt": {"value": "0", "unit": "No"},
                    "wind_direction": {"value": "8", "unit": ""},
                    "wind_speed": {"value": "0.0", "unit": "m/s"},
                    "wind_gust": {"value": "0.0", "unit": "m/s"},
                },
            }
        ],
    }

    coordinator = TFAmeDataCoordinator(
        hass,
        tfa_me_mock_entry,
        "017-654-321",
        timedelta(seconds=30),
        name_with_station_id=False,
    )
    coordinator.first_init = 1

    with (
        patch(
            "homeassistant.components.tfa_me.TFAmeDataCoordinator.resolve_mdns",
            return_value="127.0.0.1",
        ),
        patch(
            "homeassistant.components.tfa_me.coordinator.TFAmeClient",
            autospec=True,
        ) as mock_client_cls,
    ):
        mock_client = AsyncMock()
        mock_client.async_get_sensors.return_value = dummy_json
        mock_client_cls.return_value = mock_client

        result = await coordinator._async_update_data()

    # Asserts
    assert "sensor.017654321_a21234567_wind_direction" in result
    assert "sensor.017654321_a21234567_wind_direction_txt" in result
    assert "sensor.017654321_a21234567_wind_direction_deg" in result
    assert "sensor.017654321_a21234567_wind_speed" in result
    assert "sensor.017654321_a21234567_wind_gust" in result
    assert "sensor.017654321_a21234567_rssi" in result
    assert "sensor.017654321_a21234567_lowbatt" in result
    assert "sensor.017654321_a21234567_lowbatt_txt" in result

    assert coordinator.gateway_id == "017654321"
    assert coordinator.first_init == 2


@pytest.mark.asyncio
async def test_update_data_with_mdns_update_failed(
    aioclient_mock: AiohttpClientMocker, hass: HomeAssistant, tfa_me_mock_entry
) -> None:
    """Test request fails (UpdateFailed)."""
    # Bad request
    aioclient_mock.get(
        "http://tfa-me-017-654-321.local/sensors",
        json={
            "Error": "Bad request",
        },
        status=HTTPStatus.BAD_REQUEST,
    )

    coordinator = TFAmeDataCoordinator(
        hass,
        tfa_me_mock_entry,
        "017-654-321",
        timedelta(seconds=30),
        name_with_station_id=True,
    )
    coordinator.first_init = 1
    with (
        pytest.raises(UpdateFailed),
        patch(
            "homeassistant.components.tfa_me.TFAmeDataCoordinator.resolve_mdns",
            return_value="127.0.0.1",
        ),
    ):
        await coordinator._async_update_data()


@pytest.mark.asyncio
async def test_update_data_with_mdns_config_entry_not_ready(
    aioclient_mock: AiohttpClientMocker, hass: HomeAssistant, tfa_me_mock_entry
) -> None:
    """Test request fails (ConfigEntryNotReady) coordinator.first_init = 1."""
    # Bad request
    aioclient_mock.get(
        "http://tfa-me-017-654-321.local/sensors",
        json={
            "Error": "Bad request",
        },
        status=HTTPStatus.BAD_REQUEST,
    )

    coordinator = TFAmeDataCoordinator(
        hass,
        tfa_me_mock_entry,
        "017-654-321",
        timedelta(seconds=30),
        name_with_station_id=True,
    )
    coordinator.first_init = 0
    with (
        pytest.raises(ConfigEntryNotReady),
        patch(
            "homeassistant.components.tfa_me.TFAmeDataCoordinator.resolve_mdns",
            return_value="127.0.0.1",
        ),
    ):
        await coordinator._async_update_data()


@pytest.mark.asyncio
async def test_update_data_with_mdns_http_errory(
    aioclient_mock: AiohttpClientMocker, hass: HomeAssistant, tfa_me_mock_entry
) -> None:
    """Test request fails (HTTPError) and coordinator.first_init = 0."""
    # Bad request
    aioclient_mock.get(
        "http://127.0.0.1/sensors",
        json={
            "Error": "Bad request",
        },
        status=HTTPStatus.BAD_REQUEST,
    )

    coordinator = TFAmeDataCoordinator(
        hass,
        tfa_me_mock_entry,
        "017-654-321",
        timedelta(seconds=30),
        name_with_station_id=True,
    )
    coordinator.first_init = 0
    with (
        pytest.raises(ConfigEntryNotReady),
        patch(
            "homeassistant.components.tfa_me.TFAmeDataCoordinator.resolve_mdns",
            return_value="127.0.0.1",
        ),
    ):
        await coordinator._async_update_data()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("exc", "expected"),
    [
        (TFAmeTimeoutError("timeout"), ConfigEntryNotReady),
        (TFAmeConnectionError("conn"), ConfigEntryNotReady),
        (TFAmeHTTPError("http"), UpdateFailed),
        (TFAmeJSONError("json"), UpdateFailed),
        (TFAmeException("other"), ConfigEntryNotReady),
        (RuntimeError("unexpected"), ConfigEntryNotReady),
    ],
)
async def test_async_update_data_exceptions_first_init(
    hass: HomeAssistant, tfa_me_mock_entry: ConfigEntry, exc, expected
) -> None:
    """Test that coordinator maps exceptions correctly on first init."""

    coordinator = TFAmeDataCoordinator(
        hass=hass,
        config_entry=tfa_me_mock_entry,
        host="127.0.0.1",
        interval=timedelta(seconds=30),
        name_with_station_id=False,
    )

    # Patch the client so that async_get_sensors raises our test exception
    with (
        patch(
            "homeassistant.components.tfa_me.coordinator.TFAmeClient.async_get_sensors",
            side_effect=exc,
        ),
        pytest.raises(expected),
    ):
        await coordinator._async_update_data()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("exc", "expected"),
    [
        (TFAmeTimeoutError("timeout"), UpdateFailed),
        (TFAmeConnectionError("conn"), UpdateFailed),
        (TFAmeHTTPError("http"), UpdateFailed),
        (TFAmeJSONError("json"), UpdateFailed),
        (TFAmeException("other"), UpdateFailed),
        (RuntimeError("unexpected"), UpdateFailed),
    ],
)
async def test_async_update_data_exceptions_after_first_init(
    hass: HomeAssistant, tfa_me_mock_entry: ConfigEntry, exc, expected
) -> None:
    """Test that coordinator maps exceptions correctly after first init."""

    coordinator = TFAmeDataCoordinator(
        hass=hass,
        config_entry=tfa_me_mock_entry,
        host="127.0.0.1",
        interval=timedelta(seconds=30),
        name_with_station_id=False,
    )
    coordinator.first_init = 1  # simulate already initialized

    with (
        patch(
            "homeassistant.components.tfa_me.coordinator.TFAmeClient.async_get_sensors",
            side_effect=exc,
        ),
        pytest.raises(expected),
    ):
        await coordinator._async_update_data()
