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

from homeassistant.components.tfa_me.coordinator import TFAmeUpdateCoordinator
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.util.dt import naive_now

from tests.common import AsyncMock


def _fake_sensor_payload() -> dict:
    """Return fake TFA.me sensor payload."""
    now = int(naive_now().timestamp())

    return {
        "gateway_id": "017654321",
        "sensors": [
            {
                "sensor_id": "a21234567",
                "name": "A21234567",
                "timestamp": "2025-09-04T12:21:41Z",
                "ts": now,
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
                "ts": now,
                "measurements": {
                    "rssi": {"value": "216", "unit": "/255"},
                    "lowbatt": {"value": "0", "unit": "No"},
                    "rain": {"value": "29.2", "unit": "mm"},
                },
            },
        ],
    }


async def test_update_data_with_ip(
    hass: HomeAssistant,
    tfa_me_options_flow_mock_entry: ConfigEntry,
) -> None:
    """Test normal coordinator update with IP."""
    coordinator = TFAmeUpdateCoordinator(hass, tfa_me_options_flow_mock_entry)

    with patch(
        "homeassistant.components.tfa_me.coordinator.TFAmeClient.async_get_sensors",
        new=AsyncMock(return_value=_fake_sensor_payload()),
    ):
        result = await coordinator._async_update_data()

    assert result.gateway_id == "017654321"
    assert len(result.entities) == 12

    assert "sensor.017654321_a21234567_rssi" in result.entities
    assert "sensor.017654321_a21234567_wind_speed" in result.entities
    assert "sensor.017654321_a12345678_rain" in result.entities


@pytest.mark.parametrize(
    "exc",
    [
        TFAmeTimeoutError("timeout"),
        TFAmeConnectionError("connection error"),
        TFAmeHTTPError("http error"),
        TFAmeJSONError("json error"),
        TFAmeException("generic error"),
    ],
)
async def test_async_update_data_exceptions(
    hass: HomeAssistant,
    tfa_me_options_flow_mock_entry: ConfigEntry,
    exc: TFAmeException,
) -> None:
    """Test that coordinator maps client exceptions to UpdateFailed."""
    coordinator = TFAmeUpdateCoordinator(
        hass=hass,
        config_entry=tfa_me_options_flow_mock_entry,
    )

    with (
        patch(
            "homeassistant.components.tfa_me.coordinator.TFAmeClient.async_get_sensors",
            side_effect=exc,
        ),
        pytest.raises(UpdateFailed),
    ):
        await coordinator._async_update_data()
