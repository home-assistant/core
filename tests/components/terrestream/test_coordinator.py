"""Test scheduled polling and snapshot publication."""

import asyncio
from copy import deepcopy
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from terrestream_local.models import Snapshot

from homeassistant.core import HomeAssistant

LIGHT = "sensor.terrestream_illuminance"


async def test_polling_interval(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Read every 30 seconds without issuing clock commands between polls."""
    freezer.move_to("2026-01-01T00:00:00.500000+00:00")
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    mock_client.refresh.assert_awaited_once()
    assert hass.states.get(LIGHT).state == "100"

    freezer.tick(29)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    mock_client.refresh.assert_awaited_once()
    assert hass.states.get(LIGHT).state == "100"

    updated: Snapshot = deepcopy(mock_client.refresh.return_value)
    updated["measurements"]["illuminance"]["value"] = 200
    mock_client.refresh.return_value = updated
    freezer.tick(1)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert mock_client.refresh.await_count == 2
    assert hass.states.get(LIGHT).state == "200"
    mock_client.command.assert_not_awaited()
    assert await hass.config_entries.async_unload(config_entry.entry_id)


async def test_delayed_refresh_publishes_one_snapshot(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Keep the last observation until the next poll has completed."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    updated: Snapshot = deepcopy(mock_client.refresh.return_value)
    updated["measurements"]["illuminance"]["value"] = 200
    refresh_started = asyncio.Event()
    finish_refresh = asyncio.Event()

    async def blocked_refresh() -> Snapshot:
        mock_client.measurement_available.side_effect = None
        mock_client.measurement_available.return_value = False
        refresh_started.set()
        await finish_refresh.wait()
        mock_client.measurement_available.return_value = True
        return updated

    mock_client.refresh.side_effect = blocked_refresh
    freezer.tick(31)
    async_fire_time_changed(hass)
    await refresh_started.wait()
    try:
        await hass.async_block_till_done()
        assert hass.states.get(LIGHT).state == "100"
        entity = hass.data["entity_components"]["sensor"].get_entity(LIGHT)
        entity.async_write_ha_state()
        assert hass.states.get(LIGHT).state == "100"
    finally:
        finish_refresh.set()
        await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(LIGHT).state == "200"
    mock_client.command.assert_not_awaited()
    assert await hass.config_entries.async_unload(config_entry.entry_id)
