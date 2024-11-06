"""The test for the Nord Pool coordinator."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from pynordpool.exceptions import NordpoolError
from pynordpool.model import DeliveryPeriodData
import pytest

from homeassistant.components.nordpool.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from . import ENTRY_CONFIG

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.freeze_time("2024-11-05T18:00:00+00:00")
async def test_coordinator(
    hass: HomeAssistant,
    get_data: DeliveryPeriodData,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the Nord Pool coordinator with errors."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        data=ENTRY_CONFIG,
    )

    config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.nordpool.coordinator.NordpoolClient.async_get_delivery_period",
        ) as mock_data,
    ):
        mock_data.return_value = get_data
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        mock_data.assert_called_once()
        state = hass.states.get("sensor.nord_pool_se3_current_price")
        assert state.state == "1.01177"
        mock_data.reset_mock()

        mock_data.side_effect = NordpoolError("error")
        freezer.tick(timedelta(hours=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)
        mock_data.assert_called_once()
        state = hass.states.get("sensor.nord_pool_se3_current_price")
        assert state.state == STATE_UNAVAILABLE
        mock_data.reset_mock()

        mock_data.return_value = DeliveryPeriodData(
            raw={},
            requested_date="2024-11-05",
            updated_at=dt_util.utcnow(),
            entries=[],
            block_prices=[],
            currency="SEK",
            exchange_rate=1,
            area_average={},
        )
        mock_data.side_effect = None
        freezer.tick(timedelta(hours=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        mock_data.assert_called_once()
        state = hass.states.get("sensor.nord_pool_se3_current_price")
        assert state.state == STATE_UNAVAILABLE
        mock_data.reset_mock()

        mock_data.return_value = get_data
        mock_data.side_effect = None
        freezer.tick(timedelta(hours=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        mock_data.assert_called_once()
        state = hass.states.get("sensor.nord_pool_se3_current_price")
        assert state.state == "0.5223"
