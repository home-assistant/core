"""Tests for the Picnic coordinator."""

from datetime import timedelta
import json
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory

from homeassistant.components.picnic.coordinator import (
    DEFAULT_UPDATE_INTERVAL,
    DELIVERY_UPDATE_INTERVAL,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry, async_load_fixture


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


async def test_update_interval_default_without_current_delivery(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_picnic_api: MagicMock,
) -> None:
    """Test that the update interval is the default without an undelivered order."""
    delivery = json.loads(await async_load_fixture(hass, "picnic/delivery.json"))
    mock_picnic_api.get_deliveries.return_value = [delivery]

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data
    assert coordinator.update_interval == DEFAULT_UPDATE_INTERVAL


async def test_update_interval_around_delivery(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_picnic_api: MagicMock,
) -> None:
    """Test that the update interval tightens around the delivery and relaxes after."""
    delivery = json.loads(await async_load_fixture(hass, "picnic/delivery.json"))
    delivery["status"] = "CURRENT"
    del delivery["delivery_time"]
    delivery["eta2"] = {
        "start": (dt_util.utcnow() - timedelta(minutes=5)).isoformat(),
        "end": (dt_util.utcnow() + timedelta(minutes=15)).isoformat(),
    }
    mock_picnic_api.get_deliveries.return_value = [delivery]

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data
    assert coordinator.update_interval == DELIVERY_UPDATE_INTERVAL

    delivery["status"] = "COMPLETED"
    await coordinator.async_refresh()

    assert coordinator.update_interval == DEFAULT_UPDATE_INTERVAL


async def test_update_interval_default_before_delivery_day(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_picnic_api: MagicMock,
) -> None:
    """Test that the update interval stays default while the delivery is far away."""
    delivery = json.loads(await async_load_fixture(hass, "picnic/delivery.json"))
    delivery["status"] = "CURRENT"
    del delivery["delivery_time"]
    delivery["eta2"] = {
        "start": (dt_util.utcnow() + timedelta(days=2)).isoformat(),
        "end": (dt_util.utcnow() + timedelta(days=2, hours=1)).isoformat(),
    }
    mock_picnic_api.get_deliveries.return_value = [delivery]

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data
    assert coordinator.update_interval == DEFAULT_UPDATE_INTERVAL


async def test_update_interval_capped_before_delivery_window(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_picnic_api: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that the next poll is not scheduled past the fast-polling window start."""
    delivery = json.loads(await async_load_fixture(hass, "picnic/delivery.json"))
    delivery["status"] = "CURRENT"
    del delivery["delivery_time"]
    delivery["eta2"] = {
        "start": (dt_util.utcnow() + timedelta(minutes=40)).isoformat(),
        "end": (dt_util.utcnow() + timedelta(minutes=60)).isoformat(),
    }
    mock_picnic_api.get_deliveries.return_value = [delivery]

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data
    assert coordinator.update_interval == timedelta(minutes=10)
