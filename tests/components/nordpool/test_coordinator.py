"""The test for the Nord Pool coordinator."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from pynordpool import (
    NordPoolAuthenticationError,
    NordPoolClient,
    NordPoolEmptyResponseError,
    NordPoolError,
    NordPoolResponseError,
)
import pytest

from homeassistant.components.nordpool.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from . import ENTRY_CONFIG

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.freeze_time("2024-11-05T10:00:00+00:00")
async def test_coordinator(
    hass: HomeAssistant,
    get_client: NordPoolClient,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the Nord Pool coordinator with errors."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        data=ENTRY_CONFIG,
    )

    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    state = hass.states.get("sensor.nord_pool_se3_current_price")
    assert state.state == "0.92737"

    with (
        patch(
            "homeassistant.components.nordpool.coordinator.NordPoolClient.async_get_delivery_period",
            side_effect=NordPoolError("error"),
        ) as mock_data,
    ):
        freezer.tick(timedelta(hours=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)
        assert mock_data.call_count == 1
        state = hass.states.get("sensor.nord_pool_se3_current_price")
        assert state.state == STATE_UNAVAILABLE

    with (
        patch(
            "homeassistant.components.nordpool.coordinator.NordPoolClient.async_get_delivery_period",
            side_effect=NordPoolAuthenticationError("Authentication error"),
        ) as mock_data,
    ):
        assert "Authentication error" not in caplog.text
        freezer.tick(timedelta(hours=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)
        assert mock_data.call_count == 1
        state = hass.states.get("sensor.nord_pool_se3_current_price")
        assert state.state == STATE_UNAVAILABLE
        assert "Authentication error" in caplog.text

    with (
        patch(
            "homeassistant.components.nordpool.coordinator.NordPoolClient.async_get_delivery_period",
            side_effect=NordPoolEmptyResponseError("Empty response"),
        ) as mock_data,
    ):
        assert "Empty response" not in caplog.text
        freezer.tick(timedelta(hours=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)
        # Empty responses does not raise
        assert mock_data.call_count == 3
        state = hass.states.get("sensor.nord_pool_se3_current_price")
        assert state.state == STATE_UNAVAILABLE
        assert "Empty response" in caplog.text

    with (
        patch(
            "homeassistant.components.nordpool.coordinator.NordPoolClient.async_get_delivery_period",
            side_effect=NordPoolResponseError("Response error"),
        ) as mock_data,
    ):
        assert "Response error" not in caplog.text
        freezer.tick(timedelta(hours=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)
        assert mock_data.call_count == 1
        state = hass.states.get("sensor.nord_pool_se3_current_price")
        assert state.state == STATE_UNAVAILABLE
        assert "Response error" in caplog.text

    freezer.tick(timedelta(hours=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    state = hass.states.get("sensor.nord_pool_se3_current_price")
    assert state.state == "1.81645"
