"""Tests for the Theben Conexa coordinator."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import aiohttp
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from theben_conexa_smgw import UnexpectedReturnCode

from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.test_setup import FrozenDateTimeFactory


async def test_setup_entry_initializes_correctly(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_conexa_smgw: SimpleNamespace,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup initializes runtime coordinator data and schedules updates."""
    # Freeze the clock so the coordinator and test advance from the same time base.
    now = datetime(2026, 8, 6, 12, 33, 5, tzinfo=UTC)
    freezer.move_to(now)

    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    scheduled_call_count = mock_conexa_smgw.client.getLatestValues.call_count

    freezer.tick(timedelta(minutes=12, seconds=35))

    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (
        mock_conexa_smgw.client.getLatestValues.call_count == scheduled_call_count + 1
    )

    # Unload to confirm the scheduled poll is cancelled and does not fire again.
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    freezer.tick(timedelta(minutes=15))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (
        mock_conexa_smgw.client.getLatestValues.call_count == scheduled_call_count + 1
    )


async def test_setup_entry_not_ready_when_gateway_unreachable(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_conexa_smgw: SimpleNamespace,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup retries when gateway is unreachable and no entities are created."""
    mock_config_entry.add_to_hass(hass)

    mock_conexa_smgw.network.side_effect = TimeoutError
    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert (
        er.async_entries_for_config_entry(entity_registry, mock_config_entry.entry_id)
        == []
    )


@pytest.mark.parametrize(
    "side_effect",
    [
        pytest.param(TimeoutError, id="timeout"),
        pytest.param(aiohttp.ServerDisconnectedError, id="server-disconnected"),
    ],
)
async def test_setup_entry_auth_failed_starts_reauth(
    hass: HomeAssistant,
    mock_conexa_smgw: SimpleNamespace,
    mock_config_entry: MockConfigEntry,
    side_effect: type[Exception],
) -> None:
    """Test a reachable gateway rejecting the credentials starts a reauth flow."""
    mock_config_entry.add_to_hass(hass)

    mock_conexa_smgw.create.side_effect = side_effect
    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == mock_config_entry.entry_id


async def test_setup_entry_not_ready_on_unexpected_reply(
    hass: HomeAssistant,
    mock_conexa_smgw: SimpleNamespace,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup retries without reauth when the gateway replies unexpectedly."""
    mock_config_entry.add_to_hass(hass)

    mock_conexa_smgw.create.side_effect = UnexpectedReturnCode("boom")
    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert hass.config_entries.flow.async_progress() == []


async def test_scheduled_update_unexpected_reply(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_conexa_smgw: SimpleNamespace,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test an unexpected reply during a scheduled poll marks the update failed."""
    freezer.move_to(datetime(2026, 8, 6, 12, 33, 5, tzinfo=UTC))
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.runtime_data.last_update_success

    mock_conexa_smgw.client.getLatestValues.side_effect = UnexpectedReturnCode("boom")
    freezer.tick(timedelta(minutes=12, seconds=35))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_conexa_smgw.client.getLatestValues.call_count == 2
    assert not mock_config_entry.runtime_data.last_update_success
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert hass.config_entries.flow.async_progress() == []
