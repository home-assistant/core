"""The test for the Nord Pool coordinator."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

import aiohttp
from freezegun.api import FrozenDateTimeFactory
from pynordpool import (
    NordPoolAuthenticationError,
    NordPoolClient,
    NordPoolEmptyResponseError,
    NordPoolError,
    NordPoolResponseError,
)
import pytest

from homeassistant.components.homeassistant import (
    DOMAIN as HOMEASSISTANT_DOMAIN,
    SERVICE_UPDATE_ENTITY,
)
from homeassistant.components.nordpool.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import ENTRY_CONFIG

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.freeze_time("2025-10-01T10:00:00+00:00")
async def test_coordinator(
    hass: HomeAssistant,
    get_client: NordPoolClient,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the Nord Pool coordinator with errors."""
    await async_setup_component(hass, HOMEASSISTANT_DOMAIN, {})
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        data=ENTRY_CONFIG,
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    state = hass.states.get("sensor.nord_pool_se3_current_price")
    assert state.state == "0.67405"

    assert "Next data update at 2025-10-01 11:00:00+00:00" in caplog.text
    assert "Next listener update at 2025-10-01 10:15:00+00:00" in caplog.text

    with (
        patch(
            "homeassistant.components.nordpool.coordinator.NordPoolClient.async_get_delivery_period",
            wraps=get_client.async_get_delivery_period,
        ) as mock_data,
    ):
        freezer.tick(timedelta(minutes=17))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)
        assert mock_data.call_count == 0
        state = hass.states.get("sensor.nord_pool_se3_current_price")
        assert state.state == "0.63858"

    assert "Next data update at 2025-10-01 11:00:00+00:00" in caplog.text
    assert "Next listener update at 2025-10-01 10:30:00+00:00" in caplog.text

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
        assert state.state == "0.66068"

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
        assert state.state == "0.68544"
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
        assert state.state == "0.72953"
        assert "Empty response" in caplog.text

    with (
        patch(
            "homeassistant.components.nordpool.coordinator.NordPoolClient.async_get_delivery_period",
            side_effect=aiohttp.ClientError("error"),
        ) as mock_data,
    ):
        assert "Response error" not in caplog.text
        freezer.tick(timedelta(hours=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)
        assert mock_data.call_count == 1
        state = hass.states.get("sensor.nord_pool_se3_current_price")
        assert state.state == "0.90294"
        assert "error" in caplog.text

    with (
        patch(
            "homeassistant.components.nordpool.coordinator.NordPoolClient.async_get_delivery_period",
            side_effect=TimeoutError("error"),
        ) as mock_data,
    ):
        assert "Response error" not in caplog.text
        freezer.tick(timedelta(hours=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)
        assert mock_data.call_count == 1
        state = hass.states.get("sensor.nord_pool_se3_current_price")
        assert state.state == "1.16266"
        assert "error" in caplog.text

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
        assert state.state == "1.90004"
        assert "Response error" in caplog.text

    freezer.tick(timedelta(hours=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    state = hass.states.get("sensor.nord_pool_se3_current_price")
    assert state.state == "3.42983"

    # Test manual polling
    hass.config_entries.async_update_entry(
        entry=config_entry, pref_disable_polling=True
    )
    await hass.config_entries.async_reload(config_entry.entry_id)
    freezer.tick(timedelta(hours=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    state = hass.states.get("sensor.nord_pool_se3_current_price")
    assert state.state == "1.42403"

    # Prices should update without any polling made (read from cache)
    freezer.tick(timedelta(hours=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    state = hass.states.get("sensor.nord_pool_se3_current_price")
    assert state.state == "1.1358"

    # Test manually updating the data
    with (
        patch(
            "homeassistant.components.nordpool.coordinator.NordPoolClient.async_get_delivery_periods",
            wraps=get_client.async_get_delivery_periods,
        ) as mock_data,
    ):
        await hass.services.async_call(
            HOMEASSISTANT_DOMAIN,
            SERVICE_UPDATE_ENTITY,
            {ATTR_ENTITY_ID: "sensor.nord_pool_se3_current_price"},
            blocking=True,
        )
        assert mock_data.call_count == 1

    freezer.tick(timedelta(hours=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    state = hass.states.get("sensor.nord_pool_se3_current_price")
    assert state.state == "0.933"

    hass.config_entries.async_update_entry(
        entry=config_entry, pref_disable_polling=False
    )
    await hass.config_entries.async_reload(config_entry.entry_id)

    with (
        patch(
            "homeassistant.components.nordpool.coordinator.NordPoolClient.async_get_delivery_period",
            side_effect=NordPoolError("error"),
        ) as mock_data,
    ):
        freezer.tick(timedelta(hours=48))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)
        assert mock_data.call_count == 1
        state = hass.states.get("sensor.nord_pool_se3_current_price")
        assert state.state == STATE_UNAVAILABLE
        assert "Data for current day is missing" in caplog.text
