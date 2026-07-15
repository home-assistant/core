"""Tests for the Picnic coordinator."""

from datetime import timedelta
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.picnic.const import (
    DEFAULT_UPDATE_INTERVAL,
    DELIVERY_UPDATE_INTERVAL,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .conftest import SetupDeliveryFixture

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_timeout_failed_with_retry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_picnic_api: MagicMock,
) -> None:
    """Test that a TimeoutError is handled properly."""
    mock_picnic_api.get_cart.side_effect = TimeoutError

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize(
    ("status", "eta2", "slot_window", "expected_interval"),
    [
        pytest.param(
            "COMPLETED",
            None,
            (timedelta(hours=-2), timedelta(hours=-1)),
            DEFAULT_UPDATE_INTERVAL,
            id="no_undelivered_order",
        ),
        pytest.param(
            "CURRENT",
            (timedelta(days=2), timedelta(days=2, hours=1)),
            (timedelta(days=2), timedelta(days=2, hours=1)),
            DEFAULT_UPDATE_INTERVAL,
            id="delivery_days_away",
        ),
        pytest.param(
            "CURRENT",
            (timedelta(minutes=10), timedelta(minutes=30)),
            (timedelta(minutes=-15), timedelta(minutes=45)),
            DELIVERY_UPDATE_INTERVAL,
            id="delivery_under_way",
        ),
        pytest.param(
            "CURRENT",
            (timedelta(minutes=40), timedelta(minutes=60)),
            (timedelta(minutes=40), timedelta(minutes=60)),
            timedelta(minutes=10),
            id="next_poll_capped_at_window_start",
        ),
        pytest.param(
            "CURRENT",
            (timedelta(minutes=30, seconds=30), timedelta(minutes=50)),
            (timedelta(minutes=30, seconds=30), timedelta(minutes=50)),
            DELIVERY_UPDATE_INTERVAL,
            id="next_poll_never_sooner_than_delivery_interval",
        ),
        pytest.param(
            "CURRENT",
            (timedelta(hours=-4), timedelta(hours=-3)),
            (timedelta(hours=-4), timedelta(hours=-3)),
            DEFAULT_UPDATE_INTERVAL,
            id="long_past_window_still_current",
        ),
        pytest.param(
            "CURRENT",
            None,
            (timedelta(minutes=10), timedelta(minutes=70)),
            DELIVERY_UPDATE_INTERVAL,
            id="slot_window_fallback_without_eta",
        ),
    ],
)
@pytest.mark.usefixtures("freezer")
async def test_update_interval(
    mock_config_entry: MockConfigEntry,
    setup_delivery: SetupDeliveryFixture,
    status: str,
    eta2: tuple[timedelta, timedelta] | None,
    slot_window: tuple[timedelta, timedelta],
    expected_interval: timedelta,
) -> None:
    """Test the update interval for the various delivery states."""
    await setup_delivery(status, eta2, slot_window)

    coordinator = mock_config_entry.runtime_data
    assert coordinator.update_interval == expected_interval


@pytest.mark.usefixtures("freezer")
async def test_update_interval_with_malformed_eta(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_picnic_api: MagicMock,
) -> None:
    """Test that a malformed ETA falls back to the slot window."""
    delivery = mock_picnic_api.get_deliveries.return_value[0]
    delivery["status"] = "CURRENT"
    delivery["delivery_time"] = None
    delivery["eta2"] = {"start": "malformed", "end": "malformed"}
    delivery["slot"]["window_start"] = (
        dt_util.utcnow() + timedelta(minutes=10)
    ).isoformat()
    delivery["slot"]["window_end"] = (
        dt_util.utcnow() + timedelta(minutes=70)
    ).isoformat()

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data
    assert coordinator.update_interval == DELIVERY_UPDATE_INTERVAL


async def test_update_interval_relaxes_after_delivery(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    setup_delivery: SetupDeliveryFixture,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that the update interval returns to the default once delivered."""
    delivery = await setup_delivery(
        "CURRENT",
        (timedelta(minutes=10), timedelta(minutes=30)),
        (timedelta(minutes=-15), timedelta(minutes=45)),
    )

    coordinator = mock_config_entry.runtime_data
    assert coordinator.update_interval == DELIVERY_UPDATE_INTERVAL

    delivery["status"] = "COMPLETED"
    freezer.tick(DELIVERY_UPDATE_INTERVAL + timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert coordinator.update_interval == DEFAULT_UPDATE_INTERVAL


async def test_update_interval_relaxes_when_refresh_fails(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_picnic_api: MagicMock,
    setup_delivery: SetupDeliveryFixture,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that failed refreshes still relax the interval past the window."""
    await setup_delivery(
        "CURRENT",
        (timedelta(minutes=10), timedelta(minutes=30)),
        (timedelta(minutes=-15), timedelta(minutes=45)),
    )

    coordinator = mock_config_entry.runtime_data
    assert coordinator.update_interval == DELIVERY_UPDATE_INTERVAL

    mock_picnic_api.get_cart.return_value = None
    freezer.tick(timedelta(hours=3))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert coordinator.last_update_success is False
    assert coordinator.update_interval == DEFAULT_UPDATE_INTERVAL
