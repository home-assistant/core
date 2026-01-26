"""Test the TFA.me integration: test of coordinator.py."""

# For test run: "pytest ./tests/components/tfa_me/ --cov=homeassistant.components.tfa_me --cov-report term-missing -vv"

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
from homeassistant.components.tfa_me.coordinator import TFAmeDataCoordinator
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import UpdateFailed

from tests.common import AsyncMock


@pytest.mark.asyncio
async def test_update_data_with_ip(
    hass: HomeAssistant, tfa_me_options_flow_mock_entry
) -> None:
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
        tfa_me_options_flow_mock_entry,
        "017-654-321",
        name_with_station_id=True,
    )
    coordinator.first_init = 1

    # Patch TFAmeClient delivers JSON directly
    with patch(
        "homeassistant.components.tfa_me.coordinator.TFAmeClient.async_get_sensors",
        new=AsyncMock(return_value=dummy_json),
    ):
        # Request data
        result = await coordinator._async_update_data()

    # Simply check if the number of entities is correct
    assert len(result) == 12

    # Asserts others
    assert coordinator.gateway_id == "017654321"
    assert coordinator.first_init == 2

    # Create invalid JSON: "measurements" is a string not a dict
    bad_json = {
        "gateway_id": "017654321",
        "sensors": [
            {
                "sensor_id": "a21234567",
                "name": "A21234567",
                "timestamp": "2025-09-04T12:21:41Z",
                "ts": 1234567890,
                "measurements": "THIS SHOULD BE A DICT, NOT A STRING",
            }
        ],
    }

    # Assert: TFAmeJSONError
    with pytest.raises(TFAmeJSONError, match="Invalid JSON response"):
        coordinator.json_to_entities(bad_json)


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
        name_with_station_id=False,
    )

    # Patch the client so that async_get_sensors raises the test exception
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
