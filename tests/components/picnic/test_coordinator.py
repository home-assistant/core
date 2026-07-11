"""Tests for the Picnic coordinator."""

from datetime import timedelta
import json
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.picnic.const import DOMAIN
from homeassistant.components.picnic.coordinator import (
    DEFAULT_UPDATE_INTERVAL,
    DELIVERY_UPDATE_INTERVAL,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed, async_load_fixture


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


async def _setup_with_delivery(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_picnic_api: MagicMock,
    status: str,
    eta2: tuple[timedelta, timedelta] | None,
    slot_window: tuple[timedelta, timedelta] | None,
) -> dict:
    """Set up the integration with a delivery in the given state."""
    # eta2 is the route-planning ETA as served by the deliveries API;
    # the coordinator exposes it as the delivery's "eta"
    delivery = json.loads(await async_load_fixture(hass, "delivery.json", DOMAIN))
    delivery["status"] = status
    delivery["delivery_time"] = None
    delivery["eta2"] = (
        {
            "start": (dt_util.utcnow() + eta2[0]).isoformat(),
            "end": (dt_util.utcnow() + eta2[1]).isoformat(),
        }
        if eta2 is not None
        else None
    )
    if slot_window is not None:
        delivery["slot"]["window_start"] = (
            dt_util.utcnow() + slot_window[0]
        ).isoformat()
        delivery["slot"]["window_end"] = (dt_util.utcnow() + slot_window[1]).isoformat()
    mock_picnic_api.get_deliveries.return_value = [delivery]

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return delivery


@pytest.mark.parametrize(
    ("status", "eta2", "slot_window", "expected_interval"),
    [
        # No undelivered order
        ("COMPLETED", None, None, DEFAULT_UPDATE_INTERVAL),
        # Delivery days away
        (
            "CURRENT",
            (timedelta(days=2), timedelta(days=2, hours=1)),
            None,
            DEFAULT_UPDATE_INTERVAL,
        ),
        # Delivery under way
        (
            "CURRENT",
            (timedelta(minutes=10), timedelta(minutes=30)),
            None,
            DELIVERY_UPDATE_INTERVAL,
        ),
        # Just ahead of the window: next poll capped at the window start
        (
            "CURRENT",
            (timedelta(minutes=40), timedelta(minutes=60)),
            None,
            timedelta(minutes=10),
        ),
        # Long past the window while still current
        (
            "CURRENT",
            (timedelta(hours=-4), timedelta(hours=-3)),
            None,
            DEFAULT_UPDATE_INTERVAL,
        ),
        # No ETA yet: the slot window selects the faster interval
        (
            "CURRENT",
            None,
            (timedelta(minutes=10), timedelta(minutes=70)),
            DELIVERY_UPDATE_INTERVAL,
        ),
    ],
)
@pytest.mark.usefixtures("freezer")
async def test_update_interval(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_picnic_api: MagicMock,
    status: str,
    eta2: tuple[timedelta, timedelta] | None,
    slot_window: tuple[timedelta, timedelta] | None,
    expected_interval: timedelta,
) -> None:
    """Test the update interval for the various delivery states."""
    await _setup_with_delivery(
        hass, mock_config_entry, mock_picnic_api, status, eta2, slot_window
    )

    coordinator = mock_config_entry.runtime_data
    assert coordinator.update_interval == expected_interval


async def test_update_interval_relaxes_after_delivery(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_picnic_api: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that the update interval returns to the default once delivered."""
    delivery = await _setup_with_delivery(
        hass,
        mock_config_entry,
        mock_picnic_api,
        "CURRENT",
        (timedelta(minutes=10), timedelta(minutes=30)),
        None,
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
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that failed refreshes still relax the interval past the window."""
    await _setup_with_delivery(
        hass,
        mock_config_entry,
        mock_picnic_api,
        "CURRENT",
        (timedelta(minutes=10), timedelta(minutes=30)),
        None,
    )

    coordinator = mock_config_entry.runtime_data
    assert coordinator.update_interval == DELIVERY_UPDATE_INTERVAL

    mock_picnic_api.get_cart.return_value = None
    freezer.tick(timedelta(hours=3))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert coordinator.last_update_success is False
    assert coordinator.update_interval == DEFAULT_UPDATE_INTERVAL
