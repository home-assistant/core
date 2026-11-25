"""Tests for the iCloud coordinators."""

from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from pytest_homeassistant.common import (
    AsyncMock,
    MockConfigEntry,
    async_fire_time_changed,
)

from homeassistant.components.icloud.coordinator import (
    REMINDERS_LIST_WINDOW,
    REMINDERS_SCAN_INTERVAL,
    IcloudRemindersCoordinator,
)
from homeassistant.core import HomeAssistant

LIST_COUNT = 500


def _mock_list(index: int) -> MagicMock:
    """Build a mock pyicloud reminder list that should become an entity."""
    reminder_list = MagicMock()
    reminder_list.id = f"list-{index}"
    reminder_list.title = f"List {index}"
    reminder_list.is_group = False
    reminder_list.deleted = False
    return reminder_list


def _mock_reminder(uid: str) -> MagicMock:
    """Build a mock pyicloud reminder with the fields the coordinator reads."""
    reminder = MagicMock()
    reminder.id = uid
    reminder.title = "Milk"
    reminder.desc = ""
    reminder.due_date = None
    reminder.all_day = False
    reminder.completed = False
    reminder.completed_date = None
    reminder.parent_reminder_id = None
    reminder.deleted = False
    return reminder


def _fetched_ids(service: MagicMock) -> list[str]:
    """Return the list IDs fetched so far, in request order."""
    return [call.kwargs["list_id"] for call in service.list_reminders.call_args_list]


async def test_reminders_fetch_is_bounded(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    icloud_client: AsyncMock,
) -> None:
    """Many lists must not turn into one CloudKit request per list.

    The old ``_fetch`` called ``list_reminders()`` once for every live list, so
    an account with hundreds of lists made hundreds of CloudKit requests and
    the refresh hit the 300s FETCH_TIMEOUT before any to-do entities appeared.
    """
    service = icloud_client.api.reminders
    service.lists.return_value = [_mock_list(i) for i in range(LIST_COUNT)]
    service.list_reminders.return_value = MagicMock(reminders=[])
    config_entry.runtime_data = icloud_client

    coordinator = IcloudRemindersCoordinator(hass, config_entry)
    data = await coordinator._async_update_data()

    assert len(data) == LIST_COUNT
    assert _fetched_ids(service) == [f"list-{i}" for i in range(REMINDERS_LIST_WINDOW)]


async def test_reminders_fetch_rotates_and_retains_data(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    icloud_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A later refresh fetches the next window and keeps the older lists' data."""
    service = icloud_client.api.reminders
    service.lists.return_value = [_mock_list(i) for i in range(LIST_COUNT)]
    service.list_reminders.side_effect = lambda **kwargs: MagicMock(
        reminders=[_mock_reminder(f"r-{kwargs['list_id']}")]
    )
    config_entry.runtime_data = icloud_client
    coordinator = IcloudRemindersCoordinator(hass, config_entry)
    coordinator.async_add_listener(lambda: None)
    coordinator.async_set_updated_data(await coordinator._async_update_data())
    service.list_reminders.reset_mock()
    freezer.tick(REMINDERS_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert _fetched_ids(service) == [
        f"list-{i}" for i in range(REMINDERS_LIST_WINDOW, 2 * REMINDERS_LIST_WINDOW)
    ]
    assert coordinator.data is not None
    # The first window is no longer fetched, but its reminders remain visible.
    assert [reminder.uid for reminder in coordinator.data["list-0"].reminders] == [
        "r-list-0"
    ]
    assert [
        reminder.uid
        for reminder in coordinator.data[f"list-{REMINDERS_LIST_WINDOW}"].reminders
    ] == [f"r-list-{REMINDERS_LIST_WINDOW}"]
