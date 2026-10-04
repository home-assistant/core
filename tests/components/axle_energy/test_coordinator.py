"""Test coordinator-owned event notifications."""

import asyncio
from dataclasses import replace
from datetime import timedelta
from unittest.mock import AsyncMock, Mock, patch

from aioaxlevpp import AxleStatus, GridEvent
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.freeze_time("2026-09-11T16:59:00Z")
async def test_event_notifications(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
    mock_event: GridEvent,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Notify listeners without a binary sensor or a change to API polling."""
    mock_client.get_status.return_value = AxleStatus(
        replace(mock_event, end=mock_event.start + timedelta(minutes=1)),
        opted_out=False,
    )
    mock_config_entry.add_to_hass(hass)
    with patch("homeassistant.components.axle_energy.PLATFORMS", [Platform.SENSOR]):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
    listener = Mock()
    mock_config_entry.runtime_data.async_add_listener(listener)
    mock_client.get_status.reset_mock()

    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    listener.assert_called_once_with()
    mock_client.get_status.assert_not_called()
    listener.reset_mock()

    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    listener.assert_called_once_with()
    mock_client.get_status.assert_not_called()

    freezer.tick(timedelta(minutes=8))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    mock_client.get_status.assert_awaited_once_with()


@pytest.mark.freeze_time("2026-09-11T16:59:00Z")
async def test_shutdown_during_refresh(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
    mock_event: GridEvent,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A fetch completing after shutdown must not restart boundary notifications."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    coordinator = mock_config_entry.runtime_data
    listener = Mock()
    coordinator.async_add_listener(listener)
    started = asyncio.Event()
    response = asyncio.Future[AxleStatus]()

    async def get_status() -> AxleStatus:
        started.set()
        return await response

    mock_client.get_status.side_effect = get_status
    refresh = hass.async_create_task(coordinator.async_refresh())
    await started.wait()
    await coordinator.async_shutdown()
    response.set_result(AxleStatus(mock_event, opted_out=False))
    await refresh

    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    listener.assert_not_called()
