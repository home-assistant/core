"""Test the TFA.me integration: test of coordinator.py."""

# For test run: "pytest ./tests/components/tfa_me/ --cov=homeassistant.components.tfa_me --cov-report term-missing -vv"

from unittest.mock import patch

import pytest
from tfa_me_ha_local.client import (
    TFAmeClient,
    TFAmeConnectionError,
    TFAmeException,
    TFAmeHTTPError,
    TFAmeJSONError,
    TFAmeTimeoutError,
)

from homeassistant.components.hassio import datetime
from homeassistant.components.tfa_me.coordinator import TFAmeUpdateCoordinator
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
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

    coordinator = TFAmeUpdateCoordinator(
        hass,
        tfa_me_options_flow_mock_entry,
    )

    # Patch TFAmeClient delivers JSON directly
    with patch(
        "homeassistant.components.tfa_me.coordinator.TFAmeClient.async_get_sensors",
        new=AsyncMock(return_value=dummy_json),
    ):
        # Request data
        result = await coordinator._async_update_data()

    # Simply check if the number of entities is correct
    assert len(result.entities) == 12

    # Asserts others
    assert result.gateway_id == "017654321"

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
    tfa_me_client = TFAmeClient("192.168.1.60", "sensors", timeout=7, log_level=1)
    with pytest.raises(TFAmeJSONError, match="Invalid JSON response"):
        tfa_me_client.parse_and_filter_json(json_data=bad_json, valid_keys=[])


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("exc", "expected"),
    [
        (TFAmeTimeoutError("timeout"), UpdateFailed),
        (TFAmeConnectionError("conn"), UpdateFailed),
        (TFAmeHTTPError("http"), UpdateFailed),
        (TFAmeJSONError("json"), UpdateFailed),
        (TFAmeException("other"), UpdateFailed),
    ],
)
async def test_async_update_data_exceptions_first_init(
    hass: HomeAssistant, tfa_me_mock_entry: ConfigEntry, exc, expected
) -> None:
    """Test that coordinator maps exceptions correctly on first init."""

    coordinator = TFAmeUpdateCoordinator(
        hass=hass,
        config_entry=tfa_me_mock_entry,
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
    ],
)
async def test_async_update_data_exceptions_after_first_init(
    hass: HomeAssistant, tfa_me_mock_entry: ConfigEntry, exc, expected
) -> None:
    """Test that coordinator maps exceptions correctly after first init."""

    coordinator = TFAmeUpdateCoordinator(
        hass=hass,
        config_entry=tfa_me_mock_entry,
    )

    with (
        patch(
            "homeassistant.components.tfa_me.coordinator.TFAmeClient.async_get_sensors",
            side_effect=exc,
        ),
        pytest.raises(expected),
    ):
        await coordinator._async_update_data()
