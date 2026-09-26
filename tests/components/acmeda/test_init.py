"""Tests for the Acmeda integration."""

import asyncio
from collections.abc import Generator
import threading
from unittest.mock import AsyncMock, MagicMock, patch

import aiopulse
import pytest

from homeassistant.components.acmeda.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry


@pytest.fixture
def mock_roller() -> MagicMock:
    """Return a mocked Acmeda roller."""
    roller = MagicMock()
    roller.id = 1234567890123
    roller.name = "Roller"
    roller.battery = 50
    roller.type = 1
    roller.closed_percent = 50
    return roller


@pytest.fixture
def mock_hub(mock_roller: MagicMock) -> Generator[MagicMock]:
    """Mock the aiopulse Hub client."""
    with patch("homeassistant.components.acmeda.hub.aiopulse.Hub") as hub_class:
        hub = hub_class.return_value
        hub.id = "hub-id"
        hub.host = "127.0.0.1"
        hub.rollers = {mock_roller.id: mock_roller}
        hub.run = AsyncMock()
        hub.stop = AsyncMock()
        yield hub


async def test_update_devices_renames_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    mock_hub: MagicMock,
    mock_roller: MagicMock,
) -> None:
    """Test a roller rename is propagated to the device registry."""
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # The integration subscribes a callback which the hub invokes once it has
    # fetched roller updates; grab it and simulate the hub reporting an update.
    notify_update = mock_hub.callback_subscribe.call_args[0][0]
    notify_update(aiopulse.UpdateType.rollers)
    await hass.async_block_till_done()

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, str(mock_roller.id)), mock_config_entry.entry_id
    )
    assert device is not None
    assert device.name == "Roller"

    mock_roller.name = "Living room blind"
    notify_update(aiopulse.UpdateType.rollers)
    await hass.async_block_till_done()

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, str(mock_roller.id)), mock_config_entry.entry_id
    )
    assert device.name == "Living room blind"


async def test_hub_run_immediately_reports_rollers(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_hub: MagicMock,
    mock_roller: MagicMock,
) -> None:
    """Test entities are registered when Hub.run() immediately reports rollers."""

    # Make hub.run() immediately fire the callback with UpdateType.rollers,
    # simulating the race condition where the hub discovers rollers before
    # platforms have finished setting up.
    async def run_immediately() -> None:
        notify_update = mock_hub.callback_subscribe.call_args[0][0]
        notify_update(aiopulse.UpdateType.rollers)

    mock_hub.run = AsyncMock(side_effect=run_immediately)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Verify entities were registered despite the hub reporting rollers
    # during setup rather than after.
    entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert len(entities) == 2
    assert any(e.domain == "cover" for e in entities)
    assert any(e.domain == "sensor" for e in entities)


async def test_hub_callback_from_worker_thread(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_hub: MagicMock,
    mock_roller: MagicMock,
) -> None:
    """Test entities are registered when callback is invoked from a worker thread."""
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    notify_update = mock_hub.callback_subscribe.call_args[0][0]

    # Invoke the callback from a worker thread, simulating how aiopulse
    # reports updates from its own thread. This exercises the
    # call_soon_threadsafe handoff in _schedule_update.
    event = threading.Event()
    thread = threading.Thread(
        target=lambda: (notify_update(aiopulse.UpdateType.rollers), event.set())
    )
    thread.start()
    await asyncio.to_thread(event.wait, 5)
    await asyncio.to_thread(thread.join, 5)
    await hass.async_block_till_done()

    entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert len(entities) == 2
    assert any(e.domain == "cover" for e in entities)
    assert any(e.domain == "sensor" for e in entities)
