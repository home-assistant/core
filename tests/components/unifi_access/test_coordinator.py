"""Unit tests for the UniFiAccessDoorCoordinator class."""

from asyncio import Event, Queue, wait_for
import builtins
from contextlib import asynccontextmanager
from unittest.mock import patch

import pytest
import uiaccessclient

from homeassistant import config_entries
from homeassistant.components.unifi_access import UniFiAccessDoorCoordinator
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.typing import ClientSessionGenerator


@pytest.fixture(autouse=True)
def lock_platform_only():
    """Skip setting up platform to speed up tests."""
    with patch("homeassistant.components.unifi_access.PLATFORMS", []):
        yield


async def test_coordinator_lifecycle(
    hass: HomeAssistant,
    aiohttp_client: ClientSessionGenerator,
    config_entry: ConfigEntry,
    mock_doors: list[uiaccessclient.Door],
) -> None:
    """Test the coordinator lifecycle."""
    config_entries.current_entry.set(config_entry)
    coordinator = UniFiAccessDoorCoordinator(
        hass,
        uiaccessclient.ApiClient.get_default(),
        uiaccessclient.WebsocketClient("hostname", "access_token"),
    )

    @asynccontextmanager
    async def notifications_manager():
        yield notifications_iterator

    async def notifications_iterator():
        while not notification_stop.is_set():
            try:
                yield await wait_for(notification_queue.get(), timeout=0.1)
                notification_queue.task_done()
            except builtins.TimeoutError:
                continue

    notification_stop = Event()
    notification_queue = Queue()
    notifications_iterator = notifications_iterator()

    # Run first refresh
    with (
        patch(
            "homeassistant.config_entries.ConfigEntry.__setattr__", object.__setattr__
        ),
        patch.object(config_entry, "state", ConfigEntryState.SETUP_IN_PROGRESS),
        patch(
            "uiaccessclient.WebsocketClient.device_notifications",
            return_value=notifications_manager(),
        ),
        patch(
            "uiaccessclient.SpaceApi.fetch_all_doors",
            return_value=uiaccessclient.DoorsResponse(data=mock_doors),
        ),
    ):
        await coordinator.async_config_entry_first_refresh()

    # Assert state after first refresh
    assert coordinator.task is not None
    assert not coordinator.task.cancelled()

    assert len(coordinator.data) == 2
    assert coordinator.data["id-1"] == mock_doors[0]
    assert coordinator.data["id-2"] == mock_doors[1]

    # Trigger update by sending event on the coordinator's websocket
    with patch(
        "uiaccessclient.SpaceApi.fetch_all_doors",
        return_value=uiaccessclient.DoorsResponse(data=mock_doors[1:]),
    ):
        await notification_queue.put(
            uiaccessclient.Notification(
                event=uiaccessclient.NotificationEvent.DeviceUpdateV2
            )
        )
        await notification_queue.join()
        notification_stop.set()

    # Assert state after update triggered from websocket
    assert len(coordinator.data) == 1
    assert coordinator.data["id-2"] == mock_doors[1]

    await coordinator.async_shutdown()
    assert coordinator.task.done()
